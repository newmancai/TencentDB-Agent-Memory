import {
  selectAnswerFeedback,
  type AnswerFeedbackObservation,
  type AnswerFeedbackResult,
} from './answer-feedback.js';
import type { FeedbackObservationType } from './trace.js';

export interface AnswerFeedbackDecisionLog {
  schema: 1;
  feature: 'temporary_answer_feedback';
  mode: 'baseline' | 'enabled';
  status: AnswerFeedbackResult['status'];
  policyVersion: string;
  signalType: FeedbackObservationType;
  /** Maximum number of auxiliary feedback items accepted from the selector. */
  k: number;
  candidateCount: number;
  eligibleCandidateCount: number;
  selectedCount: number;
  auxiliaryPathUsed: boolean;
  fallback: boolean;
  fallbackReason: AnswerFeedbackResult['reason'] | 'invalid_config' | null;
  useBaseline: boolean;
  elapsedMs: number;
}

export interface AnswerFeedbackAdapterResult extends AnswerFeedbackResult {
  decisionLog: AnswerFeedbackDecisionLog;
}

/**
 * Portable host adapter for the temporary B sidecar.
 *
 * The host keeps ownership of the baseline and selector. This wrapper adds a
 * bounded selection size and one structured decision log without changing the
 * selector contract or granting a memory-write handle.
 */
export async function runAnswerFeedbackAdapter<T extends AnswerFeedbackObservation>(p: {
  enabled: boolean;
  observation: T;
  baselineFeedback: readonly string[];
  selector: (observation: T, signal: AbortSignal) => Promise<readonly string[] | null>;
  signalType: FeedbackObservationType;
  policyVersion: string;
  maxSelectedK?: number;
  timeoutMs?: number;
}): Promise<AnswerFeedbackAdapterResult> {
  const started = performance.now();
  const k = p.maxSelectedK ?? 8;
  const candidates = Array.isArray(p.observation?.candidates) ? p.observation.candidates : [];
  const eligibleCandidateCount = candidates.filter(candidate => candidate?.checkerPass === false).length;
  let selectorInvoked = false;
  const validConfig = Number.isInteger(k) && k >= 1 && k <= 32
    && typeof p.policyVersion === 'string' && !!p.policyVersion.trim();

  let result: AnswerFeedbackResult;
  let adapterReason: AnswerFeedbackDecisionLog['fallbackReason'] = null;
  if (!validConfig) {
    result = {
      feedback: p.baselineFeedback,
      useBaseline: true,
      status: 'fallback',
      reason: 'invalid_observation',
      elapsedMs: performance.now() - started,
    };
    adapterReason = 'invalid_config';
  } else {
    result = await selectAnswerFeedback({
      enabled: p.enabled,
      observation: p.observation,
      baselineFeedback: p.baselineFeedback,
      timeoutMs: p.timeoutMs,
      selector: async (observation, signal) => {
        selectorInvoked = true;
        const selected = await p.selector(observation, signal);
        return Array.isArray(selected) && selected.length > k ? null : selected;
      },
    });
    adapterReason = result.reason ?? null;
  }

  const decisionLog: AnswerFeedbackDecisionLog = {
    schema: 1,
    feature: 'temporary_answer_feedback',
    mode: p.enabled ? 'enabled' : 'baseline',
    status: result.status,
    policyVersion: p.policyVersion,
    signalType: p.signalType,
    k,
    candidateCount: candidates.length,
    eligibleCandidateCount,
    selectedCount: result.status === 'selected' ? result.feedback.length : 0,
    auxiliaryPathUsed: selectorInvoked,
    fallback: result.status === 'fallback',
    fallbackReason: adapterReason,
    useBaseline: result.useBaseline,
    elapsedMs: result.elapsedMs,
  };
  return { ...result, decisionLog };
}
