import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { L1SearchResult } from "../store/types.js";
import {
  assertShadowCaptureEvent,
  captureEventIntegrityDigest,
  type MemoryCaptureScope,
  type VersionedMemoryRecord,
} from "./capture-contracts.js";

const RECALL_TRUNCATION_SUFFIX = "…（已截断；可用 tdai_memory_search 或 tdai_conversation_search 查看详情）";
const MIN_TRUNCATED_RECALL_LINE_CHARS = 40;
const RECALL_LINE_SEPARATOR = "\n";

export type RecallRetrievalStage = "l1_keyword" | "l1_embedding" | "l1_hybrid";

/**
 * A selected search result before the prompt character budget is applied.
 * The persisted row travels with its rendered representation so identity is
 * never reconstructed from prompt text.
 */
export interface StructuredRecallCandidate {
  row: L1SearchResult;
  retrievalRank: number;
  score: number;
  stage: RecallRetrievalStage;
  renderedText: string;
}

export type RecallNotExposedReason =
  | "budget_pruned"
  | "prompt_not_acknowledged"
  | "prompt_mismatch";

/** A candidate after budgeting, including candidates that were pruned. */
export interface BudgetedRecallCandidate extends StructuredRecallCandidate {
  promptRank: number | null;
  budgetedText: string | null;
  truncated: boolean;
  notExposedReason: "budget_pruned" | null;
}

export interface RecallBudgetLimits {
  maxCharsPerMemory?: number;
  maxTotalRecallChars?: number;
}

export interface RecallSearchFacts {
  strategy: "keyword" | "embedding" | "hybrid" | "skipped";
  status: "completed" | "skipped" | "failed";
  failureCode: string | null;
  queryEligible: boolean;
  configuredMaxResults: number;
  configuredScoreThreshold: number;
  rawCandidateCount: number;
  scoreFilteredCount: number;
  rankPrunedCount: number;
  selectedCandidateCount: number;
  smallCorpusThresholdBypass: boolean;
}

export interface RecallShadowDraft {
  schemaVersion: "tdai-recall-shadow-draft.v1";
  traceId: string;
  capturedAt: string;
  sessionKey: string;
  sessionId: string | null;
  taskRunId: string | null;
  actorId: string;
  queryHash: string;
  expectedPrependContextHash: string | null;
  search: RecallSearchFacts;
  budget: {
    maxCharsPerMemory: number | null;
    maxTotalRecallChars: number | null;
  };
  candidates: BudgetedRecallCandidate[];
}

export interface RecallShadowCandidateObservation {
  recordId: string;
  logicalId: string | null;
  version: number;
  persistenceReceiptHash: string | null;
  recordDigest: string | null;
  identityAuthorityEventId: string | null;
  identityAuthorityEventHash: string | null;
  exactIdentityReady: boolean;
  identityReasonCodes: string[];
  contentHash: string;
  metadataHash: string;
  scopeHash: string;
  entityBindingHash: string;
  retrievalStage: RecallRetrievalStage;
  retrievalRank: number;
  promptRank: number | null;
  score: number;
  highestObservedState: "retrieved" | "exposed";
  exposed: boolean;
  /** This adapter never infers use from injection or task outcome. */
  used: false;
  preparedRenderedHash: string | null;
  preparedRenderedChars: number;
  renderedHash: string | null;
  renderedChars: number;
  truncated: boolean;
  notExposedReason: RecallNotExposedReason | null;
}

export interface RecallShadowObservation {
  schemaVersion: "tdai-recall-shadow-observation.v1";
  eventType: "recall_exposure_observation";
  eventId: string;
  eventHash: string;
  capturedAt: string;
  exposureObservedAt: string;
  traceId: string;
  sessionKey: string;
  sessionId: string | null;
  taskRunId: string | null;
  actorId: string;
  queryHash: string;
  observedPrependContextHash: string | null;
  promptAssemblyEvidence: "exact_context_acknowledged" | "not_acknowledged" | "context_mismatch";
  search: RecallSearchFacts;
  budget: RecallShadowDraft["budget"];
  candidates: RecallShadowCandidateObservation[];
  noMatch: {
    /** What the production retrieval path did; not a correctness label. */
    systemDecision: "inject_candidates" | "inject_none" | "skip_query" | "retrieval_failed";
    expectedMatch: "unknown";
    decision: "abstain";
    reasonCodes: string[];
  };
  warnings: string[];
  dataClassification: "shadow_telemetry";
  feedbackDepth: 0;
  memoryIngestionAllowed: false;
  mayWriteProductionMemory: false;
  mayEnqueueFeedback: false;
  feedbackReingestionEnabled: false;
  optimizationReady: false;
}

export interface RecallShadowObserver {
  append(event: RecallShadowObservation): void | Promise<void>;
}

/**
 * Trusted-side input for joining retrieval rows to immutable capture records.
 * A digest-shaped value embedded in mutable row metadata is only a claim; the
 * full event is revalidated before it can establish exact identity.
 */
export interface RecallIdentityAuthorityInput {
  records: readonly VersionedMemoryRecord[];
}

export interface RecallShadowLogger {
  warn?: (message: string) => void;
}

function hash(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? "null";
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(",")}]`;
  const row = value as Record<string, unknown>;
  return `{${Object.keys(row).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(row[key])}`).join(",")}}`;
}

function canonicalHash(value: unknown): string {
  return hash(canonicalize(value));
}

function deepFreeze<T>(value: T, seen = new Set<object>()): T {
  if (!value || typeof value !== "object" || seen.has(value as object)) return value;
  seen.add(value as object);
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function positiveLimit(value: number | undefined): number | undefined {
  if (value == null || !Number.isFinite(value) || value <= 0) return undefined;
  return Math.floor(value);
}

function truncateRecallLine(line: string, maxChars: number): string {
  const codePoints = Array.from(line);
  if (codePoints.length <= maxChars) return line;
  if (maxChars <= RECALL_TRUNCATION_SUFFIX.length) {
    return codePoints.slice(0, maxChars).join("");
  }
  return `${codePoints.slice(0, maxChars - RECALL_TRUNCATION_SUFFIX.length).join("").trimEnd()}${RECALL_TRUNCATION_SUFFIX}`;
}

/**
 * Applies the existing prompt budget without dropping candidate identity.
 * Output contains one row per input candidate, including budget-pruned rows.
 */
export function applyStructuredRecallBudget(
  candidates: StructuredRecallCandidate[],
  limits: RecallBudgetLimits,
): BudgetedRecallCandidate[] {
  const maxCharsPerMemory = positiveLimit(limits.maxCharsPerMemory);
  const maxTotalRecallChars = positiveLimit(limits.maxTotalRecallChars);
  let usedChars = 0;
  let promptRank = 0;
  let exhausted = false;

  return candidates.map((candidate) => {
    if (exhausted) {
      return {
        ...candidate,
        promptRank: null,
        budgetedText: null,
        truncated: false,
        notExposedReason: "budget_pruned" as const,
      };
    }

    const perMemoryBounded = maxCharsPerMemory
      ? truncateRecallLine(candidate.renderedText, maxCharsPerMemory)
      : candidate.renderedText;
    let budgetedText = perMemoryBounded;
    let truncated = perMemoryBounded !== candidate.renderedText;

    if (maxTotalRecallChars) {
      const separatorChars = promptRank > 0 ? RECALL_LINE_SEPARATOR.length : 0;
      const remainingChars = maxTotalRecallChars - usedChars - separatorChars;
      if (remainingChars <= 0) {
        exhausted = true;
        return {
          ...candidate,
          promptRank: null,
          budgetedText: null,
          truncated: false,
          notExposedReason: "budget_pruned" as const,
        };
      }
      if (budgetedText.length > remainingChars) {
        if (remainingChars < MIN_TRUNCATED_RECALL_LINE_CHARS) {
          exhausted = true;
          return {
            ...candidate,
            promptRank: null,
            budgetedText: null,
            truncated: false,
            notExposedReason: "budget_pruned" as const,
          };
        }
        budgetedText = truncateRecallLine(budgetedText, remainingChars);
        truncated ||= budgetedText !== perMemoryBounded;
        exhausted = true;
      }
      usedChars += separatorChars + budgetedText.length;
    }

    promptRank += 1;
    return {
      ...candidate,
      promptRank,
      budgetedText,
      truncated,
      notExposedReason: null,
    };
  });
}

function parseIdentityMetadata(metadataJson: string): {
  logicalId: string | null;
  claimedPersistenceReceiptHash: string | null;
  persistenceReceiptClaimPresent: boolean;
  canonicalMetadataHash: string | null;
  projectId: string | null;
  entityBindings: Record<string, string>;
  warnings: string[];
} {
  if (!metadataJson.trim()) {
    return {
      logicalId: null,
      claimedPersistenceReceiptHash: null,
      persistenceReceiptClaimPresent: false,
      canonicalMetadataHash: null,
      projectId: null,
      entityBindings: {},
      warnings: [],
    };
  }
  try {
    const metadata = JSON.parse(metadataJson) as unknown;
    if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
      return {
        logicalId: null,
        claimedPersistenceReceiptHash: null,
        persistenceReceiptClaimPresent: false,
        canonicalMetadataHash: null,
        projectId: null,
        entityBindings: {},
        warnings: ["invalid_metadata_shape"],
      };
    }
    const metadataRow = metadata as Record<string, unknown>;
    const canonicalMetadataHash = canonicalHash(metadataRow);
    const provenance = metadataRow._tdai_provenance;
    if (!provenance || typeof provenance !== "object" || Array.isArray(provenance)) {
      return {
        logicalId: null,
        claimedPersistenceReceiptHash: null,
        persistenceReceiptClaimPresent: false,
        canonicalMetadataHash,
        projectId: null,
        entityBindings: {},
        warnings: [],
      };
    }
    const provenanceRow = provenance as Record<string, unknown>;
    const value = provenanceRow.logicalId;
    const rawReceipt = provenanceRow.persistenceReceiptHash;
    const rawProjectId = provenanceRow.projectId;
    const rawBindings = provenanceRow.entityBindings;
    const claimedPersistenceReceiptHash = typeof rawReceipt === "string" && /^[a-f0-9]{64}$/i.test(rawReceipt)
      ? rawReceipt
      : null;
    const entityBindings = rawBindings && typeof rawBindings === "object" && !Array.isArray(rawBindings)
      ? Object.fromEntries(Object.entries(rawBindings).filter(
        (entry): entry is [string, string] => Boolean(entry[0].trim())
          && typeof entry[1] === "string"
          && Boolean(entry[1].trim()),
      ))
      : {};
    return {
      logicalId: typeof value === "string" && Boolean(value.trim()) ? value : null,
      claimedPersistenceReceiptHash,
      persistenceReceiptClaimPresent: rawReceipt !== undefined,
      canonicalMetadataHash,
      projectId: typeof rawProjectId === "string" && Boolean(rawProjectId.trim()) ? rawProjectId : null,
      entityBindings,
      warnings: rawReceipt !== undefined && claimedPersistenceReceiptHash === null
        ? ["invalid_persistence_receipt_hash"]
        : [],
    };
  } catch {
    return {
      logicalId: null,
      claimedPersistenceReceiptHash: null,
      persistenceReceiptClaimPresent: false,
      canonicalMetadataHash: null,
      projectId: null,
      entityBindings: {},
      warnings: ["invalid_metadata_json"],
    };
  }
}

interface IndexedRecallIdentityAuthority {
  event: VersionedMemoryRecord;
  fingerprint: string;
}

interface RecallIdentityAuthorityIndex {
  records: Map<string, IndexedRecallIdentityAuthority>;
  conflicts: Set<string>;
  invalid: Set<string>;
  unkeyedInvalid: boolean;
}

function recallRecordKey(recordId: string, version: number): string {
  return `${recordId}\u001f${version}`;
}

function nonEmptyOrNull(value: string): string | null {
  return value.trim() ? value : null;
}

function observedRecallScope(row: L1SearchResult, projectId: string | null): MemoryCaptureScope {
  return {
    teamId: nonEmptyOrNull(row.team_id),
    userId: nonEmptyOrNull(row.user_id),
    agentId: nonEmptyOrNull(row.agent_id),
    sessionKey: nonEmptyOrNull(row.session_key),
    sessionId: nonEmptyOrNull(row.session_id),
    taskId: nonEmptyOrNull(row.task_id),
    projectId,
    sceneName: nonEmptyOrNull(row.scene_name),
  };
}

function unsafeAuthorityKey(event: unknown): string | null {
  if (!event || typeof event !== "object") return null;
  const payload = (event as { payload?: unknown }).payload;
  if (!payload || typeof payload !== "object") return null;
  const record = (payload as { record?: unknown }).record;
  if (!record || typeof record !== "object") return null;
  const { layer, id, version } = record as { layer?: unknown; id?: unknown; version?: unknown };
  if (layer !== "L1" || typeof id !== "string" || !id.trim() || !Number.isSafeInteger(version)) return null;
  return recallRecordKey(id, version as number);
}

function indexRecallIdentityAuthorities(
  input: RecallIdentityAuthorityInput | undefined,
): RecallIdentityAuthorityIndex {
  const index: RecallIdentityAuthorityIndex = {
    records: new Map(),
    conflicts: new Set(),
    invalid: new Set(),
    unkeyedInvalid: false,
  };
  for (const event of input?.records ?? []) {
    const unsafeKey = unsafeAuthorityKey(event);
    try {
      assertShadowCaptureEvent(event);
      if (event.eventType !== "versioned_memory_record" || event.payload.record.layer !== "L1") {
        if (unsafeKey) index.invalid.add(unsafeKey);
        else index.unkeyedInvalid = true;
        continue;
      }
      const key = recallRecordKey(event.payload.record.id, event.payload.record.version);
      const fingerprint = canonicalHash({
        record: event.payload.record,
        logicalId: event.payload.logicalId,
        contentHash: event.payload.contentHash,
        persistenceReceiptHash: event.payload.persistenceReceiptHash,
        recordDigest: captureEventIntegrityDigest(event),
      });
      const existing = index.records.get(key);
      if (existing && existing.fingerprint !== fingerprint) {
        index.conflicts.add(key);
        index.records.delete(key);
      } else if (!existing && !index.conflicts.has(key)) {
        index.records.set(key, { event, fingerprint });
      }
    } catch {
      if (unsafeKey) index.invalid.add(unsafeKey);
      else index.unkeyedInvalid = true;
    }
  }
  return index;
}

export function createRecallShadowDraft(input: {
  traceId: string;
  capturedAt: string;
  sessionKey: string;
  sessionId?: string | null;
  taskRunId?: string | null;
  actorId: string;
  query: string;
  expectedPrependContext?: string;
  search: RecallSearchFacts;
  limits: RecallBudgetLimits;
  candidates: BudgetedRecallCandidate[];
}): RecallShadowDraft {
  if (!input.traceId.trim()) throw new Error("traceId is required");
  if (!input.sessionKey.trim()) throw new Error("sessionKey is required");
  if (!Number.isFinite(Date.parse(input.capturedAt))) throw new Error("capturedAt must be an ISO-compatible timestamp");
  if (input.candidates.some((candidate, index) => candidate.retrievalRank !== index + 1)) {
    throw new Error("Recall candidate retrieval ranks must be contiguous and ordered");
  }
  return deepFreeze({
    schemaVersion: "tdai-recall-shadow-draft.v1" as const,
    traceId: input.traceId,
    capturedAt: input.capturedAt,
    sessionKey: input.sessionKey,
    sessionId: input.sessionId ?? null,
    taskRunId: input.taskRunId ?? null,
    actorId: input.actorId,
    queryHash: hash(input.query),
    expectedPrependContextHash: input.expectedPrependContext ? hash(input.expectedPrependContext) : null,
    search: structuredClone(input.search),
    budget: {
      maxCharsPerMemory: positiveLimit(input.limits.maxCharsPerMemory) ?? null,
      maxTotalRecallChars: positiveLimit(input.limits.maxTotalRecallChars) ?? null,
    },
    candidates: structuredClone(input.candidates),
  });
}

/**
 * Finalizes a two-phase trace. `actualPrependContext` must be supplied only at
 * a host point that can attest the exact generated context was assembled. If it
 * is missing or differs, candidates remain retrieved; they are never upgraded
 * optimistically to exposed.
 */
export function finalizeRecallShadowObservation(
  draft: RecallShadowDraft,
  exposureObservedAt: string,
  actualPrependContext?: string,
  identityAuthority?: RecallIdentityAuthorityInput,
): RecallShadowObservation {
  if (!Number.isFinite(Date.parse(exposureObservedAt))) {
    throw new Error("exposureObservedAt must be an ISO-compatible timestamp");
  }
  const observedHash = actualPrependContext ? hash(actualPrependContext) : null;
  const acknowledged = draft.expectedPrependContextHash !== null
    && observedHash === draft.expectedPrependContextHash;
  const promptAssemblyEvidence = actualPrependContext === undefined
    ? "not_acknowledged" as const
    : acknowledged
      ? "exact_context_acknowledged" as const
      : "context_mismatch" as const;
  const warnings = new Set<string>();
  const authorityIndex = indexRecallIdentityAuthorities(identityAuthority);
  if (authorityIndex.unkeyedInvalid) warnings.add("invalid_unkeyed_identity_authority");

  const candidates = draft.candidates.map((candidate): RecallShadowCandidateObservation => {
    const parsed = parseIdentityMetadata(candidate.row.metadata_json);
    parsed.warnings.forEach((warning) => warnings.add(`${warning}:${candidate.row.record_id}`));
    const candidateContentHash = canonicalHash(candidate.row.content);
    const candidateMetadataHash = parsed.canonicalMetadataHash ?? hash(candidate.row.metadata_json);
    const candidateScopeHash = canonicalHash(observedRecallScope(candidate.row, parsed.projectId));
    const candidateEntityBindingHash = canonicalHash(parsed.entityBindings);
    const identityReasonCodes: string[] = [];
    if (!candidate.row.record_id.trim()) identityReasonCodes.push("missing_record_id");
    if (!Number.isSafeInteger(candidate.row.version) || candidate.row.version < 1) {
      identityReasonCodes.push("unresolved_version");
    }
    const key = recallRecordKey(candidate.row.record_id, candidate.row.version);
    const indexedAuthority = authorityIndex.records.get(key);
    let logicalId = parsed.logicalId;
    let persistenceReceiptHash: string | null = null;
    let recordDigest: string | null = null;
    let identityAuthorityEventId: string | null = null;
    let identityAuthorityEventHash: string | null = null;

    if (authorityIndex.invalid.has(key) || authorityIndex.unkeyedInvalid) {
      identityReasonCodes.push("invalid_identity_authority");
    } else if (authorityIndex.conflicts.has(key)) {
      identityReasonCodes.push("conflicting_identity_authority");
    } else if (!indexedAuthority) {
      identityReasonCodes.push("missing_identity_authority");
      if (parsed.claimedPersistenceReceiptHash) {
        identityReasonCodes.push("unverified_metadata_persistence_receipt");
      }
    } else {
      const authority = indexedAuthority.event;
      if (parsed.logicalId && parsed.logicalId !== authority.payload.logicalId) {
        identityReasonCodes.push("identity_authority_logical_id_mismatch");
      }
      if (candidateContentHash !== authority.payload.contentHash) {
        identityReasonCodes.push("identity_authority_content_hash_mismatch");
      }
      if (parsed.canonicalMetadataHash !== authority.payload.metadataHash) {
        identityReasonCodes.push("identity_authority_metadata_hash_mismatch");
      }
      if (candidateScopeHash !== authority.payload.scopeHash) {
        identityReasonCodes.push("identity_authority_scope_hash_mismatch");
      }
      if (candidateEntityBindingHash !== authority.payload.entityBindingHash) {
        identityReasonCodes.push("identity_authority_entity_binding_hash_mismatch");
      }
      if (
        parsed.persistenceReceiptClaimPresent
        && parsed.claimedPersistenceReceiptHash !== authority.payload.persistenceReceiptHash
      ) {
        identityReasonCodes.push("identity_authority_receipt_mismatch");
      }
      if (identityReasonCodes.length === 0) {
        logicalId = authority.payload.logicalId;
        persistenceReceiptHash = authority.payload.persistenceReceiptHash;
        recordDigest = authority.payload.recordDigest;
        identityAuthorityEventId = authority.eventId;
        identityAuthorityEventHash = authority.eventHash;
      }
    }
    if (!logicalId) identityReasonCodes.push("missing_logical_id");
    const exposed = candidate.budgetedText !== null && acknowledged;
    const notExposedReason: RecallNotExposedReason | null = exposed
      ? null
      : candidate.notExposedReason
        ?? (actualPrependContext === undefined ? "prompt_not_acknowledged" : "prompt_mismatch");
    return {
      recordId: candidate.row.record_id,
      logicalId,
      version: candidate.row.version,
      persistenceReceiptHash,
      recordDigest,
      identityAuthorityEventId,
      identityAuthorityEventHash,
      exactIdentityReady: identityReasonCodes.length === 0,
      identityReasonCodes,
      contentHash: candidateContentHash,
      metadataHash: candidateMetadataHash,
      scopeHash: candidateScopeHash,
      entityBindingHash: candidateEntityBindingHash,
      retrievalStage: candidate.stage,
      retrievalRank: candidate.retrievalRank,
      promptRank: candidate.promptRank,
      score: candidate.score,
      highestObservedState: exposed ? "exposed" : "retrieved",
      exposed,
      used: false,
      preparedRenderedHash: candidate.budgetedText ? hash(candidate.budgetedText) : null,
      preparedRenderedChars: candidate.budgetedText?.length ?? 0,
      renderedHash: exposed && candidate.budgetedText ? hash(candidate.budgetedText) : null,
      renderedChars: exposed && candidate.budgetedText ? candidate.budgetedText.length : 0,
      truncated: candidate.truncated,
      notExposedReason,
    };
  });

  if (draft.taskRunId === null) warnings.add("missing_task_run_id");
  if (draft.sessionId === null) warnings.add("missing_session_id");
  if (promptAssemblyEvidence !== "exact_context_acknowledged" && draft.candidates.some((candidate) => candidate.promptRank !== null)) {
    warnings.add(`prompt_exposure_${promptAssemblyEvidence}`);
  }
  const hasInjectableCandidate = draft.candidates.some(
    (candidate) => candidate.promptRank !== null && candidate.budgetedText !== null,
  );
  const systemDecision = draft.search.status === "failed"
    ? "retrieval_failed" as const
    : !draft.search.queryEligible
    ? "skip_query" as const
    : hasInjectableCandidate
      ? "inject_candidates" as const
      : "inject_none" as const;
  const body = {
    capturedAt: draft.capturedAt,
    exposureObservedAt,
    traceId: draft.traceId,
    sessionKey: draft.sessionKey,
    sessionId: draft.sessionId,
    taskRunId: draft.taskRunId,
    actorId: draft.actorId,
    queryHash: draft.queryHash,
    observedPrependContextHash: observedHash,
    promptAssemblyEvidence,
    search: structuredClone(draft.search),
    budget: structuredClone(draft.budget),
    candidates,
    noMatch: {
      systemDecision,
      expectedMatch: "unknown" as const,
      decision: "abstain" as const,
      reasonCodes: draft.search.status === "failed"
        ? ["retrieval_failed", "independent_relevance_authority_missing"]
        : ["independent_relevance_authority_missing"],
    },
    warnings: [...warnings].sort(),
    dataClassification: "shadow_telemetry" as const,
    feedbackDepth: 0 as const,
    memoryIngestionAllowed: false as const,
    mayWriteProductionMemory: false as const,
    mayEnqueueFeedback: false as const,
    feedbackReingestionEnabled: false as const,
    optimizationReady: false as const,
  };
  const eventHash = canonicalHash(body);
  return deepFreeze({
    schemaVersion: "tdai-recall-shadow-observation.v1" as const,
    eventType: "recall_exposure_observation" as const,
    eventId: `recall-shadow-${eventHash.slice(0, 24)}`,
    eventHash,
    ...body,
  });
}

export function assertRecallShadowObservation(event: RecallShadowObservation): void {
  if (!event || typeof event !== "object") throw new Error("Recall shadow observation must be an object");
  if (event.schemaVersion !== "tdai-recall-shadow-observation.v1" || event.eventType !== "recall_exposure_observation") {
    throw new Error("Unsupported recall shadow observation schema");
  }
  if (
    event.feedbackDepth !== 0
    || event.dataClassification !== "shadow_telemetry"
    || event.memoryIngestionAllowed !== false
    || event.mayWriteProductionMemory !== false
    || event.mayEnqueueFeedback !== false
    || event.feedbackReingestionEnabled !== false
    || event.optimizationReady !== false
  ) {
    throw new Error("Recall observation violates the shadow-only, non-recursive safety contract");
  }
  const { schemaVersion: _schemaVersion, eventType: _eventType, eventId, eventHash, ...body } = event;
  const expectedHash = canonicalHash(body);
  if (eventHash !== expectedHash || eventId !== `recall-shadow-${expectedHash.slice(0, 24)}`) {
    throw new Error("Recall shadow observation integrity mismatch");
  }
  const identities = new Set<string>();
  for (const candidate of event.candidates) {
    const identity = `${candidate.recordId}\u001f${candidate.version}`;
    if (identities.has(identity)) throw new Error(`Duplicate recalled record-version ${identity}`);
    identities.add(identity);
    if (!Number.isSafeInteger(candidate.retrievalRank) || candidate.retrievalRank < 1) {
      throw new Error("Invalid retrieval rank in recall shadow observation");
    }
    if (candidate.used !== false) throw new Error("Recall shadow adapter cannot assert Memory use");
    for (const [field, value] of [
      ["contentHash", candidate.contentHash],
      ["metadataHash", candidate.metadataHash],
      ["scopeHash", candidate.scopeHash],
      ["entityBindingHash", candidate.entityBindingHash],
    ] as const) {
      if (!/^[a-f0-9]{64}$/i.test(value)) {
        throw new Error(`Recall candidate ${field} must be a SHA-256 digest`);
      }
    }
    if (candidate.exactIdentityReady) {
      if (candidate.identityReasonCodes.length > 0) {
        throw new Error("Exact recall identity cannot contain unresolved reason codes");
      }
      if (!candidate.logicalId?.trim() || !Number.isSafeInteger(candidate.version) || candidate.version < 1) {
        throw new Error("Exact recall identity requires logical ID and positive version");
      }
      for (const [field, value] of [
        ["persistenceReceiptHash", candidate.persistenceReceiptHash],
        ["recordDigest", candidate.recordDigest],
        ["identityAuthorityEventHash", candidate.identityAuthorityEventHash],
      ] as const) {
        if (typeof value !== "string" || !/^[a-f0-9]{64}$/i.test(value)) {
          throw new Error(`Exact recall identity requires verified ${field}`);
        }
      }
      if (!candidate.identityAuthorityEventId?.trim()) {
        throw new Error("Exact recall identity requires an authority event ID");
      }
    }
  }
}

/**
 * Optional append-only JSONL observer. Constructing and wiring it is explicit;
 * auto-recall never creates this store by default.
 */
export class JsonlRecallShadowObserver implements RecallShadowObserver {
  readonly filePath: string;
  private readonly identities = new Map<string, string>();

  constructor(rootDirectory: string, fileName = "recall-exposure-observations.v1.jsonl") {
    if (!rootDirectory.trim()) throw new Error("Recall shadow observer root directory is required");
    if (!/^[a-zA-Z0-9._-]+\.jsonl$/.test(fileName)) {
      throw new Error("Recall shadow observer filename must be a plain .jsonl basename");
    }
    mkdirSync(rootDirectory, { recursive: true, mode: 0o700 });
    this.filePath = resolve(rootDirectory, fileName);
    this.load().forEach((event) => this.remember(event));
  }

  append(event: RecallShadowObservation): void {
    assertRecallShadowObservation(event);
    const existing = this.identities.get(event.eventId);
    if (existing === event.eventHash) throw new Error(`Duplicate recall shadow observation ${event.eventId}`);
    if (existing !== undefined) throw new Error(`Conflicting recall shadow observation ${event.eventId}`);
    appendFileSync(this.filePath, `${JSON.stringify(event)}\n`, { encoding: "utf8", mode: 0o600 });
    this.identities.set(event.eventId, event.eventHash);
  }

  readAll(): RecallShadowObservation[] {
    return this.load().map((event) => deepFreeze(structuredClone(event)));
  }

  private remember(event: RecallShadowObservation): void {
    assertRecallShadowObservation(event);
    const existing = this.identities.get(event.eventId);
    if (existing === event.eventHash) throw new Error(`Duplicate recall shadow observation ${event.eventId}`);
    if (existing !== undefined) throw new Error(`Conflicting recall shadow observation ${event.eventId}`);
    this.identities.set(event.eventId, event.eventHash);
  }

  private load(): RecallShadowObservation[] {
    let raw: string;
    try {
      raw = readFileSync(this.filePath, "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
    return raw.split("\n").filter(Boolean).map((line, index) => {
      try {
        const event = JSON.parse(line) as RecallShadowObservation;
        assertRecallShadowObservation(event);
        return event;
      } catch (error) {
        throw new Error(`Malformed recall shadow row ${index + 1}: ${(error as Error).message}`);
      }
    });
  }
}

/**
 * Fire-and-forget fail-open delivery. Observer exceptions are contained and
 * can neither fail nor delay the user task. The adapter has no Memory surface.
 */
export function dispatchRecallShadowObservation(
  observer: RecallShadowObserver | undefined,
  event: RecallShadowObservation,
  logger?: RecallShadowLogger,
): void {
  if (!observer) return;
  setImmediate(() => {
    try {
      Promise.resolve(observer.append(event)).catch((error: unknown) => {
        logger?.warn?.(`[memory-tdai] [shadow-recall] sidecar append failed (ignored): ${error instanceof Error ? error.message : String(error)}`);
      });
    } catch (error) {
      logger?.warn?.(`[memory-tdai] [shadow-recall] sidecar append failed (ignored): ${error instanceof Error ? error.message : String(error)}`);
    }
  });
}
