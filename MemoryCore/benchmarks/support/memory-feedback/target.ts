/** Target-binding baseline used by feedback experiments. */
import type { DecisionTrace, FeedbackTargetType } from './trace.js';

export type TargetableDecision = Pick<DecisionTrace,
  'candidateMemoryIds' | 'outputIds' | 'toolCallIds'>;

export interface FeedbackTargetReference {
  targetType: Exclude<FeedbackTargetType, 'unknown'>;
  targetId: string;
}

export interface FeedbackTargetEvidence {
  /** Trusted host/tool references, not IDs parsed from free-form model reasoning. */
  explicitReferences?: readonly FeedbackTargetReference[];
  /** Host conversation edge; identifies the answer object, not its memory cause. */
  replyToOutputId?: string | null;
}

export interface FeedbackTargetBinding {
  status: 'bound' | 'unknown';
  targetType: FeedbackTargetType;
  targetIds: readonly string[];
  reason: 'explicit_reference' | 'reply_to_output' | 'no_target_evidence'
    | 'invalid_reference' | 'conflicting_references';
}

function allowed(decision: TargetableDecision, reference: FeedbackTargetReference): boolean {
  if (reference.targetType === 'memory_assertion') {
    return decision.candidateMemoryIds.includes(reference.targetId);
  }
  if (reference.targetType === 'tool_call') return decision.toolCallIds.includes(reference.targetId);
  return decision.outputIds.includes(reference.targetId);
}

/** High-precision object binding. It never promotes answer feedback to a memory cause. */
export function bindFeedbackTarget(
  decision: TargetableDecision,
  evidence: FeedbackTargetEvidence,
): FeedbackTargetBinding {
  const references = evidence.explicitReferences ?? [];
  if (references.some(reference => !reference.targetId.trim() || !allowed(decision, reference))) {
    return { status: 'unknown', targetType: 'unknown', targetIds: [], reason: 'invalid_reference' };
  }
  const unique = new Map(references.map(reference =>
    [`${reference.targetType}\u001f${reference.targetId}`, reference]));
  if (unique.size > 1) {
    return { status: 'unknown', targetType: 'unknown', targetIds: [], reason: 'conflicting_references' };
  }
  if (unique.size === 1) {
    const [reference] = unique.values();
    return { status: 'bound', targetType: reference.targetType,
      targetIds: [reference.targetId], reason: 'explicit_reference' };
  }
  if (evidence.replyToOutputId && decision.outputIds.includes(evidence.replyToOutputId)) {
    return { status: 'bound', targetType: 'answer_span',
      targetIds: [evidence.replyToOutputId], reason: 'reply_to_output' };
  }
  return { status: 'unknown', targetType: 'unknown', targetIds: [], reason: 'no_target_evidence' };
}
