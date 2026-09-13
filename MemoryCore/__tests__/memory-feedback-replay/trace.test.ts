import { describe, expect, it } from 'vitest';
import {
  observeFeedback,
  recordMemoryAssertion,
  recordOutcome,
  selectMemoryAction,
  validateFeedbackReplay,
} from '../../benchmarks/support/memory-feedback/trace.js';

const decision = () => selectMemoryAction({
  id: 'decision-1',
  contextId: 'context-1',
  taskId: 'task-1',
  contextEventIds: ['event-request'],
  candidateMemoryIds: ['memory-old'],
  action: 'include',
  selectedMemoryIds: ['memory-old'],
  policyVersion: 'policy:v1',
  propensity: 0.5,
  decidedAt: '2026-09-13T00:00:00.000Z',
  promptMemorySpans: [{ memoryId: 'memory-old', start: 10, end: 30 }],
  outputIds: ['answer-1'],
  toolCallIds: [],
  cost: { inputTokens: 100, outputTokens: 20, latencyMs: 50, monetaryUsd: null },
});

describe('feedback trace replay', () => {
  it('links a complete decision, claim, assertion and numeric outcome', () => {
    const selected = decision();
    const claim = observeFeedback({
      id: 'claim-1', decisionId: selected.id, observationType: 'explicit_correction',
      targetType: 'answer_span', targetIds: ['answer-1:0-8'], claimText: 'Use port 9090.',
      scope: 'project=demo', authority: 'explicit_user', confidence: 1,
      sourceEventIds: ['event-feedback'], observedAt: '2026-09-13T00:01:00.000Z',
    });
    const assertion = recordMemoryAssertion({
      id: 'assertion-1', subject: 'demo', predicate: 'port', value: 9090,
      scope: 'project=demo', validFrom: '2026-09-13T00:01:00.000Z', validTo: null,
      recordedAt: '2026-09-13T00:02:00.000Z', supersededAt: null, status: 'verified',
      authority: 'explicit_user', sourceEventIds: ['event-feedback'],
      supportedByClaimIds: [claim.id], contradictsAssertionIds: [],
    });
    const outcome = recordOutcome({
      id: 'outcome-1', decisionId: selected.id, result: 'success', reward: 1,
      metrics: { checkerPass: true }, source: 'task-checker',
      observedAt: '2026-09-13T00:03:00.000Z', delayed: true,
    });

    const replay = validateFeedbackReplay([selected, claim, assertion, outcome]);
    expect(replay).toMatchObject({ ok: true, counts: {
      decision_trace: 1, feedback_claim: 1, memory_assertion: 1, outcome: 1,
    } });
    expect(replay.learningSamples).toEqual([{
      decisionId: selected.id, feedbackClaimIds: [claim.id], outcomeIds: [outcome.id],
    }]);
    expect(replay.pendingDecisionIds).toEqual([]);
  });

  it.each([
    ['candidateMemoryIds', 'missing_candidate_set'],
    ['action', 'missing_action'],
    ['propensity', 'missing_propensity'],
  ] as const)('rejects a learning log missing %s', (field, code) => {
    const incomplete = { ...decision() } as Record<string, unknown>;
    delete incomplete[field];
    const replay = validateFeedbackReplay([incomplete]);
    expect(replay.ok).toBe(false);
    expect(replay.issues.map(issue => issue.code)).toContain(code);
    expect(replay.learningSamples).toEqual([]);
  });

  it('keeps unresolved feedback explicit without inventing an attribution', () => {
    const claim = observeFeedback({
      id: 'claim-unbound', decisionId: null, observationType: 'implicit', targetType: 'unknown',
      targetIds: [], claimText: 'The user retried.', scope: 'session=current',
      authority: 'behavioral', confidence: 0.2, sourceEventIds: ['event-retry'],
      observedAt: '2026-09-13T00:01:00.000Z',
    });
    expect(validateFeedbackReplay([claim])).toMatchObject({ ok: true, learningSamples: [] });
    expect(() => observeFeedback({ ...claim, decisionId: null,
      targetType: 'answer_span', targetIds: ['answer-1'] })).toThrow('unbound feedback');
  });

  it('rejects selections outside the logged candidate set and invalid bitemporal ranges', () => {
    expect(() => selectMemoryAction({ ...decision(), candidateMemoryIds: ['other'] }))
      .toThrow('selected memories must be candidates');
    expect(() => recordMemoryAssertion({
      id: 'assertion-bad-time', subject: 'demo', predicate: 'port', value: 9090,
      scope: 'project=demo', validFrom: '2026-09-14T00:00:00.000Z',
      validTo: '2026-09-13T00:00:00.000Z', recordedAt: '2026-09-13T00:00:00.000Z',
      supersededAt: null, status: 'candidate', authority: 'explicit_user',
      sourceEventIds: ['event-feedback'], supportedByClaimIds: [], contradictsAssertionIds: [],
    })).toThrow('validTo cannot precede validFrom');
  });

  it('fails closed on forward causal links and exposes non-numeric outcomes as pending', () => {
    const selected = decision();
    const unknownOutcome = recordOutcome({
      id: 'outcome-unknown', decisionId: selected.id, result: 'unknown', reward: null,
      metrics: {}, source: 'timeout', observedAt: '2026-09-13T00:03:00.000Z', delayed: true,
    });
    expect(validateFeedbackReplay([selected, unknownOutcome])).toMatchObject({
      ok: true, learningSamples: [], pendingDecisionIds: [selected.id],
    });

    const reversed = validateFeedbackReplay([unknownOutcome, selected]);
    expect(reversed.ok).toBe(false);
    expect(reversed.issues.map(issue => issue.code)).toContain('missing_prior_decision');
  });

  it('rejects duplicate record IDs across schema kinds', () => {
    const selected = decision();
    const duplicate = recordOutcome({
      id: selected.id, decisionId: selected.id, result: 'success', reward: 1,
      metrics: {}, source: 'checker', observedAt: '2026-09-13T00:03:00.000Z', delayed: false,
    });
    const replay = validateFeedbackReplay([selected, duplicate]);
    expect(replay.ok).toBe(false);
    expect(replay.issues.map(issue => issue.code)).toContain('duplicate_record_id');
  });
});
