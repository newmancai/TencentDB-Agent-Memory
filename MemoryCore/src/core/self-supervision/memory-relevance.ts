import {
  canonicalHash,
  memoryRelevanceSubjectBindingHash,
} from "./observation-plane.js";
import type {
  MemoryRelevanceAuthorityRef,
  MemoryRelevanceBasis,
  MemoryRelevanceDecision,
  MemoryRelevanceObservation,
} from "./types.js";

export interface PreRetrievalMemoryRelevanceSubject {
  taskRunId: string;
  sessionId: string;
  preRetrievalContextHash: string;
  authority: MemoryRelevanceAuthorityRef;
}

export interface IndependentMemoryRelevanceEvaluator {
  readonly id: string;
  readonly version: string;
  readonly evaluatorDigest: string;
  readonly policyDigest: string;
  readonly basis: Exclude<MemoryRelevanceBasis, "unavailable">;
  readonly calibrationArtifactDigest: string | null;
  readonly inputSurface: "pre_retrieval_subject_and_authority_only";
  evaluate(
    subject: Readonly<PreRetrievalMemoryRelevanceSubject>,
  ): Promise<{
    decision: Exclude<MemoryRelevanceDecision, "unknown">;
    evidenceHash: string;
  }>;
}

function requireNonEmpty(value: string, field: string): void {
  if (!value.trim()) throw new Error(`${field} is required`);
}

function requireSha256(value: string, field: string): void {
  if (!/^[a-f0-9]{64}$/i.test(value)) throw new Error(`${field} must be a SHA-256 digest`);
}

function deepFreeze<T>(value: T, seen = new Set<object>()): T {
  if (!value || typeof value !== "object" || seen.has(value as object)) return value;
  seen.add(value as object);
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function exactSubject(subject: PreRetrievalMemoryRelevanceSubject): PreRetrievalMemoryRelevanceSubject {
  return {
    taskRunId: subject.taskRunId,
    sessionId: subject.sessionId,
    preRetrievalContextHash: subject.preRetrievalContextHash,
    authority: {
      authorityId: subject.authority.authorityId,
      authorityVersion: subject.authority.authorityVersion,
      effectiveAt: subject.authority.effectiveAt,
      authoritySnapshotDigest: subject.authority.authoritySnapshotDigest,
    },
  };
}

function validateSubject(subject: PreRetrievalMemoryRelevanceSubject): void {
  requireNonEmpty(subject.taskRunId, "taskRunId");
  requireNonEmpty(subject.sessionId, "sessionId");
  requireSha256(subject.preRetrievalContextHash, "preRetrievalContextHash");
  requireNonEmpty(subject.authority.authorityId, "authority.authorityId");
  requireNonEmpty(subject.authority.authorityVersion, "authority.authorityVersion");
  if (!Number.isFinite(Date.parse(subject.authority.effectiveAt))) {
    throw new Error("authority.effectiveAt must be an ISO-compatible timestamp");
  }
  requireSha256(subject.authority.authoritySnapshotDigest, "authority.authoritySnapshotDigest");
}

/**
 * The evaluator receives a recursively frozen whitelist view containing no
 * production candidates, ranks, scores, exposures, or post-retrieval context.
 */
export async function evaluateIndependentMemoryRelevance(input: {
  subject: PreRetrievalMemoryRelevanceSubject;
  evaluator: IndependentMemoryRelevanceEvaluator;
  evaluatedAt: string;
}): Promise<MemoryRelevanceObservation> {
  validateSubject(input.subject);
  if (!Number.isFinite(Date.parse(input.evaluatedAt))) {
    throw new Error("evaluatedAt must be an ISO-compatible timestamp");
  }
  if (Date.parse(input.subject.authority.effectiveAt) > Date.parse(input.evaluatedAt)) {
    throw new Error("Memory relevance authority cannot become effective after evaluation");
  }
  const evaluator = input.evaluator;
  if (evaluator.inputSurface !== "pre_retrieval_subject_and_authority_only") {
    throw new Error("Memory relevance evaluator declares a forbidden input surface");
  }
  requireNonEmpty(evaluator.id, "evaluator.id");
  requireNonEmpty(evaluator.version, "evaluator.version");
  requireSha256(evaluator.evaluatorDigest, "evaluator.evaluatorDigest");
  requireSha256(evaluator.policyDigest, "evaluator.policyDigest");
  if (evaluator.basis === "calibrated_no_match_model") {
    if (!evaluator.calibrationArtifactDigest) {
      throw new Error("Model-based Memory relevance requires a calibration artifact digest");
    }
    requireSha256(evaluator.calibrationArtifactDigest, "evaluator.calibrationArtifactDigest");
  } else if (evaluator.calibrationArtifactDigest !== null) {
    throw new Error("Non-model Memory relevance cannot claim a calibration artifact");
  }

  const subject = deepFreeze(exactSubject(input.subject));
  const result = await evaluator.evaluate(subject);
  if (result.decision !== "memory_relevant" && result.decision !== "no_match") {
    throw new Error("Independent evaluator must return a decisive relevance result or fail closed upstream");
  }
  requireSha256(result.evidenceHash, "relevance evidenceHash");
  return deepFreeze({
    schemaVersion: "tdai-memory-relevance.v1" as const,
    decision: result.decision,
    basis: evaluator.basis,
    evaluatorId: evaluator.id,
    evaluatorVersion: evaluator.version,
    evaluatorDigest: evaluator.evaluatorDigest,
    policyDigest: evaluator.policyDigest,
    evaluatedAt: input.evaluatedAt,
    evidenceHash: result.evidenceHash,
    authority: structuredClone(subject.authority),
    calibrationArtifactDigest: evaluator.calibrationArtifactDigest,
    subjectBindingHash: memoryRelevanceSubjectBindingHash({
      taskRunId: subject.taskRunId,
      sessionId: subject.sessionId,
      preRetrievalContextHash: subject.preRetrievalContextHash,
      authority: subject.authority,
    }),
    independentOfProductionRetrieval: true as const,
    evaluationSurface: "pre_retrieval_subject_and_authority_only" as const,
  });
}

/** Explicit fallback used when no trusted independent evaluator/authority is available. */
export function unavailableMemoryRelevance(input: {
  taskRunId: string;
  sessionId: string;
  preRetrievalContextHash: string;
  evaluatedAt: string;
}): MemoryRelevanceObservation {
  requireNonEmpty(input.taskRunId, "taskRunId");
  requireNonEmpty(input.sessionId, "sessionId");
  requireSha256(input.preRetrievalContextHash, "preRetrievalContextHash");
  if (!Number.isFinite(Date.parse(input.evaluatedAt))) {
    throw new Error("evaluatedAt must be an ISO-compatible timestamp");
  }
  return deepFreeze({
    schemaVersion: "tdai-memory-relevance.v1" as const,
    decision: "unknown" as const,
    basis: "unavailable" as const,
    evaluatorId: "unavailable",
    evaluatorVersion: "unavailable",
    evaluatorDigest: canonicalHash("unavailable-memory-relevance-evaluator"),
    policyDigest: canonicalHash("unavailable-memory-relevance-policy"),
    evaluatedAt: input.evaluatedAt,
    evidenceHash: null,
    authority: null,
    calibrationArtifactDigest: null,
    subjectBindingHash: memoryRelevanceSubjectBindingHash({
      taskRunId: input.taskRunId,
      sessionId: input.sessionId,
      preRetrievalContextHash: input.preRetrievalContextHash,
      authority: null,
    }),
    independentOfProductionRetrieval: true as const,
    evaluationSurface: "pre_retrieval_subject_and_authority_only" as const,
  });
}
