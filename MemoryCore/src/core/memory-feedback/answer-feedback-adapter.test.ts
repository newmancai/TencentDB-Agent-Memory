import { describe, expect, it, vi } from 'vitest';
import { runAnswerFeedbackAdapter } from './answer-feedback-adapter.js';

const observation = { answerId: 'answer-1', candidates: [
  { id: 'failed-1', checkerPass: false },
  { id: 'failed-2', checkerPass: false },
  { id: 'passed', checkerPass: true },
] };
const baseline = ['host-baseline'];
const common = {
  observation,
  baselineFeedback: baseline,
  signalType: 'explicit_correction' as const,
  policyVersion: 'temporary-feedback:v1',
};

describe('answer feedback adapter', () => {
  it('keeps the feature off and emits a baseline decision log', async () => {
    const selector = vi.fn(async () => ['failed-1']);
    const result = await runAnswerFeedbackAdapter({ ...common, enabled: false, selector });

    expect(result.feedback).toBe(baseline);
    expect(selector).not.toHaveBeenCalled();
    expect(result.decisionLog).toMatchObject({
      mode: 'baseline', status: 'off', k: 8, auxiliaryPathUsed: false,
      fallback: false, fallbackReason: null, useBaseline: true,
      candidateCount: 3, eligibleCandidateCount: 2, selectedCount: 0,
    });
  });

  it('records a bounded enabled selection', async () => {
    const result = await runAnswerFeedbackAdapter({ ...common, enabled: true,
      maxSelectedK: 1, selector: async () => ['failed-1'] });

    expect(result.feedback).toEqual(['failed-1']);
    expect(result.decisionLog).toMatchObject({
      mode: 'enabled', status: 'selected', k: 1, auxiliaryPathUsed: true,
      fallback: false, useBaseline: false, selectedCount: 1,
    });
    expect(result.decisionLog.elapsedMs).toBeGreaterThanOrEqual(0);
  });

  it('forces baseline fallback when the auxiliary selector fails', async () => {
    const result = await runAnswerFeedbackAdapter({ ...common, enabled: true,
      selector: async () => { throw Error('forced failure'); } });

    expect(result.feedback).toBe(baseline);
    expect(result.decisionLog).toMatchObject({
      status: 'fallback', auxiliaryPathUsed: true, fallback: true,
      fallbackReason: 'selector_failed', useBaseline: true, selectedCount: 0,
    });
  });

  it('rejects a selection larger than k and an invalid adapter configuration', async () => {
    const overK = await runAnswerFeedbackAdapter({ ...common, enabled: true,
      maxSelectedK: 1, selector: async () => ['failed-1', 'failed-2'] });
    expect(overK.feedback).toBe(baseline);
    expect(overK.decisionLog).toMatchObject({
      status: 'fallback', fallbackReason: 'invalid_selection', k: 1,
    });

    const selector = vi.fn(async () => ['failed-1']);
    const invalid = await runAnswerFeedbackAdapter({ ...common, enabled: true,
      maxSelectedK: 33, selector });
    expect(invalid.feedback).toBe(baseline);
    expect(invalid.decisionLog).toMatchObject({
      status: 'fallback', fallbackReason: 'invalid_config', auxiliaryPathUsed: false,
    });
    expect(selector).not.toHaveBeenCalled();
  });
});
