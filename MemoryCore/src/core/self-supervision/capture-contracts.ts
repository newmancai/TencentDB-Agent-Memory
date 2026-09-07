import type { MemoryLayer, MemoryNodeRef } from "./types.js";
import { canonicalHash } from "./observation-plane.js";

/** JSON-only values keep hashes stable across JSONL sidecars and runtimes. */
export type CaptureJsonValue =
  | null
  | boolean
  | number
  | string
  | CaptureJsonValue[]
  | { [key: string]: CaptureJsonValue };

export type CaptureOrigin = "production_capture" | "benchmark_fixture";

export interface ShadowCaptureContext {
  captureId: string;
  capturedAt: string;
  origin: CaptureOrigin;
  feedbackDepth: 0;
  taskRunId: string | null;
}

interface ShadowCaptureEnvelope {
  schemaVersion: "tdai-shadow-capture.v1";
  eventId: string;
  eventHash: string;
  eventType:
    | "versioned_memory_record"
    | "materialized_l0_authority"
    | "aggregation_manifest"
    | "memory_use_trace";
  captureId: string;
  capturedAt: string;
  origin: CaptureOrigin;
  feedbackDepth: 0;
  taskRunId: string | null;
  dataClassification: "shadow_telemetry";
  memoryIngestionAllowed: false;
  mayWriteProductionMemory: false;
  mayEnqueueFeedback: false;
  feedbackReingestionEnabled: false;
  optimizationReady: false;
}

export interface MemoryCaptureScope {
  teamId: string | null;
  userId: string | null;
  agentId: string | null;
  sessionKey: string | null;
  sessionId: string | null;
  taskId: string | null;
  projectId: string | null;
  sceneName: string | null;
}

export interface ExactL0Ref extends MemoryNodeRef {
  layer: "L0";
  version: 1;
}

export interface ExactL1Ref extends MemoryNodeRef {
  layer: "L1";
}

export interface ExactL2Ref extends MemoryNodeRef {
  layer: "L2";
}

export type ExactPersistedMemoryRef = ExactL1Ref | ExactL2Ref;

export type VersionPredecessor =
  | { relation: "replaces" | "merged_from"; record: ExactL1Ref }
  | { relation: "supersedes"; record: ExactL2Ref };

export interface CapturedMemoryPayload {
  record: ExactPersistedMemoryRef;
  logicalId: string;
  content: string;
  contentHash: string;
  metadata: CaptureJsonValue;
  metadataHash: string;
  scope: MemoryCaptureScope;
  scopeHash: string;
  entityBindings: Record<string, string>;
  entityBindingHash: string;
  sourceL0: ExactL0Ref[];
  predecessors: VersionPredecessor[];
  createdAt: string;
  observedAt: string;
  capturePoint: "l1_write_receipt" | "l2_profile_commit_receipt" | "benchmark_fixture";
  persistenceReceiptHash: string;
  recordDigest: string;
}

/**
 * Immutable snapshot of one persisted L1/L2 version. The snapshot materializes
 * the exact payload; a later row with the same layer/id/version and a different
 * digest is an integrity conflict, not a new version.
 */
export interface VersionedMemoryRecord extends ShadowCaptureEnvelope {
  eventType: "versioned_memory_record";
  payload: CapturedMemoryPayload;
}

export interface VersionedMemoryRecordInput {
  context: ShadowCaptureContext;
  layer: "L1" | "L2";
  recordId: string;
  logicalId: string;
  version: number;
  content: string;
  metadata: CaptureJsonValue;
  scope: MemoryCaptureScope;
  entityBindings: Record<string, string>;
  sourceL0?: ExactL0Ref[];
  predecessors?: VersionPredecessor[];
  createdAt: string;
  observedAt: string;
  capturePoint: CapturedMemoryPayload["capturePoint"];
  persistenceReceiptHash: string;
}

export type PersistedL0Role = "user" | "assistant";
export type L0AuthorityClass = "user_assertion" | "assistant_generated_output";

export interface MaterializedL0Source {
  record: ExactL0Ref;
  role: PersistedL0Role;
  authorityClass: L0AuthorityClass;
  eligibleForUserFactSupport: boolean;
  content: string;
  contentHash: string;
  recordedAt: string;
  scope: MemoryCaptureScope;
  scopeHash: string;
  materializationBasis: "persisted_l0_row" | "benchmark_fixture";
}

export interface SourceSpan {
  /** UTF-16 offsets, matching JavaScript String.slice. */
  start: number;
  end: number;
}

export interface MaterializedL0Assertion {
  assertionId: string;
  claimId: string;
  span: SourceSpan;
  sourceText: string;
  sourceTextHash: string;
  supports: ExactL1Ref[];
  authorityClass: L0AuthorityClass;
  eligibleForUserFactSupport: boolean;
}

/** Role is copied from persisted L0 and authority class is derived, never supplied. */
export interface MaterializedL0Authority extends ShadowCaptureEnvelope {
  eventType: "materialized_l0_authority";
  authorityId: string;
  authorityVersion: 1;
  source: MaterializedL0Source;
  assertions: MaterializedL0Assertion[];
  authorityDigest: string;
}

export interface MaterializedL0AuthorityInput {
  context: ShadowCaptureContext;
  source: {
    recordId: string;
    version: 1;
    role: PersistedL0Role | string;
    content: string;
    recordedAt: string;
    scope: MemoryCaptureScope;
    materializationBasis: MaterializedL0Source["materializationBasis"];
  };
  assertions: Array<{
    assertionId: string;
    claimId: string;
    span: SourceSpan;
    supports: ExactL1Ref[];
  }>;
}

export interface AggregatorIdentity {
  componentId: string;
  componentVersion: string;
  promptId: string;
  promptVersion: string;
  promptHash: string;
  modelId: string;
  modelVersion: string;
  seed: number | null;
}

export interface FrozenAggregationInput {
  record: ExactL1Ref;
  logicalId: string;
  contentHash: string;
  recordDigest: string;
  scopeHash: string;
  entityBindingHash: string;
}

/** Created before L2 generation and embedded unchanged in its manifest. */
export interface FrozenAggregationInputSet {
  schemaVersion: "tdai-frozen-aggregation-inputs.v1";
  aggregationRunId: string;
  frozenAt: string;
  aggregator: AggregatorIdentity;
  inputs: FrozenAggregationInput[];
  inputSetHash: string;
}

export interface FreezeAggregationInputsInput {
  aggregationRunId: string;
  frozenAt: string;
  aggregator: AggregatorIdentity;
  records: VersionedMemoryRecord[];
}

export interface ExactDerivationEdgeSnapshot {
  edgeId: string;
  version: number;
  from: ExactL1Ref;
  to: ExactL2Ref;
  sourceContentHash: string;
  sourceRecordDigest: string;
  claimIds: string[];
  metadataHash: string;
}

export interface AggregatedClaim {
  claimId: string;
  span: SourceSpan;
  text: string;
  textHash: string;
  derivations: Array<{
    edgeId: string;
    edgeVersion: number;
    source: ExactL1Ref;
    sourceContentHash: string;
    sourceRecordDigest: string;
  }>;
  lineageStatus: "attributed" | "unattributed";
}

export interface ClaimCoverage {
  coveredNonWhitespaceChars: number;
  totalNonWhitespaceChars: number;
  complete: boolean;
}

/**
 * Capture-time claim-to-lineage manifest. It records what the aggregator
 * declared it used; it is provenance evidence, not a correctness label.
 */
export interface AggregationManifest extends ShadowCaptureEnvelope {
  eventType: "aggregation_manifest";
  manifestId: string;
  manifestVersion: number;
  aggregationRunId: string;
  frozenInputs: FrozenAggregationInputSet;
  output: {
    record: ExactL2Ref;
    logicalId: string;
    contentHash: string;
    recordDigest: string;
  };
  claims: AggregatedClaim[];
  edges: ExactDerivationEdgeSnapshot[];
  claimCoverage: ClaimCoverage;
  aggregationCompletedAt: string;
  manifestDigest: string;
}

export interface AggregationManifestInput {
  context: ShadowCaptureContext;
  manifestId: string;
  manifestVersion: number;
  frozenInputs: FrozenAggregationInputSet;
  output: VersionedMemoryRecord;
  aggregationCompletedAt: string;
  claims: Array<{
    claimId: string;
    span: SourceSpan;
    sources: Array<{
      edgeId: string;
      edgeVersion: number;
      source: ExactL1Ref;
    }>;
  }>;
}

export type RetrievalStage =
  | "l1_keyword"
  | "l1_embedding"
  | "l1_hybrid"
  | "l2_scene_index"
  | "l2_file_read"
  | "memory_tool";

export type CaptureExposureChannel = "prompt_l1" | "system_l2_navigation" | "l2_file_read";
export type ExposureRepresentation =
  | "l1_rendered_line"
  | "l2_navigation_summary"
  | "l2_full_content"
  | "tool_result_snippet";

export type NotExposedReason =
  | "budget_pruned"
  | "score_filtered"
  | "not_selected"
  | "retrieval_only";

export type UseEvidenceBasis =
  | "explicit_citation"
  | "tool_argument_dependency"
  | "deterministic_dataflow";

export interface MemoryUseEvidence {
  basis: UseEvidenceBasis;
  evidenceId: string;
  evidenceHash: string;
}

export interface CapturedMemoryAccess {
  accessId: string;
  node: ExactPersistedMemoryRef;
  recordDigest: string;
  retrieval: {
    retrievalId: string;
    retrievedAt: string;
    stage: RetrievalStage;
    queryHash: string;
    rank: number | null;
    score: number | null;
  };
  exposure: null | {
    exposureId: string;
    exposedAt: string;
    channel: CaptureExposureChannel;
    representation: ExposureRepresentation;
    renderedHash: string;
    renderedChars: number;
    truncated: boolean;
    derivationEdges: Array<{ edgeId: string; edgeVersion: number }>;
  };
  use: null | {
    useId: string;
    usedAt: string;
    consumer: "model_output" | "tool_call" | "validator_input";
    evidence: MemoryUseEvidence[];
  };
  notExposedReason: NotExposedReason | null;
  highestObservedState: "retrieved" | "exposed" | "used";
}

/** One task-level trace with separate retrieval, exposure and evidenced-use facts. */
export interface MemoryUseTrace extends ShadowCaptureEnvelope {
  eventType: "memory_use_trace";
  traceId: string;
  traceVersion: number;
  sessionId: string;
  queryHash: string;
  finalPromptHash: string;
  modelId: string;
  modelVersion: string;
  environmentHash: string;
  accesses: CapturedMemoryAccess[];
  traceDigest: string;
}

export interface MemoryAccessInput {
  accessId: string;
  record: VersionedMemoryRecord;
  retrieval: CapturedMemoryAccess["retrieval"];
  exposure: null | {
    exposureId: string;
    exposedAt: string;
    channel: CaptureExposureChannel;
    representation: ExposureRepresentation;
    renderedText: string;
    truncated: boolean;
    derivationEdges?: Array<{ edgeId: string; edgeVersion: number }>;
  };
  use: CapturedMemoryAccess["use"];
  notExposedReason: NotExposedReason | null;
}

export interface MemoryUseTraceInput {
  context: ShadowCaptureContext & { taskRunId: string };
  traceId: string;
  traceVersion: number;
  sessionId: string;
  queryHash: string;
  finalPromptHash: string;
  modelId: string;
  modelVersion: string;
  environmentHash: string;
  accesses: MemoryAccessInput[];
}

export type ShadowCaptureEvent =
  | VersionedMemoryRecord
  | MaterializedL0Authority
  | AggregationManifest
  | MemoryUseTrace;

export interface CaptureCompletenessAudit {
  schemaVersion: "tdai-capture-completeness-audit.v1";
  eventSetHash: string;
  exactLocalizationCaptureReady: boolean;
  exactNodeIdentityReady: boolean;
  roleCorrectL0Ready: boolean;
  exactDerivationReady: boolean;
  runtimeAttributionReady: boolean;
  counts: {
    records: number;
    authorities: number;
    manifests: number;
    traces: number;
    derivationEdges: number;
    accesses: number;
  };
  errors: string[];
  warnings: string[];
  safety: {
    shadowOnly: true;
    feedbackDepth: 0;
    memoryIngestionAllowed: false;
    mayWriteProductionMemory: false;
    mayEnqueueFeedback: false;
    optimizationReady: false;
  };
}

function requireNonEmpty(value: string, field: string): void {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${field} is required`);
}

function requireHash(value: string, field: string): void {
  requireNonEmpty(value, field);
  if (!/^[a-f0-9]{64}$/i.test(value)) throw new Error(`${field} must be a SHA-256 hex digest`);
}

function requirePositiveVersion(value: number, field: string): void {
  if (!Number.isSafeInteger(value) || value < 1) throw new Error(`${field} must be a positive integer`);
}

function requireIso(value: string, field: string): void {
  requireNonEmpty(value, field);
  if (!Number.isFinite(Date.parse(value))) throw new Error(`${field} must be an ISO-compatible timestamp`);
}

function assertJsonValue(value: unknown, field: string, seen = new Set<object>()): asserts value is CaptureJsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error(`${field} contains a non-finite number`);
    return;
  }
  if (typeof value !== "object") throw new Error(`${field} must be JSON-only`);
  if (seen.has(value)) throw new Error(`${field} must not contain cycles`);
  seen.add(value);
  if (Array.isArray(value)) {
    value.forEach((entry, index) => assertJsonValue(entry, `${field}[${index}]`, seen));
  } else {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new Error(`${field} must contain plain objects`);
    for (const [key, entry] of Object.entries(value)) {
      requireNonEmpty(key, `${field} key`);
      assertJsonValue(entry, `${field}.${key}`, seen);
    }
  }
  seen.delete(value);
}

function assertContext(context: ShadowCaptureContext): void {
  requireNonEmpty(context.captureId, "context.captureId");
  requireIso(context.capturedAt, "context.capturedAt");
  if (context.origin !== "production_capture" && context.origin !== "benchmark_fixture") {
    throw new Error("Capture origin cannot be self-supervision or replay output");
  }
  if (context.feedbackDepth !== 0) throw new Error("Capture feedbackDepth must be 0");
  if (context.taskRunId !== null) requireNonEmpty(context.taskRunId, "context.taskRunId");
}

function assertScope(scope: MemoryCaptureScope, field: string): void {
  const keys: Array<keyof MemoryCaptureScope> = [
    "teamId", "userId", "agentId", "sessionKey", "sessionId", "taskId", "projectId", "sceneName",
  ];
  for (const key of keys) {
    const value = scope[key];
    if (value !== null) requireNonEmpty(value, `${field}.${key}`);
  }
}

function assertNodeRef(ref: MemoryNodeRef, expectedLayer?: MemoryLayer): void {
  if (expectedLayer && ref.layer !== expectedLayer) throw new Error(`Expected ${expectedLayer} reference`);
  if (ref.layer !== "L0" && ref.layer !== "L1" && ref.layer !== "L2") throw new Error("Unknown memory layer");
  requireNonEmpty(ref.id, "record.id");
  requirePositiveVersion(ref.version, `record.version:${ref.id}`);
  if (ref.layer === "L0" && ref.version !== 1) throw new Error("Persisted L0 references must use immutable version 1");
}

function nodeKey(ref: MemoryNodeRef): string {
  return `${ref.layer}\u001f${ref.id}\u001f${ref.version}`;
}

function assertUnique<T>(values: T[], key: (value: T) => string, field: string): void {
  const seen = new Set<string>();
  for (const value of values) {
    const identity = key(value);
    if (seen.has(identity)) throw new Error(`Duplicate ${field} ${identity}`);
    seen.add(identity);
  }
}

function deepFreeze<T>(value: T, seen = new Set<object>()): T {
  if (!value || typeof value !== "object" || seen.has(value as object)) return value;
  seen.add(value as object);
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function cloneFreeze<T>(value: T): T {
  return deepFreeze(structuredClone(value));
}

type EventBody<T extends ShadowCaptureEvent> = Omit<T, "eventId" | "eventHash">;

function sealEvent<T extends ShadowCaptureEvent>(body: EventBody<T>): T {
  const eventHash = canonicalHash(body);
  const eventId = `capture:${body.eventType}:${eventHash.slice(0, 32)}`;
  return cloneFreeze({ ...body, eventId, eventHash } as T);
}

function envelope(context: ShadowCaptureContext) {
  assertContext(context);
  return {
    schemaVersion: "tdai-shadow-capture.v1" as const,
    captureId: context.captureId,
    capturedAt: context.capturedAt,
    origin: context.origin,
    feedbackDepth: 0 as const,
    taskRunId: context.taskRunId,
    dataClassification: "shadow_telemetry" as const,
    memoryIngestionAllowed: false as const,
    mayWriteProductionMemory: false as const,
    mayEnqueueFeedback: false as const,
    feedbackReingestionEnabled: false as const,
    optimizationReady: false as const,
  };
}

function sortedRefs<T extends MemoryNodeRef>(refs: T[]): T[] {
  return [...refs].sort((left, right) => nodeKey(left).localeCompare(nodeKey(right)));
}

function assertBindings(bindings: Record<string, string>): void {
  for (const [key, value] of Object.entries(bindings)) {
    requireNonEmpty(key, "entity binding key");
    requireNonEmpty(value, `entityBindings.${key}`);
  }
}

export function createVersionedMemoryRecord(input: VersionedMemoryRecordInput): VersionedMemoryRecord {
  assertContext(input.context);
  if (input.layer !== "L1" && input.layer !== "L2") throw new Error("Versioned records only support L1 or L2");
  requireNonEmpty(input.recordId, "recordId");
  requireNonEmpty(input.logicalId, "logicalId");
  requirePositiveVersion(input.version, "version");
  requireNonEmpty(input.content, "content");
  assertJsonValue(input.metadata, "metadata");
  assertScope(input.scope, "scope");
  assertBindings(input.entityBindings);
  requireIso(input.createdAt, "createdAt");
  requireIso(input.observedAt, "observedAt");
  requireHash(input.persistenceReceiptHash, "persistenceReceiptHash");
  if (input.capturePoint === "l1_write_receipt" && input.layer !== "L1") {
    throw new Error("l1_write_receipt requires an L1 record");
  }
  if (input.capturePoint === "l2_profile_commit_receipt" && input.layer !== "L2") {
    throw new Error("l2_profile_commit_receipt requires an L2 record");
  }
  if ((input.capturePoint === "benchmark_fixture") !== (input.context.origin === "benchmark_fixture")) {
    throw new Error("benchmark_fixture capture point and origin must agree");
  }
  const sourceL0 = sortedRefs(input.sourceL0 ?? []);
  sourceL0.forEach((ref) => assertNodeRef(ref, "L0"));
  assertUnique(sourceL0, nodeKey, "L0 source reference");
  const predecessors = [...(input.predecessors ?? [])].sort((left, right) =>
    `${left.relation}\u001f${nodeKey(left.record)}`.localeCompare(`${right.relation}\u001f${nodeKey(right.record)}`));
  predecessors.forEach((entry) => {
    assertNodeRef(entry.record, entry.relation === "supersedes" ? "L2" : "L1");
    if (input.layer === "L1" && entry.relation === "supersedes") {
      throw new Error("L1 version predecessors must use replaces/merged_from");
    }
    if (input.layer === "L2" && entry.relation !== "supersedes") {
      throw new Error("L2 version predecessors must use supersedes");
    }
  });
  assertUnique(predecessors, (entry) => `${entry.relation}\u001f${nodeKey(entry.record)}`, "predecessor");
  if (input.layer === "L2" && sourceL0.length > 0) {
    throw new Error("L2 source lineage must be represented by an AggregationManifest, not direct L0 fields");
  }
  const record: ExactPersistedMemoryRef = { layer: input.layer, id: input.recordId, version: input.version };
  const immutableRecordBody = {
    record,
    logicalId: input.logicalId,
    content: input.content,
    contentHash: canonicalHash(input.content),
    metadata: structuredClone(input.metadata),
    metadataHash: canonicalHash(input.metadata),
    scope: structuredClone(input.scope),
    scopeHash: canonicalHash(input.scope),
    entityBindings: Object.fromEntries(Object.entries(input.entityBindings).sort(([a], [b]) => a.localeCompare(b))),
    entityBindingHash: canonicalHash(input.entityBindings),
    sourceL0,
    predecessors,
    createdAt: input.createdAt,
    observedAt: input.observedAt,
  };
  const payload: CapturedMemoryPayload = {
    ...immutableRecordBody,
    capturePoint: input.capturePoint,
    persistenceReceiptHash: input.persistenceReceiptHash,
    // Receipt/capture-point prove where the snapshot came from, but do not
    // change the immutable semantic identity of the persisted record version.
    recordDigest: canonicalHash(immutableRecordBody),
  };
  return sealEvent<VersionedMemoryRecord>({
    ...envelope(input.context),
    eventType: "versioned_memory_record",
    payload,
  });
}

function authorityForRole(role: PersistedL0Role): {
  authorityClass: L0AuthorityClass;
  eligibleForUserFactSupport: boolean;
} {
  return role === "user"
    ? { authorityClass: "user_assertion", eligibleForUserFactSupport: true }
    : { authorityClass: "assistant_generated_output", eligibleForUserFactSupport: false };
}

function assertSpan(content: string, span: SourceSpan, field: string): void {
  if (!Number.isSafeInteger(span.start) || !Number.isSafeInteger(span.end)) {
    throw new Error(`${field} offsets must be integers`);
  }
  if (span.start < 0 || span.end <= span.start || span.end > content.length) {
    throw new Error(`${field} is outside the materialized content`);
  }
  if (!content.slice(span.start, span.end).trim()) throw new Error(`${field} selects no non-whitespace content`);
}

export function materializeL0Authority(input: MaterializedL0AuthorityInput): MaterializedL0Authority {
  assertContext(input.context);
  requireNonEmpty(input.source.recordId, "source.recordId");
  if (input.source.version !== 1) throw new Error("Persisted L0 authority must use immutable version 1");
  if (input.source.role !== "user" && input.source.role !== "assistant") {
    throw new Error(`Unsupported persisted L0 role: ${input.source.role}`);
  }
  if ((input.source.materializationBasis === "benchmark_fixture") !== (input.context.origin === "benchmark_fixture")) {
    throw new Error("benchmark_fixture materialization basis and origin must agree");
  }
  requireNonEmpty(input.source.content, "source.content");
  requireIso(input.source.recordedAt, "source.recordedAt");
  assertScope(input.source.scope, "source.scope");
  const role = input.source.role;
  const derivedAuthority = authorityForRole(role);
  const sourceRef: ExactL0Ref = { layer: "L0", id: input.source.recordId, version: 1 };
  const assertions = input.assertions.map((assertion): MaterializedL0Assertion => {
    requireNonEmpty(assertion.assertionId, "assertion.assertionId");
    requireNonEmpty(assertion.claimId, "assertion.claimId");
    assertSpan(input.source.content, assertion.span, `assertion.span:${assertion.assertionId}`);
    const supports = sortedRefs(assertion.supports);
    supports.forEach((ref) => assertNodeRef(ref, "L1"));
    assertUnique(supports, nodeKey, `assertion support:${assertion.assertionId}`);
    const sourceText = input.source.content.slice(assertion.span.start, assertion.span.end);
    return {
      assertionId: assertion.assertionId,
      claimId: assertion.claimId,
      span: structuredClone(assertion.span),
      sourceText,
      sourceTextHash: canonicalHash(sourceText),
      supports,
      ...derivedAuthority,
    };
  }).sort((left, right) => left.assertionId.localeCompare(right.assertionId));
  assertUnique(assertions, (assertion) => assertion.assertionId, "L0 assertion");
  const source: MaterializedL0Source = {
    record: sourceRef,
    role,
    ...derivedAuthority,
    content: input.source.content,
    contentHash: canonicalHash(input.source.content),
    recordedAt: input.source.recordedAt,
    scope: structuredClone(input.source.scope),
    scopeHash: canonicalHash(input.source.scope),
    materializationBasis: input.source.materializationBasis,
  };
  const authorityIdentityHash = canonicalHash(assertions.map((assertion) => ({
    assertionId: assertion.assertionId,
    claimId: assertion.claimId,
    supports: assertion.supports,
  })));
  const authorityWithoutDigest = {
    authorityId: `authority:l0:${input.source.recordId}@1:${authorityIdentityHash.slice(0, 20)}`,
    authorityVersion: 1 as const,
    source,
    assertions,
  };
  return sealEvent<MaterializedL0Authority>({
    ...envelope(input.context),
    eventType: "materialized_l0_authority",
    ...authorityWithoutDigest,
    authorityDigest: canonicalHash(authorityWithoutDigest),
  });
}

function assertAggregatorIdentity(identity: AggregatorIdentity): void {
  requireNonEmpty(identity.componentId, "aggregator.componentId");
  requireNonEmpty(identity.componentVersion, "aggregator.componentVersion");
  requireNonEmpty(identity.promptId, "aggregator.promptId");
  requireNonEmpty(identity.promptVersion, "aggregator.promptVersion");
  requireHash(identity.promptHash, "aggregator.promptHash");
  requireNonEmpty(identity.modelId, "aggregator.modelId");
  requireNonEmpty(identity.modelVersion, "aggregator.modelVersion");
  if (identity.seed !== null && !Number.isSafeInteger(identity.seed)) throw new Error("aggregator.seed must be an integer or null");
}

export function freezeAggregationInputs(input: FreezeAggregationInputsInput): FrozenAggregationInputSet {
  requireNonEmpty(input.aggregationRunId, "aggregationRunId");
  requireIso(input.frozenAt, "frozenAt");
  assertAggregatorIdentity(input.aggregator);
  if (input.records.length === 0) throw new Error("Aggregation input set must not be empty");
  const inputs = input.records.map((event): FrozenAggregationInput => {
    assertShadowCaptureEvent(event);
    if (event.payload.record.layer !== "L1") throw new Error("Aggregation inputs must be exact L1 versions");
    return {
      record: structuredClone(event.payload.record),
      logicalId: event.payload.logicalId,
      contentHash: event.payload.contentHash,
      recordDigest: event.payload.recordDigest,
      scopeHash: event.payload.scopeHash,
      entityBindingHash: event.payload.entityBindingHash,
    };
  }).sort((left, right) => nodeKey(left.record).localeCompare(nodeKey(right.record)));
  assertUnique(inputs, (entry) => nodeKey(entry.record), "aggregation input");
  const body = {
    schemaVersion: "tdai-frozen-aggregation-inputs.v1" as const,
    aggregationRunId: input.aggregationRunId,
    frozenAt: input.frozenAt,
    aggregator: structuredClone(input.aggregator),
    inputs,
  };
  return cloneFreeze({ ...body, inputSetHash: canonicalHash(body) });
}

function assertFrozenInputSet(input: FrozenAggregationInputSet): void {
  if (input.schemaVersion !== "tdai-frozen-aggregation-inputs.v1") throw new Error("Unsupported frozen input schema");
  requireNonEmpty(input.aggregationRunId, "frozenInputs.aggregationRunId");
  requireIso(input.frozenAt, "frozenInputs.frozenAt");
  assertAggregatorIdentity(input.aggregator);
  if (input.inputs.length === 0) throw new Error("Frozen aggregation input set must not be empty");
  input.inputs.forEach((entry) => {
    assertNodeRef(entry.record, "L1");
    requireNonEmpty(entry.logicalId, "frozen input logicalId");
    requireHash(entry.contentHash, "frozen input contentHash");
    requireHash(entry.recordDigest, "frozen input recordDigest");
    requireHash(entry.scopeHash, "frozen input scopeHash");
    requireHash(entry.entityBindingHash, "frozen input entityBindingHash");
  });
  assertUnique(input.inputs, (entry) => nodeKey(entry.record), "frozen aggregation input");
  const { inputSetHash: _hash, ...body } = input;
  if (canonicalHash(body) !== input.inputSetHash) throw new Error("Frozen aggregation input set hash mismatch");
}

function nonWhitespaceCoverage(content: string, spans: SourceSpan[]): ClaimCoverage {
  const covered = new Set<number>();
  let total = 0;
  for (let index = 0; index < content.length; index++) {
    if (/\s/u.test(content[index]!)) continue;
    total++;
    if (spans.some((span) => index >= span.start && index < span.end)) covered.add(index);
  }
  return { coveredNonWhitespaceChars: covered.size, totalNonWhitespaceChars: total, complete: covered.size === total };
}

export function createAggregationManifest(input: AggregationManifestInput): AggregationManifest {
  assertContext(input.context);
  requireNonEmpty(input.manifestId, "manifestId");
  requirePositiveVersion(input.manifestVersion, "manifestVersion");
  requireIso(input.aggregationCompletedAt, "aggregationCompletedAt");
  assertFrozenInputSet(input.frozenInputs);
  assertShadowCaptureEvent(input.output);
  if (input.output.payload.record.layer !== "L2") throw new Error("Aggregation output must be an exact L2 version");
  if (Date.parse(input.aggregationCompletedAt) < Date.parse(input.frozenInputs.frozenAt)) {
    throw new Error("Aggregation cannot complete before its inputs were frozen");
  }
  const inputIndex = new Map(input.frozenInputs.inputs.map((entry) => [nodeKey(entry.record), entry] as const));
  const outputRef = input.output.payload.record;
  const edgeIndex = new Map<string, ExactDerivationEdgeSnapshot>();
  const edgeIdVersions = new Map<string, number>();
  const claims = input.claims.map((claim): AggregatedClaim => {
    requireNonEmpty(claim.claimId, "claim.claimId");
    assertSpan(input.output.payload.content, claim.span, `claim.span:${claim.claimId}`);
    const derivations = claim.sources.map((source) => {
      requireNonEmpty(source.edgeId, `edgeId:${claim.claimId}`);
      requirePositiveVersion(source.edgeVersion, `edgeVersion:${source.edgeId}`);
      assertNodeRef(source.source, "L1");
      const frozen = inputIndex.get(nodeKey(source.source));
      if (!frozen) throw new Error(`Claim ${claim.claimId} cites an L1 version outside the frozen input set`);
      const priorEdgeVersion = edgeIdVersions.get(source.edgeId);
      if (priorEdgeVersion !== undefined && priorEdgeVersion !== source.edgeVersion) {
        throw new Error(`Manifest contains multiple versions of edge ${source.edgeId}`);
      }
      edgeIdVersions.set(source.edgeId, source.edgeVersion);
      const edgeKey = `${source.edgeId}\u001f${source.edgeVersion}`;
      const existing = edgeIndex.get(edgeKey);
      if (existing && nodeKey(existing.from) !== nodeKey(source.source)) {
        throw new Error(`Edge ${source.edgeId}@${source.edgeVersion} has conflicting source endpoints`);
      }
      const claimIds = [...new Set([...(existing?.claimIds ?? []), claim.claimId])].sort();
      edgeIndex.set(edgeKey, {
        edgeId: source.edgeId,
        version: source.edgeVersion,
        from: structuredClone(source.source),
        to: structuredClone(outputRef),
        sourceContentHash: frozen.contentHash,
        sourceRecordDigest: frozen.recordDigest,
        claimIds,
        metadataHash: canonicalHash({
          aggregationRunId: input.frozenInputs.aggregationRunId,
          claimIds,
          from: source.source,
          to: outputRef,
        }),
      });
      return {
        edgeId: source.edgeId,
        edgeVersion: source.edgeVersion,
        source: structuredClone(source.source),
        sourceContentHash: frozen.contentHash,
        sourceRecordDigest: frozen.recordDigest,
      };
    }).sort((left, right) =>
      `${left.edgeId}\u001f${left.edgeVersion}`.localeCompare(`${right.edgeId}\u001f${right.edgeVersion}`));
    assertUnique(derivations, (entry) => `${entry.edgeId}\u001f${entry.edgeVersion}`, `claim derivation:${claim.claimId}`);
    const text = input.output.payload.content.slice(claim.span.start, claim.span.end);
    return {
      claimId: claim.claimId,
      span: structuredClone(claim.span),
      text,
      textHash: canonicalHash(text),
      derivations,
      lineageStatus: derivations.length > 0 ? "attributed" : "unattributed",
    };
  }).sort((left, right) => left.claimId.localeCompare(right.claimId));
  assertUnique(claims, (claim) => claim.claimId, "aggregation claim");
  const edges = [...edgeIndex.values()].sort((left, right) =>
    `${left.edgeId}\u001f${left.version}`.localeCompare(`${right.edgeId}\u001f${right.version}`));
  const manifestWithoutDigest = {
    manifestId: input.manifestId,
    manifestVersion: input.manifestVersion,
    aggregationRunId: input.frozenInputs.aggregationRunId,
    frozenInputs: structuredClone(input.frozenInputs),
    output: {
      record: structuredClone(outputRef),
      logicalId: input.output.payload.logicalId,
      contentHash: input.output.payload.contentHash,
      recordDigest: input.output.payload.recordDigest,
    },
    claims,
    edges,
    claimCoverage: nonWhitespaceCoverage(input.output.payload.content, claims.map((claim) => claim.span)),
    aggregationCompletedAt: input.aggregationCompletedAt,
  };
  return sealEvent<AggregationManifest>({
    ...envelope(input.context),
    eventType: "aggregation_manifest",
    ...manifestWithoutDigest,
    manifestDigest: canonicalHash(manifestWithoutDigest),
  });
}

function requireFiniteOrNull(value: number | null, field: string): void {
  if (value !== null && !Number.isFinite(value)) throw new Error(`${field} must be finite or null`);
}

export function createMemoryUseTrace(input: MemoryUseTraceInput): MemoryUseTrace {
  assertContext(input.context);
  requireNonEmpty(input.context.taskRunId, "context.taskRunId");
  requireNonEmpty(input.traceId, "traceId");
  requirePositiveVersion(input.traceVersion, "traceVersion");
  requireNonEmpty(input.sessionId, "sessionId");
  requireHash(input.queryHash, "queryHash");
  requireHash(input.finalPromptHash, "finalPromptHash");
  requireNonEmpty(input.modelId, "modelId");
  requireNonEmpty(input.modelVersion, "modelVersion");
  requireHash(input.environmentHash, "environmentHash");
  const exposureIds = new Set<string>();
  const useIds = new Set<string>();
  const accesses = input.accesses.map((access): CapturedMemoryAccess => {
    requireNonEmpty(access.accessId, "accessId");
    assertShadowCaptureEvent(access.record);
    assertNodeRef(access.record.payload.record);
    requireNonEmpty(access.retrieval.retrievalId, `retrievalId:${access.accessId}`);
    requireIso(access.retrieval.retrievedAt, `retrievedAt:${access.accessId}`);
    requireHash(access.retrieval.queryHash, `retrieval.queryHash:${access.accessId}`);
    if (access.retrieval.rank !== null && (!Number.isSafeInteger(access.retrieval.rank) || access.retrieval.rank < 1)) {
      throw new Error(`retrieval.rank:${access.accessId} must be a positive integer or null`);
    }
    requireFiniteOrNull(access.retrieval.score, `retrieval.score:${access.accessId}`);
    let normalizedDerivationEdges: Array<{ edgeId: string; edgeVersion: number }> = [];
    if (access.exposure === null) {
      if (access.notExposedReason === null) throw new Error(`Retrieved-only access ${access.accessId} requires notExposedReason`);
      if (access.use !== null) throw new Error(`Memory use ${access.accessId} cannot exist without exposure`);
    } else {
      if (access.notExposedReason !== null) throw new Error(`Exposed access ${access.accessId} cannot carry notExposedReason`);
      requireNonEmpty(access.exposure.exposureId, `exposureId:${access.accessId}`);
      if (exposureIds.has(access.exposure.exposureId)) throw new Error(`Duplicate exposureId ${access.exposure.exposureId}`);
      exposureIds.add(access.exposure.exposureId);
      requireIso(access.exposure.exposedAt, `exposedAt:${access.accessId}`);
      if (Date.parse(access.exposure.exposedAt) < Date.parse(access.retrieval.retrievedAt)) {
        throw new Error(`Exposure ${access.accessId} precedes retrieval`);
      }
      requireNonEmpty(access.exposure.renderedText, `renderedText:${access.accessId}`);
      const isL1 = access.record.payload.record.layer === "L1";
      if (isL1 && access.exposure.channel !== "prompt_l1") throw new Error("L1 exposure must use prompt_l1 channel");
      if (!isL1 && access.exposure.channel === "prompt_l1") throw new Error("L2 exposure cannot use prompt_l1 channel");
      normalizedDerivationEdges = [...(access.exposure.derivationEdges ?? [])].sort((left, right) =>
        `${left.edgeId}\u001f${left.edgeVersion}`.localeCompare(`${right.edgeId}\u001f${right.edgeVersion}`));
      for (const edge of normalizedDerivationEdges) {
        requireNonEmpty(edge.edgeId, `derivation edge:${access.accessId}`);
        requirePositiveVersion(edge.edgeVersion, `derivation edge version:${edge.edgeId}`);
      }
      assertUnique(normalizedDerivationEdges, (edge) => `${edge.edgeId}\u001f${edge.edgeVersion}`, `exposure edge:${access.accessId}`);
      if (isL1 && normalizedDerivationEdges.length > 0) throw new Error("L1 exposure cannot cite L1→L2 derivation edges");
    }
    if (access.use !== null) {
      requireNonEmpty(access.use.useId, `useId:${access.accessId}`);
      if (useIds.has(access.use.useId)) throw new Error(`Duplicate useId ${access.use.useId}`);
      useIds.add(access.use.useId);
      requireIso(access.use.usedAt, `usedAt:${access.accessId}`);
      if (Date.parse(access.use.usedAt) < Date.parse(access.exposure!.exposedAt)) {
        throw new Error(`Use ${access.accessId} precedes exposure`);
      }
      if (access.use.evidence.length === 0) {
        throw new Error(`Use ${access.accessId} requires observable evidence; task outcome alone is insufficient`);
      }
      access.use.evidence.forEach((evidence) => {
        requireNonEmpty(evidence.evidenceId, `use evidenceId:${access.accessId}`);
        requireHash(evidence.evidenceHash, `use evidenceHash:${access.accessId}`);
      });
      assertUnique(access.use.evidence, (evidence) => evidence.evidenceId, `use evidence:${access.accessId}`);
    }
    return {
      accessId: access.accessId,
      node: structuredClone(access.record.payload.record),
      recordDigest: access.record.payload.recordDigest,
      retrieval: structuredClone(access.retrieval),
      exposure: access.exposure === null ? null : {
        exposureId: access.exposure.exposureId,
        exposedAt: access.exposure.exposedAt,
        channel: access.exposure.channel,
        representation: access.exposure.representation,
        renderedHash: canonicalHash(access.exposure.renderedText),
        renderedChars: access.exposure.renderedText.length,
        truncated: access.exposure.truncated,
        derivationEdges: structuredClone(normalizedDerivationEdges),
      },
      use: structuredClone(access.use),
      notExposedReason: access.notExposedReason,
      highestObservedState: access.use ? "used" : access.exposure ? "exposed" : "retrieved",
    };
  }).sort((left, right) => left.accessId.localeCompare(right.accessId));
  assertUnique(accesses, (access) => access.accessId, "memory access");
  assertUnique(accesses, (access) => access.retrieval.retrievalId, "retrievalId");
  const traceWithoutDigest = {
    traceId: input.traceId,
    traceVersion: input.traceVersion,
    sessionId: input.sessionId,
    queryHash: input.queryHash,
    finalPromptHash: input.finalPromptHash,
    modelId: input.modelId,
    modelVersion: input.modelVersion,
    environmentHash: input.environmentHash,
    accesses,
  };
  return sealEvent<MemoryUseTrace>({
    ...envelope(input.context),
    eventType: "memory_use_trace",
    ...traceWithoutDigest,
    traceDigest: canonicalHash(traceWithoutDigest),
  });
}

function eventBody(event: ShadowCaptureEvent): EventBody<ShadowCaptureEvent> {
  const { eventId: _eventId, eventHash: _eventHash, ...body } = event;
  return body;
}

/** Runtime guard for JSONL reloads and hostile/untyped callers. */
export function assertShadowCaptureEvent(event: ShadowCaptureEvent): void {
  if (!event || typeof event !== "object") throw new Error("Capture event must be an object");
  if (event.schemaVersion !== "tdai-shadow-capture.v1") throw new Error("Unsupported capture event schema");
  assertContext(event);
  if (
    event.dataClassification !== "shadow_telemetry"
    || event.memoryIngestionAllowed !== false
    || event.mayWriteProductionMemory !== false
    || event.mayEnqueueFeedback !== false
    || event.feedbackReingestionEnabled !== false
    || event.optimizationReady !== false
  ) {
    throw new Error("Capture event violates the shadow-only, non-recursive safety contract");
  }
  const expectedHash = canonicalHash(eventBody(event));
  if (event.eventHash !== expectedHash) throw new Error("Capture event hash mismatch");
  if (event.eventId !== `capture:${event.eventType}:${expectedHash.slice(0, 32)}`) {
    throw new Error("Capture event ID mismatch");
  }
  if (event.eventType === "versioned_memory_record") {
    assertNodeRef(event.payload.record);
    if (event.payload.record.layer !== "L1" && event.payload.record.layer !== "L2") {
      throw new Error("Versioned capture records only support L1 or L2");
    }
    if (
      event.payload.capturePoint !== "l1_write_receipt"
      && event.payload.capturePoint !== "l2_profile_commit_receipt"
      && event.payload.capturePoint !== "benchmark_fixture"
    ) {
      throw new Error("Unsupported versioned record capturePoint");
    }
    requireNonEmpty(event.payload.logicalId, "payload.logicalId");
    requireNonEmpty(event.payload.content, "payload.content");
    requireHash(event.payload.contentHash, "payload.contentHash");
    assertJsonValue(event.payload.metadata, "payload.metadata");
    requireHash(event.payload.metadataHash, "payload.metadataHash");
    assertScope(event.payload.scope, "payload.scope");
    requireHash(event.payload.scopeHash, "payload.scopeHash");
    assertBindings(event.payload.entityBindings);
    requireHash(event.payload.entityBindingHash, "payload.entityBindingHash");
    requireIso(event.payload.createdAt, "payload.createdAt");
    requireIso(event.payload.observedAt, "payload.observedAt");
    requireHash(event.payload.persistenceReceiptHash, "payload.persistenceReceiptHash");
    requireHash(event.payload.recordDigest, "payload.recordDigest");
    if (canonicalHash(event.payload.content) !== event.payload.contentHash) throw new Error("Record content hash mismatch");
    if (canonicalHash(event.payload.metadata) !== event.payload.metadataHash) throw new Error("Record metadata hash mismatch");
    if (canonicalHash(event.payload.scope) !== event.payload.scopeHash) throw new Error("Record scope hash mismatch");
    if (canonicalHash(event.payload.entityBindings) !== event.payload.entityBindingHash) {
      throw new Error("Record entity-binding hash mismatch");
    }
    event.payload.sourceL0.forEach((ref) => assertNodeRef(ref, "L0"));
    assertUnique(event.payload.sourceL0, nodeKey, "record L0 source");
    event.payload.predecessors.forEach((entry) => {
      assertNodeRef(entry.record, entry.relation === "supersedes" ? "L2" : "L1");
      if (event.payload.record.layer === "L1" && entry.relation === "supersedes") {
        throw new Error("L1 record has an L2 supersedes predecessor");
      }
      if (event.payload.record.layer === "L2" && entry.relation !== "supersedes") {
        throw new Error("L2 record has an L1 merge predecessor");
      }
    });
    assertUnique(event.payload.predecessors, (entry) => `${entry.relation}\u001f${nodeKey(entry.record)}`, "record predecessor");
    if (event.payload.record.layer === "L2" && event.payload.sourceL0.length > 0) {
      throw new Error("L2 record contains direct L0 lineage");
    }
    if (event.payload.capturePoint === "l1_write_receipt" && event.payload.record.layer !== "L1") {
      throw new Error("l1_write_receipt requires L1");
    }
    if (event.payload.capturePoint === "l2_profile_commit_receipt" && event.payload.record.layer !== "L2") {
      throw new Error("l2_profile_commit_receipt requires L2");
    }
    if ((event.payload.capturePoint === "benchmark_fixture") !== (event.origin === "benchmark_fixture")) {
      throw new Error("Record benchmark capture point/origin mismatch");
    }
    const {
      recordDigest: _digest,
      capturePoint: _capturePoint,
      persistenceReceiptHash: _receipt,
      ...body
    } = event.payload;
    if (canonicalHash(body) !== event.payload.recordDigest) throw new Error("Record digest mismatch");
  } else if (event.eventType === "materialized_l0_authority") {
    assertNodeRef(event.source.record, "L0");
    requireNonEmpty(event.authorityId, "authorityId");
    if (event.authorityVersion !== 1) throw new Error("L0 authorityVersion must be 1");
    if (event.source.role !== "user" && event.source.role !== "assistant") throw new Error("Unsupported persisted L0 role");
    requireNonEmpty(event.source.content, "authority source content");
    requireHash(event.source.contentHash, "authority source contentHash");
    requireIso(event.source.recordedAt, "authority source recordedAt");
    assertScope(event.source.scope, "authority source scope");
    requireHash(event.source.scopeHash, "authority source scopeHash");
    if (canonicalHash(event.source.scope) !== event.source.scopeHash) throw new Error("L0 scope hash mismatch");
    if ((event.source.materializationBasis === "benchmark_fixture") !== (event.origin === "benchmark_fixture")) {
      throw new Error("L0 benchmark materialization basis/origin mismatch");
    }
    const expected = authorityForRole(event.source.role);
    if (
      event.source.authorityClass !== expected.authorityClass
      || event.source.eligibleForUserFactSupport !== expected.eligibleForUserFactSupport
      || event.assertions.some((assertion) =>
        assertion.authorityClass !== expected.authorityClass
        || assertion.eligibleForUserFactSupport !== expected.eligibleForUserFactSupport)
    ) {
      throw new Error("L0 authority class does not match its persisted role");
    }
    if (canonicalHash(event.source.content) !== event.source.contentHash) throw new Error("L0 content hash mismatch");
    event.assertions.forEach((assertion) => {
      requireNonEmpty(assertion.assertionId, "assertion.assertionId");
      requireNonEmpty(assertion.claimId, "assertion.claimId");
      assertSpan(event.source.content, assertion.span, `assertion.span:${assertion.assertionId}`);
      const selected = event.source.content.slice(assertion.span.start, assertion.span.end);
      if (selected !== assertion.sourceText) throw new Error(`L0 assertion text/span mismatch: ${assertion.assertionId}`);
      if (canonicalHash(selected) !== assertion.sourceTextHash) throw new Error(`L0 assertion hash mismatch: ${assertion.assertionId}`);
      assertion.supports.forEach((ref) => assertNodeRef(ref, "L1"));
      assertUnique(assertion.supports, nodeKey, `L0 assertion support:${assertion.assertionId}`);
    });
    assertUnique(event.assertions, (assertion) => assertion.assertionId, "L0 assertion");
    const expectedAuthorityIdentityHash = canonicalHash(event.assertions.map((assertion) => ({
      assertionId: assertion.assertionId,
      claimId: assertion.claimId,
      supports: assertion.supports,
    })));
    if (event.authorityId !== `authority:l0:${event.source.record.id}@1:${expectedAuthorityIdentityHash.slice(0, 20)}`) {
      throw new Error("L0 authority ID mismatch");
    }
    requireHash(event.authorityDigest, "authorityDigest");
    const { authorityDigest: _digest, eventId: _id, eventHash: _hash, ...rest } = event;
    const { schemaVersion: _schema, eventType: _type, captureId: _capture, capturedAt: _at,
      origin: _origin, feedbackDepth: _depth, taskRunId: _task, dataClassification: _class,
      memoryIngestionAllowed: _ingest, mayWriteProductionMemory: _write, mayEnqueueFeedback: _enqueue,
      feedbackReingestionEnabled: _reingest, optimizationReady: _ready, ...authorityBody } = rest;
    if (canonicalHash(authorityBody) !== event.authorityDigest) throw new Error("L0 authority digest mismatch");
  } else if (event.eventType === "aggregation_manifest") {
    assertFrozenInputSet(event.frozenInputs);
    requireNonEmpty(event.manifestId, "manifestId");
    requirePositiveVersion(event.manifestVersion, "manifestVersion");
    requireNonEmpty(event.aggregationRunId, "aggregationRunId");
    if (event.aggregationRunId !== event.frozenInputs.aggregationRunId) throw new Error("Aggregation run ID mismatch");
    requireIso(event.aggregationCompletedAt, "aggregationCompletedAt");
    if (Date.parse(event.aggregationCompletedAt) < Date.parse(event.frozenInputs.frozenAt)) {
      throw new Error("Aggregation completion precedes frozen inputs");
    }
    assertNodeRef(event.output.record, "L2");
    requireNonEmpty(event.output.logicalId, "aggregation output logicalId");
    requireHash(event.output.contentHash, "aggregation output contentHash");
    requireHash(event.output.recordDigest, "aggregation output recordDigest");
    const inputIndex = new Map(event.frozenInputs.inputs.map((entry) => [nodeKey(entry.record), entry] as const));
    event.claims.forEach((claim) => requireNonEmpty(claim.claimId, "aggregation claimId"));
    const claimIndex = new Map(event.claims.map((claim) => [claim.claimId, claim] as const));
    const claimIds = new Set(claimIndex.keys());
    assertUnique(event.claims, (claim) => claim.claimId, "aggregation claim");
    const edgeIndex = new Map(event.edges.map((edge) => [`${edge.edgeId}\u001f${edge.version}`, edge] as const));
    assertUnique(event.edges, (edge) => `${edge.edgeId}\u001f${edge.version}`, "aggregation edge");
    const edgeIdVersions = new Map<string, number>();
    for (const edge of event.edges) {
      requireNonEmpty(edge.edgeId, "aggregation edgeId");
      requirePositiveVersion(edge.version, `aggregation edgeVersion:${edge.edgeId}`);
      const previous = edgeIdVersions.get(edge.edgeId);
      if (previous !== undefined && previous !== edge.version) throw new Error(`Multiple edge versions for ${edge.edgeId}`);
      edgeIdVersions.set(edge.edgeId, edge.version);
      assertNodeRef(edge.from, "L1");
      assertNodeRef(edge.to, "L2");
      if (nodeKey(edge.to) !== nodeKey(event.output.record)) throw new Error(`Aggregation edge ${edge.edgeId} targets wrong L2`);
      const frozen = inputIndex.get(nodeKey(edge.from));
      if (!frozen || frozen.contentHash !== edge.sourceContentHash || frozen.recordDigest !== edge.sourceRecordDigest) {
        throw new Error(`Aggregation edge ${edge.edgeId} does not bind a frozen L1 input`);
      }
      requireHash(edge.metadataHash, `aggregation edge metadataHash:${edge.edgeId}`);
      assertUnique(edge.claimIds, (claimId) => claimId, `aggregation edge claimId:${edge.edgeId}`);
      const sortedClaimIds = [...edge.claimIds].sort();
      if (edge.claimIds.some((claimId, index) => claimId !== sortedClaimIds[index])) {
        throw new Error(`Aggregation edge ${edge.edgeId} claim IDs must be sorted`);
      }
      if (edge.claimIds.length === 0 || edge.claimIds.some((claimId) => !claimIds.has(claimId))) {
        throw new Error(`Aggregation edge ${edge.edgeId} has invalid claim IDs`);
      }
      for (const claimId of edge.claimIds) {
        const claim = claimIndex.get(claimId)!;
        const reverseDerivation = claim.derivations.find((derivation) =>
          derivation.edgeId === edge.edgeId && derivation.edgeVersion === edge.version);
        if (!reverseDerivation
          || nodeKey(reverseDerivation.source) !== nodeKey(edge.from)
          || reverseDerivation.sourceContentHash !== edge.sourceContentHash
          || reverseDerivation.sourceRecordDigest !== edge.sourceRecordDigest) {
          throw new Error(`Aggregation edge/claim reverse mapping mismatch: ${edge.edgeId}@${edge.version}->${claimId}`);
        }
      }
      const expectedMetadataHash = canonicalHash({
        aggregationRunId: event.aggregationRunId,
        claimIds: edge.claimIds,
        from: edge.from,
        to: edge.to,
      });
      if (edge.metadataHash !== expectedMetadataHash) throw new Error(`Aggregation edge metadata mismatch: ${edge.edgeId}`);
    }
    for (const claim of event.claims) {
      requireNonEmpty(claim.claimId, "aggregation claimId");
      if (!Number.isSafeInteger(claim.span.start) || !Number.isSafeInteger(claim.span.end)
        || claim.span.start < 0 || claim.span.end <= claim.span.start) {
        throw new Error(`Invalid aggregation claim span: ${claim.claimId}`);
      }
      requireNonEmpty(claim.text, `aggregation claim text:${claim.claimId}`);
      if (claim.text.length !== claim.span.end - claim.span.start) throw new Error(`Aggregation claim span length mismatch: ${claim.claimId}`);
      if (canonicalHash(claim.text) !== claim.textHash) throw new Error(`Aggregation claim text hash mismatch: ${claim.claimId}`);
      const expectedLineage = claim.derivations.length > 0 ? "attributed" : "unattributed";
      if (claim.lineageStatus !== expectedLineage) throw new Error(`Aggregation claim lineage status mismatch: ${claim.claimId}`);
      for (const derivation of claim.derivations) {
        const edge = edgeIndex.get(`${derivation.edgeId}\u001f${derivation.edgeVersion}`);
        if (!edge || !edge.claimIds.includes(claim.claimId) || nodeKey(edge.from) !== nodeKey(derivation.source)
          || edge.sourceContentHash !== derivation.sourceContentHash
          || edge.sourceRecordDigest !== derivation.sourceRecordDigest) {
          throw new Error(`Aggregation claim derivation mismatch: ${claim.claimId}`);
        }
      }
      assertUnique(claim.derivations, (entry) => `${entry.edgeId}\u001f${entry.edgeVersion}`, `claim derivation:${claim.claimId}`);
    }
    if (!Number.isSafeInteger(event.claimCoverage.coveredNonWhitespaceChars)
      || !Number.isSafeInteger(event.claimCoverage.totalNonWhitespaceChars)
      || event.claimCoverage.coveredNonWhitespaceChars < 0
      || event.claimCoverage.totalNonWhitespaceChars < event.claimCoverage.coveredNonWhitespaceChars
      || event.claimCoverage.complete !== (
        event.claimCoverage.coveredNonWhitespaceChars === event.claimCoverage.totalNonWhitespaceChars
      )) {
      throw new Error("Invalid aggregation claim coverage");
    }
    requireHash(event.manifestDigest, "manifestDigest");
    const { manifestDigest: _digest, eventId: _id, eventHash: _hash, ...rest } = event;
    const { schemaVersion: _schema, eventType: _type, captureId: _capture, capturedAt: _at,
      origin: _origin, feedbackDepth: _depth, taskRunId: _task, dataClassification: _class,
      memoryIngestionAllowed: _ingest, mayWriteProductionMemory: _write, mayEnqueueFeedback: _enqueue,
      feedbackReingestionEnabled: _reingest, optimizationReady: _ready, ...manifestBody } = rest;
    if (canonicalHash(manifestBody) !== event.manifestDigest) throw new Error("Aggregation manifest digest mismatch");
  } else if (event.eventType === "memory_use_trace") {
    requireNonEmpty(event.taskRunId ?? "", "trace.taskRunId");
    requireNonEmpty(event.traceId, "traceId");
    requirePositiveVersion(event.traceVersion, "traceVersion");
    requireNonEmpty(event.sessionId, "trace.sessionId");
    requireHash(event.queryHash, "trace.queryHash");
    requireHash(event.finalPromptHash, "trace.finalPromptHash");
    requireNonEmpty(event.modelId, "trace.modelId");
    requireNonEmpty(event.modelVersion, "trace.modelVersion");
    requireHash(event.environmentHash, "trace.environmentHash");
    const exposureIds = new Set<string>();
    const useIds = new Set<string>();
    for (const access of event.accesses) {
      requireNonEmpty(access.accessId, "trace accessId");
      assertNodeRef(access.node);
      requireHash(access.recordDigest, `trace recordDigest:${access.accessId}`);
      requireNonEmpty(access.retrieval.retrievalId, `trace retrievalId:${access.accessId}`);
      requireIso(access.retrieval.retrievedAt, `trace retrievedAt:${access.accessId}`);
      requireHash(access.retrieval.queryHash, `trace retrieval queryHash:${access.accessId}`);
      if (access.retrieval.rank !== null && (!Number.isSafeInteger(access.retrieval.rank) || access.retrieval.rank < 1)) {
        throw new Error(`Invalid trace retrieval rank: ${access.accessId}`);
      }
      requireFiniteOrNull(access.retrieval.score, `trace retrieval score:${access.accessId}`);
      if (access.exposure === null) {
        if (access.notExposedReason === null || access.use !== null || access.highestObservedState !== "retrieved") {
          throw new Error(`Invalid retrieved-only trace access: ${access.accessId}`);
        }
      } else {
        if (access.notExposedReason !== null) throw new Error(`Exposed trace has notExposedReason: ${access.accessId}`);
        requireNonEmpty(access.exposure.exposureId, `trace exposureId:${access.accessId}`);
        if (exposureIds.has(access.exposure.exposureId)) throw new Error(`Duplicate trace exposureId ${access.exposure.exposureId}`);
        exposureIds.add(access.exposure.exposureId);
        requireIso(access.exposure.exposedAt, `trace exposedAt:${access.accessId}`);
        if (Date.parse(access.exposure.exposedAt) < Date.parse(access.retrieval.retrievedAt)) {
          throw new Error(`Trace exposure precedes retrieval: ${access.accessId}`);
        }
        requireHash(access.exposure.renderedHash, `trace renderedHash:${access.accessId}`);
        if (!Number.isSafeInteger(access.exposure.renderedChars) || access.exposure.renderedChars < 1) {
          throw new Error(`Invalid trace renderedChars: ${access.accessId}`);
        }
        const isL1 = access.node.layer === "L1";
        if (isL1 && access.exposure.channel !== "prompt_l1") throw new Error("L1 trace exposure must use prompt_l1");
        if (!isL1 && access.exposure.channel === "prompt_l1") throw new Error("L2 trace exposure cannot use prompt_l1");
        if (isL1 && access.exposure.derivationEdges.length > 0) throw new Error("L1 trace exposure cites derivation edges");
        access.exposure.derivationEdges.forEach((edge) => {
          requireNonEmpty(edge.edgeId, `trace derivation edge:${access.accessId}`);
          requirePositiveVersion(edge.edgeVersion, `trace derivation edgeVersion:${edge.edgeId}`);
        });
        assertUnique(access.exposure.derivationEdges, (edge) => `${edge.edgeId}\u001f${edge.edgeVersion}`, `trace edge:${access.accessId}`);
        if (access.use === null) {
          if (access.highestObservedState !== "exposed") throw new Error(`Trace state mismatch: ${access.accessId}`);
        } else {
          requireNonEmpty(access.use.useId, `trace useId:${access.accessId}`);
          if (useIds.has(access.use.useId)) throw new Error(`Duplicate trace useId ${access.use.useId}`);
          useIds.add(access.use.useId);
          requireIso(access.use.usedAt, `trace usedAt:${access.accessId}`);
          if (Date.parse(access.use.usedAt) < Date.parse(access.exposure.exposedAt)) {
            throw new Error(`Trace use precedes exposure: ${access.accessId}`);
          }
          if (access.use.evidence.length === 0 || access.highestObservedState !== "used") {
            throw new Error(`Trace used state lacks evidence: ${access.accessId}`);
          }
          access.use.evidence.forEach((evidence) => {
            requireNonEmpty(evidence.evidenceId, `trace use evidenceId:${access.accessId}`);
            requireHash(evidence.evidenceHash, `trace use evidenceHash:${access.accessId}`);
          });
          assertUnique(access.use.evidence, (evidence) => evidence.evidenceId, `trace use evidence:${access.accessId}`);
        }
      }
    }
    assertUnique(event.accesses, (access) => access.accessId, "trace access");
    assertUnique(event.accesses, (access) => access.retrieval.retrievalId, "trace retrievalId");
    requireHash(event.traceDigest, "traceDigest");
    const { traceDigest: _digest, eventId: _id, eventHash: _hash, ...rest } = event;
    const { schemaVersion: _schema, eventType: _type, captureId: _capture, capturedAt: _at,
      origin: _origin, feedbackDepth: _depth, taskRunId: _task, dataClassification: _class,
      memoryIngestionAllowed: _ingest, mayWriteProductionMemory: _write, mayEnqueueFeedback: _enqueue,
      feedbackReingestionEnabled: _reingest, optimizationReady: _ready, ...traceBody } = rest;
    if (canonicalHash(traceBody) !== event.traceDigest) throw new Error("Memory use trace digest mismatch");
  } else {
    throw new Error("Unknown capture event type");
  }
}

export function captureEventIdentity(event: ShadowCaptureEvent): string {
  if (event.eventType === "versioned_memory_record") return `record:${nodeKey(event.payload.record)}`;
  if (event.eventType === "materialized_l0_authority") return `authority:${event.authorityId}\u001f${event.authorityVersion}`;
  if (event.eventType === "aggregation_manifest") return `manifest:${event.manifestId}\u001f${event.manifestVersion}`;
  return `trace:${event.traceId}\u001f${event.traceVersion}`;
}

/** Digest used to distinguish an exact duplicate from an immutable identity conflict. */
export function captureEventIntegrityDigest(event: ShadowCaptureEvent): string {
  if (event.eventType === "versioned_memory_record") return event.payload.recordDigest;
  if (event.eventType === "materialized_l0_authority") return event.authorityDigest;
  if (event.eventType === "aggregation_manifest") return event.manifestDigest;
  return event.traceDigest;
}

/**
 * Audits whether a capture packet contains addressable evidence for later
 * canary fault localization. This does not manufacture a fault label or claim
 * that any captured memory is correct.
 */
export function auditCaptureCompleteness(events: ShadowCaptureEvent[]): CaptureCompletenessAudit {
  const errors = new Set<string>();
  const warnings = new Set<string>();
  const identityHashes = new Map<string, string>();
  for (const event of events) {
    try {
      assertShadowCaptureEvent(event);
    } catch (error) {
      errors.add(`invalid_event:${(error as Error).message}`);
      continue;
    }
    const identity = captureEventIdentity(event);
    const integrityDigest = captureEventIntegrityDigest(event);
    const existing = identityHashes.get(identity);
    if (existing && existing !== integrityDigest) errors.add(`immutable_identity_conflict:${identity}`);
    else if (existing) warnings.add(`duplicate_event:${identity}`);
    identityHashes.set(identity, integrityDigest);
  }
  const records = events.filter((event): event is VersionedMemoryRecord => event.eventType === "versioned_memory_record");
  const authorities = events.filter((event): event is MaterializedL0Authority => event.eventType === "materialized_l0_authority");
  const manifests = events.filter((event): event is AggregationManifest => event.eventType === "aggregation_manifest");
  const traces = events.filter((event): event is MemoryUseTrace => event.eventType === "memory_use_trace");
  const recordIndex = new Map(records.map((event) => [nodeKey(event.payload.record), event] as const));
  const authorityIndex = new Map<string, MaterializedL0Authority[]>();
  const authoritySourceDigests = new Map<string, string>();
  for (const authority of authorities) {
    const sourceKey = nodeKey(authority.source.record);
    const sourceDigest = canonicalHash(authority.source);
    const existingSourceDigest = authoritySourceDigests.get(sourceKey);
    if (existingSourceDigest && existingSourceDigest !== sourceDigest) {
      errors.add(`conflicting_l0_materialization:${sourceKey}`);
    }
    authoritySourceDigests.set(sourceKey, sourceDigest);
    authorityIndex.set(sourceKey, [...(authorityIndex.get(sourceKey) ?? []), authority]);
    for (const assertion of authority.assertions) {
      for (const supported of assertion.supports) {
        if (!recordIndex.has(nodeKey(supported))) {
          errors.add(`l0_authority_unknown_l1:${sourceKey}->${nodeKey(supported)}`);
        }
      }
    }
  }

  for (const record of records) {
    if (record.payload.record.layer === "L1") {
      if (record.payload.sourceL0.length === 0) warnings.add(`l1_without_l0_source:${nodeKey(record.payload.record)}`);
      for (const source of record.payload.sourceL0) {
        const sourceAuthorities = authorityIndex.get(nodeKey(source)) ?? [];
        if (sourceAuthorities.length === 0) {
          errors.add(`missing_materialized_l0:${nodeKey(source)}->${nodeKey(record.payload.record)}`);
          continue;
        }
        const supports = sourceAuthorities.some((authority) => authority.assertions.some((assertion) =>
          assertion.supports.some((ref) => nodeKey(ref) === nodeKey(record.payload.record))));
        if (!supports) errors.add(`l0_authority_missing_support_link:${nodeKey(source)}->${nodeKey(record.payload.record)}`);
        if (sourceAuthorities.every((authority) => !authority.source.eligibleForUserFactSupport)) {
          warnings.add(`assistant_only_source:${nodeKey(source)}->${nodeKey(record.payload.record)}`);
        }
      }
    }
    for (const predecessor of record.payload.predecessors) {
      const predecessorSnapshot = recordIndex.get(nodeKey(predecessor.record));
      if (!predecessorSnapshot) {
        errors.add(`missing_predecessor_snapshot:${nodeKey(predecessor.record)}->${nodeKey(record.payload.record)}`);
        continue;
      }
      if (record.payload.record.layer === "L2") {
        if (predecessorSnapshot.payload.scopeHash !== record.payload.scopeHash) {
          errors.add(`l2_supersedes_scope_mismatch:${nodeKey(predecessor.record)}->${nodeKey(record.payload.record)}`);
        }
        if (predecessorSnapshot.payload.entityBindingHash !== record.payload.entityBindingHash) {
          errors.add(`l2_supersedes_entity_binding_mismatch:${nodeKey(predecessor.record)}->${nodeKey(record.payload.record)}`);
        }
      }
    }
  }

  let derivationEdges = 0;
  const derivationEdgeDigests = new Map<string, string>();
  const manifestOutputs = new Set<string>();
  const manifestDigestByOutput = new Map<string, string>();
  const derivationEdgeIndex = new Map<string, ExactDerivationEdgeSnapshot>();
  for (const manifest of manifests) {
    const outputKey = nodeKey(manifest.output.record);
    manifestOutputs.add(outputKey);
    const priorManifestDigest = manifestDigestByOutput.get(outputKey);
    if (priorManifestDigest && priorManifestDigest !== manifest.manifestDigest) {
      errors.add(`conflicting_aggregation_manifests:${outputKey}`);
    }
    manifestDigestByOutput.set(outputKey, manifest.manifestDigest);
    const output = recordIndex.get(outputKey);
    if (!output) {
      errors.add(`missing_or_mismatched_l2_output:${outputKey}`);
    } else {
      if (output.payload.recordDigest !== manifest.output.recordDigest) {
        errors.add(`missing_or_mismatched_l2_output:${outputKey}`);
      }
      if (output.payload.logicalId !== manifest.output.logicalId) {
        errors.add(`mismatched_l2_logical_id:${outputKey}`);
      }
      if (output.payload.contentHash !== manifest.output.contentHash) {
        errors.add(`mismatched_l2_content_hash:${outputKey}`);
      }
      for (const claim of manifest.claims) {
        if (output.payload.content.slice(claim.span.start, claim.span.end) !== claim.text) {
          errors.add(`claim_output_span_mismatch:${manifest.manifestId}:${claim.claimId}`);
        }
      }
      const expectedCoverage = nonWhitespaceCoverage(output.payload.content, manifest.claims.map((claim) => claim.span));
      if (canonicalHash(expectedCoverage) !== canonicalHash(manifest.claimCoverage)) {
        errors.add(`claim_coverage_mismatch:${manifest.manifestId}@${manifest.manifestVersion}`);
      }
    }
    for (const frozen of manifest.frozenInputs.inputs) {
      const inputKey = nodeKey(frozen.record);
      const source = recordIndex.get(inputKey);
      if (!source) {
        errors.add(`missing_or_mismatched_l1_input:${inputKey}`);
        continue;
      }
      if (source.payload.recordDigest !== frozen.recordDigest) {
        errors.add(`missing_or_mismatched_l1_input:${inputKey}`);
      }
      if (source.payload.logicalId !== frozen.logicalId) {
        errors.add(`mismatched_l1_logical_id:${inputKey}`);
      }
      if (source.payload.contentHash !== frozen.contentHash) {
        errors.add(`mismatched_l1_content_hash:${inputKey}`);
      }
      if (source.payload.scopeHash !== frozen.scopeHash) {
        errors.add(`mismatched_l1_scope_hash:${inputKey}`);
      }
      if (source.payload.entityBindingHash !== frozen.entityBindingHash) {
        errors.add(`mismatched_l1_entity_binding_hash:${inputKey}`);
      }
    }
    if (!manifest.claimCoverage.complete) warnings.add(`incomplete_claim_coverage:${manifest.manifestId}@${manifest.manifestVersion}`);
    for (const claim of manifest.claims) {
      if (claim.lineageStatus === "unattributed") {
        errors.add(`unattributed_l2_claim:${manifest.manifestId}:${claim.claimId}`);
      }
    }
    for (const edge of manifest.edges) {
      const edgeIdentity = `${edge.edgeId}\u001f${edge.version}`;
      const edgeDigest = canonicalHash(edge);
      const existing = derivationEdgeDigests.get(edgeIdentity);
      if (existing && existing !== edgeDigest) errors.add(`immutable_derivation_edge_conflict:${edgeIdentity}`);
      derivationEdgeDigests.set(edgeIdentity, edgeDigest);
      derivationEdgeIndex.set(edgeIdentity, edge);
    }
    derivationEdges += manifest.edges.length;
  }
  for (const record of records.filter((event) => event.payload.record.layer === "L2")) {
    if (!manifestOutputs.has(nodeKey(record.payload.record))) {
      errors.add(`l2_without_aggregation_manifest:${nodeKey(record.payload.record)}`);
    }
  }

  let accesses = 0;
  for (const trace of traces) {
    accesses += trace.accesses.length;
    for (const access of trace.accesses) {
      const record = recordIndex.get(nodeKey(access.node));
      if (!record || record.payload.recordDigest !== access.recordDigest) {
        errors.add(`trace_unknown_record_version:${trace.traceId}:${nodeKey(access.node)}`);
      }
      if (access.node.layer === "L2" && access.exposure) {
        if (access.exposure.derivationEdges.length === 0) {
          warnings.add(`l2_exposure_without_edge_refs:${trace.traceId}:${access.exposure.exposureId}`);
        }
        for (const edgeRef of access.exposure.derivationEdges) {
          const edge = derivationEdgeIndex.get(`${edgeRef.edgeId}\u001f${edgeRef.edgeVersion}`);
          if (!edge || nodeKey(edge.to) !== nodeKey(access.node)) {
            errors.add(`trace_unknown_derivation_edge:${trace.traceId}:${edgeRef.edgeId}@${edgeRef.edgeVersion}`);
          }
        }
      }
    }
  }

  const exactNodeIdentityReady = records.length > 0 && ![...errors].some((item) =>
    item.startsWith("invalid_event:") || item.startsWith("immutable_identity_conflict:")
    || item.startsWith("missing_predecessor_snapshot:") || item.startsWith("l2_supersedes_scope_mismatch:")
    || item.startsWith("l2_supersedes_entity_binding_mismatch:"));
  const roleCorrectL0Ready = authorities.length > 0 && ![...errors].some((item) =>
    item.startsWith("missing_materialized_l0:") || item.startsWith("l0_authority_missing_support_link:")
    || item.startsWith("l0_authority_unknown_l1:") || item.startsWith("conflicting_l0_materialization:"));
  const exactDerivationReady = manifests.length > 0 && derivationEdges > 0 && ![...errors].some((item) =>
    item.startsWith("missing_or_mismatched_l2_output:") || item.startsWith("missing_or_mismatched_l1_input:")
    || item.startsWith("mismatched_l2_logical_id:") || item.startsWith("mismatched_l2_content_hash:")
    || item.startsWith("mismatched_l1_logical_id:") || item.startsWith("mismatched_l1_content_hash:")
    || item.startsWith("mismatched_l1_scope_hash:") || item.startsWith("mismatched_l1_entity_binding_hash:")
    || item.startsWith("conflicting_aggregation_manifests:") || item.startsWith("claim_output_span_mismatch:")
    || item.startsWith("claim_coverage_mismatch:") || item.startsWith("immutable_derivation_edge_conflict:")
    || item.startsWith("l2_without_aggregation_manifest:") || item.startsWith("unattributed_l2_claim:"))
    && ![...warnings].some((item) => item.startsWith("incomplete_claim_coverage:"));
  const runtimeAttributionReady = traces.length > 0 && accesses > 0 && ![...errors].some((item) =>
    item.startsWith("trace_unknown_record_version:") || item.startsWith("trace_unknown_derivation_edge:"));
  const sortedErrors = [...errors].sort();
  const sortedWarnings = [...warnings].sort();
  return cloneFreeze({
    schemaVersion: "tdai-capture-completeness-audit.v1",
    eventSetHash: canonicalHash(events.map((event) => event.eventHash).sort()),
    exactLocalizationCaptureReady:
      exactNodeIdentityReady && roleCorrectL0Ready && exactDerivationReady && runtimeAttributionReady
      && sortedErrors.length === 0,
    exactNodeIdentityReady,
    roleCorrectL0Ready,
    exactDerivationReady,
    runtimeAttributionReady,
    counts: {
      records: records.length,
      authorities: authorities.length,
      manifests: manifests.length,
      traces: traces.length,
      derivationEdges,
      accesses,
    },
    errors: sortedErrors,
    warnings: sortedWarnings,
    safety: {
      shadowOnly: true,
      feedbackDepth: 0,
      memoryIngestionAllowed: false,
      mayWriteProductionMemory: false,
      mayEnqueueFeedback: false,
      optimizationReady: false,
    },
  });
}
