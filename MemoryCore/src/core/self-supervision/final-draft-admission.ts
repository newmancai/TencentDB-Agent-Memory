import crypto from "node:crypto";
import type { ConversationMessage } from "../conversation/l0-recorder.js";
import type { DedupDecision, ExtractedMemory, MemoryType } from "../record/l1-writer.js";
import type { LLMRunner } from "../types.js";

export type ScopeApplicability = "behavior_rule" | "not_applicable" | "unknown";
export type ContentSupport = "supported" | "refuted" | "unknown";
export type AdoptionStatus = "established" | "not_established" | "unknown";
export type ScopeHorizon = "cross_task" | "task" | "session" | "unknown";

export interface ScopeAssessmentV1 {
  applicability: ScopeApplicability;
  contentSupport: ContentSupport;
  adoption: AdoptionStatus;
  scope: {
    subject: string | null;
    condition: string | null;
    horizon: ScopeHorizon;
    validFrom: string | null;
    validUntil: string | null;
  };
  evidence: Array<{
    messageId: string;
    excerpt: string;
    supports: "content" | "scope" | "adoption" | "counterevidence";
  }>;
}

export interface FinalMemoryDraft {
  candidateIndex: number;
  recordId: string;
  action: DedupDecision["action"];
  targetIds: string[];
  content: string;
  type: MemoryType;
  priority: number;
  sceneName: string;
  sourceMessageIds: string[];
  metadata: ExtractedMemory["metadata"];
}

export interface FinalDraftReviewInput {
  draft: Readonly<FinalMemoryDraft>;
  /** Complete ordered message window used by extraction, not candidate citation order. */
  evidenceWindow: readonly ConversationMessage[];
  strategy: "single_structured" | "independent_behavior_verifier";
}

export interface FinalDraftBatchReviewInput {
  drafts: ReadonlyArray<Readonly<FinalMemoryDraft>>;
  evidenceWindow: readonly ConversationMessage[];
  strategy: FinalDraftReviewInput["strategy"];
}

export interface FinalDraftReviewer {
  review(input: FinalDraftReviewInput): Promise<ScopeAssessmentV1>;
  /** Preferred runtime path: at most one extra semantic call per extraction batch. */
  reviewBatch?(input: FinalDraftBatchReviewInput): Promise<Array<{
    recordId: string;
    assessment: ScopeAssessmentV1;
  }>>;
}

export interface FinalDraftAdmissionDecision {
  candidateIndex: number;
  recordId: string;
  draftFingerprint: string;
  disposition: "retain" | "quarantine" | "deferred" | "skip";
  reasonCodes: string[];
  draft: FinalMemoryDraft;
  assessment: ScopeAssessmentV1 | null;
}

export const SCOPE_ASSESSMENT_V1_SCHEMA: Record<string, unknown> = {
  type: "object",
  additionalProperties: false,
  required: ["applicability", "contentSupport", "adoption", "scope", "evidence"],
  properties: {
    applicability: { type: "string", enum: ["behavior_rule", "not_applicable", "unknown"] },
    contentSupport: { type: "string", enum: ["supported", "refuted", "unknown"] },
    adoption: { type: "string", enum: ["established", "not_established", "unknown"] },
    scope: {
      type: "object", additionalProperties: false,
      required: ["subject", "condition", "horizon", "validFrom", "validUntil"],
      properties: {
        subject: { type: ["string", "null"] },
        condition: { type: ["string", "null"] },
        horizon: { type: "string", enum: ["cross_task", "task", "session", "unknown"] },
        validFrom: { type: ["string", "null"] },
        validUntil: { type: ["string", "null"] },
      },
    },
    evidence: {
      type: "array",
      items: {
        type: "object", additionalProperties: false,
        required: ["messageId", "excerpt", "supports"],
        properties: {
          messageId: { type: "string" }, excerpt: { type: "string" },
          supports: { type: "string", enum: ["content", "scope", "adoption", "counterevidence"] },
        },
      },
    },
  },
};

const SCOPE_ASSESSMENT_BATCH_V1_SCHEMA: Record<string, unknown> = {
  type: "object", additionalProperties: false, required: ["assessments"],
  properties: {
    assessments: {
      type: "array",
      items: {
        type: "object", additionalProperties: false, required: ["recordId", "assessment"],
        properties: { recordId: { type: "string" }, assessment: SCOPE_ASSESSMENT_V1_SCHEMA },
      },
    },
  },
};

const ASSESSMENT_SYSTEM_PROMPT = `Assess whether the exact final memory draft is supported by the ordered source window.
Separate three questions: whether the draft content is supported, whether a behavioral rule was adopted, and its time/scope horizon.
A temporary fact may be worth preserving but must not become a cross-task behavior rule. A prohibition can be a valid rule.
Use only exact excerpts from the supplied messages. If evidence is incomplete or conflicting, use unknown. Do not infer authority from assistant text.`;

function parseScopeAssessment(raw: string): ScopeAssessmentV1 {
  const cleaned = raw.trim().replace(/^```(?:json)?\s*/iu, "").replace(/\s*```$/u, "");
  const value = JSON.parse(cleaned) as ScopeAssessmentV1;
  if (!value || typeof value !== "object" || !Array.isArray(value.evidence)
    || !value.scope || typeof value.scope !== "object") {
    throw new Error("invalid_scope_assessment_shape");
  }
  const applicability = ["behavior_rule", "not_applicable", "unknown"];
  const support = ["supported", "refuted", "unknown"];
  const adoption = ["established", "not_established", "unknown"];
  const horizons = ["cross_task", "task", "session", "unknown"];
  if (!applicability.includes(value.applicability) || !support.includes(value.contentSupport)
    || !adoption.includes(value.adoption) || !horizons.includes(value.scope.horizon)) {
    throw new Error("invalid_scope_assessment_enum");
  }
  return value;
}

/** Create an S/D-compatible reviewer; D receives no first-pass rationale. */
export function createLlmFinalDraftReviewer(llmRunner: LLMRunner): FinalDraftReviewer {
  return {
    async review(input): Promise<ScopeAssessmentV1> {
      const raw = await llmRunner.run({
        taskId: input.strategy === "independent_behavior_verifier"
          ? "l1-final-draft-independent-review"
          : "l1-final-draft-structured-review",
        systemPrompt: ASSESSMENT_SYSTEM_PROMPT,
        prompt: JSON.stringify({
          strategy: input.strategy,
          finalDraft: input.draft,
          orderedEvidenceWindow: input.evidenceWindow.map((message, index) => ({
            order: index, id: message.id, role: message.role, content: message.content,
          })),
        }),
        outputSchema: SCOPE_ASSESSMENT_V1_SCHEMA,
        outputSchemaName: "scope_assessment_v1",
        maxTokens: 1200,
      });
      return parseScopeAssessment(raw);
    },
    async reviewBatch(input) {
      const raw = await llmRunner.run({
        taskId: input.strategy === "independent_behavior_verifier"
          ? "l1-final-draft-independent-review-batch"
          : "l1-final-draft-structured-review-batch",
        systemPrompt: ASSESSMENT_SYSTEM_PROMPT,
        prompt: JSON.stringify({
          strategy: input.strategy,
          finalDrafts: input.drafts,
          orderedEvidenceWindow: input.evidenceWindow.map((message, index) => ({
            order: index, id: message.id, role: message.role, content: message.content,
          })),
        }),
        outputSchema: SCOPE_ASSESSMENT_BATCH_V1_SCHEMA,
        outputSchemaName: "scope_assessment_batch_v1",
        maxTokens: Math.max(1200, input.drafts.length * 900),
      });
      const parsed = JSON.parse(raw) as { assessments?: Array<{ recordId: string; assessment: unknown }> };
      if (!Array.isArray(parsed.assessments)) throw new Error("invalid_scope_assessment_batch_shape");
      return parsed.assessments.map((row) => ({
        recordId: row.recordId,
        assessment: parseScopeAssessment(JSON.stringify(row.assessment)),
      }));
    },
  };
}

function finalValue<T>(merged: T | undefined, original: T): T {
  return merged ?? original;
}

export function buildFinalMemoryDrafts(input: {
  memories: ReadonlyArray<ExtractedMemory & { record_id: string }>;
  decisions: readonly DedupDecision[];
}): FinalMemoryDraft[] {
  const byId = new Map(input.decisions.map((decision) => [decision.record_id, decision]));
  return input.memories.map((memory, candidateIndex) => {
    const decision = byId.get(memory.record_id) ?? {
      record_id: memory.record_id,
      action: "store" as const,
      target_ids: [],
    };
    return {
      candidateIndex,
      recordId: memory.record_id,
      action: decision.action,
      targetIds: [...decision.target_ids],
      content: finalValue(decision.merged_content, memory.content),
      type: finalValue(decision.merged_type, memory.type),
      priority: finalValue(decision.merged_priority, memory.priority),
      sceneName: memory.scene_name,
      sourceMessageIds: [...memory.source_message_ids],
      metadata: structuredClone(memory.metadata),
    };
  });
}

export function fingerprintFinalMemoryDraft(draft: FinalMemoryDraft): string {
  return crypto.createHash("sha256").update(JSON.stringify({
    recordId: draft.recordId,
    action: draft.action,
    targetIds: draft.targetIds,
    content: draft.content,
    type: draft.type,
    priority: draft.priority,
    sceneName: draft.sceneName,
    sourceMessageIds: draft.sourceMessageIds,
    metadata: draft.metadata,
  })).digest("hex");
}

function validateAssessment(
  draft: FinalMemoryDraft,
  assessment: ScopeAssessmentV1,
  evidenceWindow: readonly ConversationMessage[],
): string[] {
  const reasons: string[] = [];
  const byId = new Map(evidenceWindow.map((message) => [message.id, message]));
  if (draft.sourceMessageIds.length === 0) reasons.push("missing_source_message_ids");
  if (draft.sourceMessageIds.some((id) => !byId.has(id))) reasons.push("source_message_outside_review_window");

  const validEvidence = assessment.evidence.filter((item) => {
    const message = byId.get(item.messageId);
    return Boolean(message && item.excerpt.length > 0 && message.content.includes(item.excerpt));
  });
  if (validEvidence.length !== assessment.evidence.length) reasons.push("invalid_evidence_reference");
  if (!validEvidence.some((item) => item.supports === "content")) reasons.push("missing_content_evidence");
  if (assessment.contentSupport !== "supported") reasons.push(`content_${assessment.contentSupport}`);

  if (assessment.applicability === "unknown") reasons.push("applicability_unknown");
  if (assessment.applicability === "behavior_rule") {
    if (assessment.adoption !== "established") reasons.push(`adoption_${assessment.adoption}`);
    if (assessment.scope.horizon !== "cross_task") reasons.push(`scope_${assessment.scope.horizon}`);
    if (!validEvidence.some((item) => item.supports === "scope")) reasons.push("missing_scope_evidence");
    const adoptionEvidence = validEvidence.filter((item) => item.supports === "adoption");
    if (adoptionEvidence.length === 0) reasons.push("missing_adoption_evidence");
    if (adoptionEvidence.some((item) => byId.get(item.messageId)?.role !== "user")) {
      reasons.push("adoption_not_user_grounded");
    }
  }
  return [...new Set(reasons)];
}

/**
 * Review the exact post-dedup draft. This first slice only activates new stores;
 * update/merge remain deferred so an unreviewed rewrite cannot replace old data.
 * Reviewer failures are converted to quarantine decisions rather than thrown.
 */
export async function reviewFinalMemoryDrafts(input: {
  drafts: readonly FinalMemoryDraft[];
  evidenceWindow: readonly ConversationMessage[];
  reviewer: FinalDraftReviewer;
  strategy: FinalDraftReviewInput["strategy"];
}): Promise<FinalDraftAdmissionDecision[]> {
  const orderedWindow = [...input.evidenceWindow];
  const results: FinalDraftAdmissionDecision[] = [];
  const actionable = input.drafts.filter((draft) => draft.action === "store");
  let batchAssessments: Map<string, ScopeAssessmentV1> | null = null;
  let batchFailed = false;
  if (input.reviewer.reviewBatch && actionable.length > 0) {
    try {
      const rows = await input.reviewer.reviewBatch({
        drafts: actionable.map((draft) => Object.freeze(structuredClone(draft))),
        evidenceWindow: orderedWindow.map((message) => Object.freeze(structuredClone(message))),
        strategy: input.strategy,
      });
      const counts = new Map<string, number>();
      for (const row of rows) counts.set(row.recordId, (counts.get(row.recordId) ?? 0) + 1);
      batchAssessments = new Map(rows
        .filter((row) => counts.get(row.recordId) === 1)
        .map((row) => [row.recordId, row.assessment]));
    } catch {
      batchFailed = true;
    }
  }
  for (const original of input.drafts) {
    const draft = structuredClone(original);
    const fingerprint = fingerprintFinalMemoryDraft(draft);
    if (draft.action === "skip") {
      results.push({ candidateIndex: draft.candidateIndex, recordId: draft.recordId, draftFingerprint: fingerprint,
        disposition: "skip", reasonCodes: ["dedup_skip"], draft, assessment: null });
      continue;
    }
    if (draft.action === "update" || draft.action === "merge") {
      results.push({ candidateIndex: draft.candidateIndex, recordId: draft.recordId, draftFingerprint: fingerprint,
        disposition: "deferred", reasonCodes: ["complex_rewrite_deferred_v1"], draft, assessment: null });
      continue;
    }
    try {
      if (batchFailed) throw new Error("reviewer_batch_error");
      const assessment = batchAssessments
        ? batchAssessments.get(draft.recordId)
        : await input.reviewer.review({
          draft: Object.freeze(structuredClone(draft)),
          evidenceWindow: orderedWindow.map((message) => Object.freeze(structuredClone(message))),
          strategy: input.strategy,
        });
      if (!assessment) throw new Error("reviewer_batch_missing_record");
      const reasonCodes = validateAssessment(draft, assessment, orderedWindow);
      results.push({
        candidateIndex: draft.candidateIndex,
        recordId: draft.recordId,
        draftFingerprint: fingerprint,
        disposition: reasonCodes.length === 0 ? "retain" : "quarantine",
        reasonCodes: reasonCodes.length === 0 ? ["final_draft_supported"] : reasonCodes,
        draft,
        assessment: structuredClone(assessment),
      });
    } catch {
      results.push({ candidateIndex: draft.candidateIndex, recordId: draft.recordId, draftFingerprint: fingerprint,
        disposition: "quarantine", reasonCodes: ["reviewer_error"], draft, assessment: null });
    }
  }
  return results;
}

export function gateDedupDecisions(
  decisions: readonly DedupDecision[],
  admissions: readonly FinalDraftAdmissionDecision[],
): DedupDecision[] {
  const decisionById = new Map(decisions.map((decision) => [decision.record_id, decision]));
  // Admissions, not the possibly incomplete model dedup output, are the fixed
  // denominator. This prevents applyDecisions() from default-storing a reviewed
  // candidate whose dedup decision was omitted.
  return admissions.map((admission) => {
    const decision = decisionById.get(admission.recordId) ?? {
      record_id: admission.recordId, action: "store" as const, target_ids: [],
    };
    return admission.disposition === "retain" || admission.disposition === "skip"
      ? structuredClone(decision)
      : { record_id: admission.recordId, action: "skip", target_ids: [] };
  });
}
