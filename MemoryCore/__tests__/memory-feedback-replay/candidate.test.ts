import { describe, expect, it } from 'vitest';

import { compileFeedbackAssertionCandidate } from '../../benchmarks/support/memory-feedback/candidate.js';
import { observeFeedback } from '../../benchmarks/support/memory-feedback/trace.js';

function claim(overrides = {}) {
  return observeFeedback({
    id: 'claim-1', decisionId: 'decision-1', observationType: 'explicit_correction',
    targetType: 'answer_span', targetIds: ['answer-1'],
    claimText: 'Use port 9090, not 8080.', scope: 'current interaction',
    authority: 'explicit_user', confidence: 1, sourceEventIds: ['event-1'],
    observedAt: '2026-09-13T00:00:00.000Z', ...overrides,
  });
}

describe('compileFeedbackAssertionCandidate', () => {
  it('creates only a current-interaction candidate from verbatim explicit feedback', () => {
    const result = compileFeedbackAssertionCandidate(claim(), {
      action: 'propose', evidence_quote: 'port 9090', proposition: 'Use port 9090.',
      scope: 'current_interaction',
    }, { id: 'assertion-1', recordedAt: '2026-09-13T00:00:01.000Z' });
    expect(result).toMatchObject({
      id: 'assertion-1', subject: 'answer-1', predicate: 'explicit_user_correction',
      scope: 'current interaction', status: 'candidate', authority: 'explicit_user',
      supportedByClaimIds: ['claim-1'],
    });
  });

  it('returns null for a clean abstention', () => {
    expect(compileFeedbackAssertionCandidate(claim(), {
      action: 'abstain', evidence_quote: '', proposition: '', scope: 'none',
    }, { id: 'unused', recordedAt: '2026-09-13T00:00:01.000Z' })).toBeNull();
  });

  it.each([
    ['non-verbatim evidence', claim(), { action: 'propose', evidence_quote: 'port 7070', proposition: 'Use port 7070.', scope: 'current_interaction' }],
    ['unbound target', claim({ decisionId: null, targetType: 'unknown', targetIds: [] }), { action: 'propose', evidence_quote: 'port 9090', proposition: 'Use port 9090.', scope: 'current_interaction' }],
    ['broader claim scope', claim({ scope: 'all projects' }), { action: 'propose', evidence_quote: 'port 9090', proposition: 'Use port 9090.', scope: 'current_interaction' }],
  ])('rejects %s', (_name, feedback, proposal) => {
    expect(() => compileFeedbackAssertionCandidate(
      feedback,
      proposal as Parameters<typeof compileFeedbackAssertionCandidate>[1],
      { id: 'assertion-1', recordedAt: '2026-09-13T00:00:01.000Z' },
    )).toThrow();
  });
});
