import { createHash } from 'node:crypto';

import {
  assertRecallShadowObservation,
  type RecallShadowObservation,
} from '../self-supervision/recall-shadow-adapter.js';
import {
  selectMemoryAction,
  type DecisionTrace,
  type PromptMemorySpan,
  type TraceCost,
} from './trace.js';

export interface RecallDecisionTraceInput {
  observation: RecallShadowObservation;
  policyVersion: string;
  /** Probability of this exact include/omit plus selected-memory set. */
  propensity: number;
  prompt: string;
  promptMemorySpans: readonly PromptMemorySpan[];
  outputIds: readonly string[];
  toolCallIds?: readonly string[];
  contextEventIds?: readonly string[];
  cost?: TraceCost;
}

const hash = (value: string) => createHash('sha256').update(value, 'utf8').digest('hex');

/**
 * Convert the existing byte-acknowledged OpenClaw recall observation into a
 * policy decision record. Exposure means include, not proven downstream use.
 */
export function decisionTraceFromRecallObservation(input: RecallDecisionTraceInput): DecisionTrace {
  assertRecallShadowObservation(input.observation);
  if (!input.outputIds.length) throw Error('Recall decision trace requires an output ID');
  const candidates = input.observation.candidates.map(candidate => candidate.recordId);
  const selected = input.observation.candidates.filter(candidate => candidate.exposed);
  const selectedIds = selected.map(candidate => candidate.recordId);
  const spanByMemory = new Map<string, PromptMemorySpan>();
  for (const span of input.promptMemorySpans) {
    if (spanByMemory.has(span.memoryId)) throw Error(`Duplicate prompt span for ${span.memoryId}`);
    spanByMemory.set(span.memoryId, span);
  }
  for (const candidate of selected) {
    const span = spanByMemory.get(candidate.recordId);
    if (!span) throw Error(`Missing prompt span for exposed memory ${candidate.recordId}`);
    const rendered = input.prompt.slice(span.start, span.end);
    if (!candidate.renderedHash || hash(rendered) !== candidate.renderedHash) {
      throw Error(`Prompt span hash mismatch for exposed memory ${candidate.recordId}`);
    }
  }
  if (input.promptMemorySpans.some(span => !selectedIds.includes(span.memoryId))) {
    throw Error('Prompt span references a memory that was not exposed');
  }

  return selectMemoryAction({
    id: `${input.observation.traceId}:decision`,
    contextId: input.observation.sessionId ?? input.observation.sessionKey,
    taskId: input.observation.taskRunId ?? input.observation.traceId,
    contextEventIds: [...new Set([input.observation.eventId, ...(input.contextEventIds ?? [])])],
    candidateMemoryIds: candidates,
    action: selectedIds.length ? 'include' : 'omit',
    selectedMemoryIds: selectedIds,
    policyVersion: input.policyVersion,
    propensity: input.propensity,
    decidedAt: input.observation.exposureObservedAt,
    promptMemorySpans: [...input.promptMemorySpans],
    outputIds: [...input.outputIds],
    toolCallIds: [...(input.toolCallIds ?? [])],
    ...(input.cost ? { cost: input.cost } : {}),
  });
}
