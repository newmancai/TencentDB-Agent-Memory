/** Temporary feedback about an answer; this interface grants no memory write handle. */
export interface AnswerFeedbackObservation {
  answerId: string;
  candidates: readonly { id: string; checkerPass: boolean | null }[];
}

export interface AnswerFeedbackResult {
  feedback: readonly string[];
  useBaseline: boolean;
  status: 'off' | 'selected' | 'fallback';
  reason?: 'timeout' | 'invalid_observation' | 'invalid_selection' | 'selector_failed';
  elapsedMs: number;
}

/** Match the research terminal-line contract; never recover IDs from reasoning text. */
export function parseAnswerFeedback(text: string, outputLimited = false): readonly string[] | null {
  if (outputLimited) return null;
  const line = text.trim().split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/).at(-1) ?? '';
  const match = /^(?:\*\*)?ACTIONABLE:(?:\*\*)?\s*(\[.*\]|unknown)$/.exec(line);
  if (!match || match[1] === 'unknown') return null;
  try {
    const ids: unknown = JSON.parse(match[1]);
    return Array.isArray(ids) && ids.every(id => typeof id === 'string')
      && new Set(ids).size === ids.length ? ids.sort() : null;
  } catch { return null; }
}

/**
 * The host supplies its already computed baseline, not an extra fallback model call.
 * State loading/validation belongs inside selector and shares this single deadline.
 * Selectors must honor the abort signal and must not publish side effects.
 */
export async function selectAnswerFeedback<T extends AnswerFeedbackObservation>(p: {
  enabled: boolean;
  observation: T;
  baselineFeedback: readonly string[];
  selector: (observation: T, signal: AbortSignal) => Promise<readonly string[] | null>;
  timeoutMs?: number;
}): Promise<AnswerFeedbackResult> {
  const start = performance.now();
  const fallback = (reason: AnswerFeedbackResult['reason']): AnswerFeedbackResult => ({
    feedback: p.baselineFeedback, useBaseline: true, status: 'fallback', reason,
    elapsedMs: performance.now() - start,
  });
  if (!p.enabled) return { feedback: p.baselineFeedback, useBaseline: true,
    status: 'off', elapsedMs: performance.now() - start };
  const timeoutMs = p.timeoutMs ?? 30_000;
  if (!p.observation || typeof p.observation !== 'object'
      || typeof p.observation.answerId !== 'string' || !p.observation.answerId.trim()) {
    return fallback('invalid_observation');
  }
  const candidates = p.observation.candidates;
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 30_000
      || !Array.isArray(candidates) || candidates.length > 256
      || candidates.some(c => !c || typeof c.id !== 'string' || !c.id
        || ![true, false, null].includes(c.checkerPass))
      || new Set(candidates.map(c => c.id)).size !== candidates.length) {
    return fallback('invalid_observation');
  }
  const eligible = new Set(candidates.filter(c => c.checkerPass === false).map(c => c.id));
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = Symbol('timeout');
  try {
    const selected = await Promise.race([
      Promise.resolve().then(() => p.selector(p.observation, controller.signal)),
      new Promise<typeof timeout>(resolve => {
        timer = setTimeout(() => { resolve(timeout); controller.abort(); }, timeoutMs);
      }),
    ]);
    if (selected === timeout || performance.now() - start >= timeoutMs) {
      controller.abort();
      return fallback('timeout');
    }
    if (!Array.isArray(selected) || selected.length > eligible.size
        || selected.some(id => typeof id !== 'string' || !eligible.has(id))
        || new Set(selected).size !== selected.length) return fallback('invalid_selection');
    return { feedback: [...selected].sort(), useBaseline: false, status: 'selected',
      elapsedMs: performance.now() - start };
  } catch { return fallback('selector_failed'); }
  finally { if (timer) clearTimeout(timer); }
}
