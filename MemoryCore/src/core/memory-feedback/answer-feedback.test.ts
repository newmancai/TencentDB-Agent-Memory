import { afterEach, describe, expect, it, vi } from 'vitest';
import { parseAnswerFeedback, selectAnswerFeedback } from './answer-feedback.js';

const observation = { answerId: 'answer-1', candidates: [
  { id: 'failed', checkerPass: false }, { id: 'passed', checkerPass: true },
  { id: 'unknown', checkerPass: null },
] };
const baseline = ['host-original'];
afterEach(() => vi.useRealTimers());

describe('temporary answer feedback', () => {
  it('off preserves the baseline without invoking the selector or state loader', async () => {
    const selector = vi.fn();
    const result = await selectAnswerFeedback({ enabled: false, observation,
      baselineFeedback: baseline, selector });
    expect(result.status).toBe('off');
    expect(result.feedback).toBe(baseline);
    expect(selector).not.toHaveBeenCalled();
  });

  it.each([{ selected: [] }, { selected: ['failed'] }])('accepts a valid subset $selected', async ({ selected }) => {
    const result = await selectAnswerFeedback({ enabled: true, observation,
      baselineFeedback: baseline, selector: async () => selected });
    expect(result).toMatchObject({ status: 'selected', useBaseline: false, feedback: selected });
  });

  it.each([null, ['passed'], ['unknown'], ['foreign'], ['failed', 'failed']].map(value => ({ value })))(
    'returns baseline for unknown or invalid selection $value', async ({ value }) => {
      const result = await selectAnswerFeedback({ enabled: true, observation,
        baselineFeedback: baseline, selector: async () => value as unknown as string[] });
      expect(result.status).toBe('fallback');
      expect(result.feedback).toBe(baseline);
    });

  it('a corrupt state/load error returns the original baseline', async () => {
    const result = await selectAnswerFeedback({ enabled: true, observation,
      baselineFeedback: baseline, selector: async () => { JSON.parse('{'); return []; } });
    expect(result).toMatchObject({ status: 'fallback', reason: 'selector_failed' });
    expect(result.feedback).toBe(baseline);
  });

  it('times out the whole selector and ignores its late result', async () => {
    vi.useFakeTimers();
    let finish!: (ids: string[]) => void;
    let signal!: AbortSignal;
    const pending = selectAnswerFeedback({ enabled: true, observation,
      baselineFeedback: baseline, timeoutMs: 10,
      selector: async (_o, s) => { signal = s; return new Promise(resolve => { finish = resolve; }); } });
    await vi.advanceTimersByTimeAsync(10);
    const result = await pending;
    expect(result.reason).toBe('timeout');
    expect(signal.aborted).toBe(true);
    finish(['failed']);
    await Promise.resolve();
    expect(result.feedback).toBe(baseline);
  });

  it('reads only the terminal list and rejects capped or malformed output', () => {
    expect(parseAnswerFeedback('explanation\nACTIONABLE: ["failed"]')).toEqual(['failed']);
    expect(parseAnswerFeedback('ACTIONABLE: []')).toEqual([]);
    expect(parseAnswerFeedback('ACTIONABLE: ["failed"]', true)).toBeNull();
    expect(parseAnswerFeedback('ACTIONABLE: ["failed"]\ntrailing')).toBeNull();
    expect(parseAnswerFeedback('ACTIONABLE: [{"id":"failed"}]')).toBeNull();
  });
});
