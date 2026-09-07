import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import type {
  LayerExposure,
  MemoryFeedbackTarget,
  MemoryGraphSnapshot,
  MemoryRelevanceAuthorityRef,
  MemoryRelevanceObservation,
  MemoryNodeRef,
  RootObservation,
  RootObservationInput,
  ShadowExecutionContext,
  ShadowExecutorSafetyDeclaration,
  ShadowObservationEvent,
  ShadowReplayAuditEvent,
  ShadowReplayResult,
  TaskOutcomeObservation,
} from "./types.js";

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    const row = value as Record<string, unknown>;
    return Object.fromEntries(Object.keys(row).sort().map((key) => [key, canonicalize(row[key])]));
  }
  return value;
}

export function canonicalHash(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(canonicalize(value)), "utf8").digest("hex");
}

function deepFreeze<T>(value: T, seen = new Set<object>()): T {
  if (!value || typeof value !== "object" || seen.has(value as object)) return value;
  seen.add(value as object);
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function requireNonEmpty(value: string, field: string): void {
  if (!value.trim()) throw new Error(`${field} is required`);
}

function requireSha256(value: string, field: string): void {
  if (!/^[a-f0-9]{64}$/i.test(value)) throw new Error(`${field} must be a SHA-256 digest`);
}

export function memoryRelevanceSubjectBindingHash(input: {
  taskRunId: string;
  sessionId: string;
  preRetrievalContextHash: string;
  authority: MemoryRelevanceAuthorityRef | null;
}): string {
  return canonicalHash({
    taskRunId: input.taskRunId,
    sessionId: input.sessionId,
    preRetrievalContextHash: input.preRetrievalContextHash,
    authority: input.authority ? {
      authorityId: input.authority.authorityId,
      authorityVersion: input.authority.authorityVersion,
      effectiveAt: input.authority.effectiveAt,
      authoritySnapshotDigest: input.authority.authoritySnapshotDigest,
    } : null,
  });
}

function nodeKey(ref: MemoryNodeRef): string {
  return `${ref.layer}\u001f${ref.id}\u001f${ref.version}`;
}

function assertVersion(version: number, field: string): void {
  if (!Number.isSafeInteger(version) || version < 0) throw new Error(`${field} must be a non-negative integer`);
}

function assertPositiveVersion(version: number, field: string): void {
  if (!Number.isSafeInteger(version) || version < 1) throw new Error(`${field} must be a positive integer`);
}

function normalizeGraph(graph: MemoryGraphSnapshot): MemoryGraphSnapshot {
  return {
    nodes: graph.nodes.map((node) => ({
      layer: node.layer,
      id: node.id,
      version: node.version,
      contentHash: node.contentHash,
      metadataHash: node.metadataHash,
      scopeHash: node.scopeHash,
      entityBindingHash: node.entityBindingHash,
      observedAt: node.observedAt,
    })),
    edges: graph.edges.map((edge) => ({
      edgeId: edge.edgeId,
      version: edge.version,
      relation: edge.relation,
      from: { layer: edge.from.layer, id: edge.from.id, version: edge.from.version },
      to: { layer: edge.to.layer, id: edge.to.id, version: edge.to.version },
      metadataHash: edge.metadataHash,
    })),
  };
}

function normalizeExposures(exposures: LayerExposure[]): LayerExposure[] {
  return exposures.map((exposure) => ({
    exposureId: exposure.exposureId,
    node: { layer: exposure.node.layer, id: exposure.node.id, version: exposure.node.version },
    state: exposure.state,
    channel: exposure.channel,
    rank: exposure.rank,
    score: exposure.score,
    renderedHash: exposure.renderedHash,
    truncated: exposure.truncated,
    derivationEdges: exposure.derivationEdges.map((edge) => ({
      edgeId: edge.edgeId,
      edgeVersion: edge.edgeVersion,
    })),
  }));
}

function normalizeMemoryRelevance(relevance: MemoryRelevanceObservation): MemoryRelevanceObservation {
  return {
    schemaVersion: "tdai-memory-relevance.v1",
    decision: relevance.decision,
    basis: relevance.basis,
    evaluatorId: relevance.evaluatorId,
    evaluatorVersion: relevance.evaluatorVersion,
    evaluatorDigest: relevance.evaluatorDigest,
    policyDigest: relevance.policyDigest,
    evaluatedAt: relevance.evaluatedAt,
    evidenceHash: relevance.evidenceHash,
    authority: relevance.authority ? {
      authorityId: relevance.authority.authorityId,
      authorityVersion: relevance.authority.authorityVersion,
      effectiveAt: relevance.authority.effectiveAt,
      authoritySnapshotDigest: relevance.authority.authoritySnapshotDigest,
    } : null,
    calibrationArtifactDigest: relevance.calibrationArtifactDigest,
    subjectBindingHash: relevance.subjectBindingHash,
    independentOfProductionRetrieval: true,
    evaluationSurface: "pre_retrieval_subject_and_authority_only",
  };
}

function normalizeOutcome(outcome: TaskOutcomeObservation | null): TaskOutcomeObservation | null {
  if (!outcome) return null;
  return {
    status: outcome.status,
    outputHash: outcome.outputHash,
    environmentHash: outcome.environmentHash,
    modelId: outcome.modelId,
    validators: outcome.validators.map((validator) => ({
      validatorId: validator.validatorId,
      validatorVersion: validator.validatorVersion,
      oracleKind: validator.oracleKind,
      status: validator.status,
      score: validator.score,
      evidenceHash: validator.evidenceHash,
    })),
  };
}

function edgeKey(ref: { edgeId: string; edgeVersion: number }): string {
  return `${ref.edgeId}\u001f${ref.edgeVersion}`;
}

export function assertMemoryGraph(graph: MemoryGraphSnapshot): void {
  const nodeKeys = new Set<string>();
  for (const node of graph.nodes) {
    requireNonEmpty(node.id, "node.id");
    assertVersion(node.version, `node.version:${node.id}`);
    requireNonEmpty(node.contentHash, `node.contentHash:${node.id}`);
    requireNonEmpty(node.metadataHash, `node.metadataHash:${node.id}`);
    requireNonEmpty(node.scopeHash, `node.scopeHash:${node.id}`);
    requireNonEmpty(node.entityBindingHash, `node.entityBindingHash:${node.id}`);
    const key = nodeKey(node);
    if (nodeKeys.has(key)) throw new Error(`Duplicate graph node ${key}`);
    nodeKeys.add(key);
  }

  const edgeKeys = new Set<string>();
  for (const edge of graph.edges) {
    requireNonEmpty(edge.edgeId, "edge.edgeId");
    assertVersion(edge.version, `edge.version:${edge.edgeId}`);
    const key = `${edge.edgeId}\u001f${edge.version}`;
    if (edgeKeys.has(key)) throw new Error(`Duplicate graph edge ${key}`);
    edgeKeys.add(key);
    if (!nodeKeys.has(nodeKey(edge.from))) throw new Error(`Edge ${edge.edgeId} has unknown from endpoint`);
    if (!nodeKeys.has(nodeKey(edge.to))) throw new Error(`Edge ${edge.edgeId} has unknown to endpoint`);
    if (edge.relation === "L0_SUPPORTS_L1" && (edge.from.layer !== "L0" || edge.to.layer !== "L1")) {
      throw new Error(`Edge ${edge.edgeId} violates L0_SUPPORTS_L1 layer contract`);
    }
    if (edge.relation === "L1_DERIVES_L2" && (edge.from.layer !== "L1" || edge.to.layer !== "L2")) {
      throw new Error(`Edge ${edge.edgeId} violates L1_DERIVES_L2 layer contract`);
    }
    if (edge.relation === "L1_SUPERSEDES_L1" && (edge.from.layer !== "L1" || edge.to.layer !== "L1")) {
      throw new Error(`Edge ${edge.edgeId} violates L1_SUPERSEDES_L1 layer contract`);
    }
    if (edge.relation === "L2_SUPERSEDES_L2" && (edge.from.layer !== "L2" || edge.to.layer !== "L2")) {
      throw new Error(`Edge ${edge.edgeId} violates L2_SUPERSEDES_L2 layer contract`);
    }
  }
}

function assertExposures(graph: MemoryGraphSnapshot, exposures: LayerExposure[]): void {
  const nodes = new Set(graph.nodes.map(nodeKey));
  const edges = new Map(graph.edges.map((edge) => [edgeKey({ edgeId: edge.edgeId, edgeVersion: edge.version }), edge] as const));
  const exposureIds = new Set<string>();
  for (const exposure of exposures) {
    requireNonEmpty(exposure.exposureId, "exposure.exposureId");
    if (exposureIds.has(exposure.exposureId)) throw new Error(`Duplicate exposure ${exposure.exposureId}`);
    exposureIds.add(exposure.exposureId);
    if (!nodes.has(nodeKey(exposure.node))) {
      throw new Error(`Exposure ${exposure.exposureId} references an unknown node version`);
    }
    if (exposure.state !== "retrieved" && !exposure.renderedHash) {
      throw new Error(`Exposed/used memory ${exposure.exposureId} requires renderedHash`);
    }
    if (exposure.state === "retrieved" && exposure.channel === "l2_file_read") {
      throw new Error(`L2 file reads must be exposed or used: ${exposure.exposureId}`);
    }
    for (const edgeRef of exposure.derivationEdges) {
      requireNonEmpty(edgeRef.edgeId, `exposure.derivationEdges.edgeId:${exposure.exposureId}`);
      assertPositiveVersion(edgeRef.edgeVersion, `exposure.derivationEdges.edgeVersion:${edgeRef.edgeId}`);
      const edge = edges.get(edgeKey(edgeRef));
      if (!edge || edge.relation !== "L1_DERIVES_L2") {
        throw new Error(
          `Exposure ${exposure.exposureId} references invalid derivation edge ${edgeRef.edgeId}@${edgeRef.edgeVersion}`,
        );
      }
      if (exposure.node.layer !== "L2" || nodeKey(edge.to) !== nodeKey(exposure.node)) {
        throw new Error(`Derivation edge ${edgeRef.edgeId}@${edgeRef.edgeVersion} does not derive exposed L2 node`);
      }
    }
  }
}

export function assertFeedbackTarget(graph: MemoryGraphSnapshot, target: MemoryFeedbackTarget): void {
  assertPositiveVersion(target.targetVersion, "feedback target version");
  if (target.targetType === "L1_NODE" || target.targetType === "L2_NODE") {
    const layer = target.targetType === "L1_NODE" ? "L1" : "L2";
    const exists = graph.nodes.some(
      (node) => node.layer === layer && node.id === target.targetId && node.version === target.targetVersion,
    );
    if (!exists) throw new Error(`Unknown ${target.targetType} target ${target.targetId}@${target.targetVersion}`);
    return;
  }
  const edge = graph.edges.find(
    (candidate) => candidate.edgeId === target.targetId && candidate.version === target.targetVersion,
  );
  if (!edge || edge.relation !== "L1_DERIVES_L2") {
    throw new Error(`Unknown L1_L2_EDGE target ${target.targetId}@${target.targetVersion}`);
  }
  assertPositiveVersion(target.from.version, "feedback edge from.version");
  assertPositiveVersion(target.to.version, "feedback edge to.version");
  if (nodeKey(edge.from) !== nodeKey(target.from) || nodeKey(edge.to) !== nodeKey(target.to)) {
    throw new Error(`L1_L2_EDGE target endpoints do not match ${target.targetId}`);
  }
}

export function createRootObservation(input: RootObservationInput, recordedAt: string): RootObservation {
  if (input.origin !== "production" && input.origin !== "benchmark_fault_injection") {
    throw new Error("Root observation origin must be production or benchmark_fault_injection");
  }
  if (input.feedbackDepth !== 0) throw new Error("Root observation feedbackDepth must be 0");
  if (!Number.isFinite(Date.parse(recordedAt))) throw new Error("recordedAt must be an ISO-compatible timestamp");
  requireNonEmpty(input.taskRunId, "taskRunId");
  requireNonEmpty(input.sessionId, "sessionId");
  requireNonEmpty(input.preRetrievalContextHash, "preRetrievalContextHash");
  requireNonEmpty(input.contextHash, "contextHash");
  requireSha256(input.preRetrievalContextHash, "preRetrievalContextHash");
  requireSha256(input.contextHash, "contextHash");
  if (input.memoryRelevance.schemaVersion !== "tdai-memory-relevance.v1") {
    throw new Error("Unsupported Memory relevance schema");
  }
  if (!(["memory_relevant", "no_match", "unknown"] as unknown[]).includes(input.memoryRelevance.decision)) {
    throw new Error("Unsupported Memory relevance decision");
  }
  if (!([
    "deterministic_task_contract", "objective_oracle", "calibrated_no_match_model", "unavailable",
  ] as unknown[]).includes(input.memoryRelevance.basis)) {
    throw new Error("Unsupported Memory relevance basis");
  }
  if (input.memoryRelevance.independentOfProductionRetrieval !== true) {
    throw new Error("Memory relevance must be evaluated independently of production retrieval");
  }
  if (input.memoryRelevance.evaluationSurface !== "pre_retrieval_subject_and_authority_only") {
    throw new Error("Memory relevance evaluator received a forbidden input surface");
  }
  requireNonEmpty(input.memoryRelevance.evaluatorId, "memoryRelevance.evaluatorId");
  requireNonEmpty(input.memoryRelevance.evaluatorVersion, "memoryRelevance.evaluatorVersion");
  requireSha256(input.memoryRelevance.evaluatorDigest, "memoryRelevance.evaluatorDigest");
  requireSha256(input.memoryRelevance.policyDigest, "memoryRelevance.policyDigest");
  requireSha256(input.memoryRelevance.subjectBindingHash, "memoryRelevance.subjectBindingHash");
  if (!Number.isFinite(Date.parse(input.memoryRelevance.evaluatedAt))) {
    throw new Error("memoryRelevance.evaluatedAt must be an ISO-compatible timestamp");
  }
  if (input.memoryRelevance.decision === "unknown") {
    if (
      input.memoryRelevance.basis !== "unavailable"
      || input.memoryRelevance.evidenceHash !== null
      || input.memoryRelevance.authority !== null
      || input.memoryRelevance.calibrationArtifactDigest !== null
    ) {
      throw new Error("Unknown Memory relevance must carry no authority, evidence, or calibration claim");
    }
  } else {
    if (input.memoryRelevance.basis === "unavailable") {
      throw new Error("A decided Memory relevance observation requires an evaluator basis");
    }
    if (!input.memoryRelevance.evidenceHash) {
      throw new Error("A decided Memory relevance observation requires evidenceHash");
    }
    requireSha256(input.memoryRelevance.evidenceHash, "memoryRelevance.evidenceHash");
    const authority = input.memoryRelevance.authority;
    if (!authority) throw new Error("A decided Memory relevance observation requires authority");
    requireNonEmpty(authority.authorityId, "memoryRelevance.authority.authorityId");
    requireNonEmpty(authority.authorityVersion, "memoryRelevance.authority.authorityVersion");
    if (!Number.isFinite(Date.parse(authority.effectiveAt))) {
      throw new Error("memoryRelevance.authority.effectiveAt must be an ISO-compatible timestamp");
    }
    if (Date.parse(authority.effectiveAt) > Date.parse(input.memoryRelevance.evaluatedAt)) {
      throw new Error("Memory relevance authority cannot become effective after evaluation");
    }
    requireSha256(authority.authoritySnapshotDigest, "memoryRelevance.authority.authoritySnapshotDigest");
    if (input.memoryRelevance.basis === "calibrated_no_match_model") {
      if (!input.memoryRelevance.calibrationArtifactDigest) {
        throw new Error("Model-based Memory relevance requires a calibration artifact digest");
      }
      requireSha256(
        input.memoryRelevance.calibrationArtifactDigest,
        "memoryRelevance.calibrationArtifactDigest",
      );
    } else if (input.memoryRelevance.calibrationArtifactDigest !== null) {
      throw new Error("Non-model Memory relevance cannot claim a calibration artifact");
    }
  }
  const expectedRelevanceBinding = memoryRelevanceSubjectBindingHash({
    taskRunId: input.taskRunId,
    sessionId: input.sessionId,
    preRetrievalContextHash: input.preRetrievalContextHash,
    authority: input.memoryRelevance.authority,
  });
  if (input.memoryRelevance.subjectBindingHash !== expectedRelevanceBinding) {
    throw new Error("Memory relevance input binding does not match the root task/context/authority");
  }
  assertMemoryGraph(input.graph);
  assertExposures(input.graph, input.exposures);
  const graph = normalizeGraph(input.graph);
  const exposures = normalizeExposures(input.exposures);
  const memoryRelevance = normalizeMemoryRelevance(input.memoryRelevance);
  const outcome = normalizeOutcome(input.outcome);
  const graphSnapshotHash = canonicalHash(graph);
  const dedupeKey = canonicalHash({
    taskRunId: input.taskRunId,
    preRetrievalContextHash: input.preRetrievalContextHash,
    contextHash: input.contextHash,
    memoryRelevance,
    graphSnapshotHash,
    exposures: exposures.map((item) => item.exposureId).sort(),
  });
  return deepFreeze({
    schemaVersion: "tdai-shadow-observation.v2",
    eventType: "root_observation",
    observationId: `obs-${dedupeKey.slice(0, 24)}`,
    recordedAt,
    graphSnapshotHash,
    dedupeKey,
    dataClassification: "shadow_telemetry",
    memoryIngestionAllowed: false,
    mayEnqueueFeedback: true,
    origin: input.origin,
    feedbackDepth: 0,
    taskRunId: input.taskRunId,
    sessionId: input.sessionId,
    preRetrievalContextHash: input.preRetrievalContextHash,
    contextHash: input.contextHash,
    memoryRelevance,
    graph,
    exposures,
    outcome,
  });
}

/** Revalidates deserialized or externally supplied roots before any gate uses them. */
export function assertRootObservation(observation: RootObservation): void {
  if (
    observation.schemaVersion !== "tdai-shadow-observation.v2"
    || observation.eventType !== "root_observation"
    || observation.dataClassification !== "shadow_telemetry"
    || observation.memoryIngestionAllowed !== false
    || observation.mayEnqueueFeedback !== true
  ) {
    throw new Error("Root observation violates the v2 shadow-only envelope");
  }
  const rebuilt = createRootObservation({
    origin: observation.origin,
    feedbackDepth: observation.feedbackDepth,
    taskRunId: observation.taskRunId,
    sessionId: observation.sessionId,
    preRetrievalContextHash: observation.preRetrievalContextHash,
    contextHash: observation.contextHash,
    memoryRelevance: observation.memoryRelevance,
    graph: observation.graph,
    exposures: observation.exposures,
    outcome: observation.outcome,
  }, observation.recordedAt);
  if (canonicalHash(observation) !== canonicalHash(rebuilt)) {
    throw new Error("Root observation integrity or strict-schema check failed");
  }
}

export function createShadowExecutionContext(parentObservationId: string): ShadowExecutionContext {
  requireNonEmpty(parentObservationId, "parentObservationId");
  return {
    origin: "self_supervision",
    parentObservationId,
    feedbackDepth: 1,
    recallEnabled: false,
    captureEnabled: false,
    memoryWriteEnabled: false,
    feedbackReingestionEnabled: false,
  };
}

export function assertShadowExecutionContext(context: ShadowExecutionContext): void {
  if (
    context.origin !== "self_supervision"
    || context.feedbackDepth !== 1
    || context.recallEnabled !== false
    || context.captureEnabled !== false
    || context.memoryWriteEnabled !== false
    || context.feedbackReingestionEnabled !== false
  ) {
    throw new Error("Unsafe or recursive shadow execution context");
  }
  requireNonEmpty(context.parentObservationId, "parentObservationId");
}

export function assertExecutorSafety(safety: ShadowExecutorSafetyDeclaration): void {
  if (
    safety.isolatedState !== true
    || safety.productionMemoryReadOnly !== true
    || safety.recallEnabled !== false
    || safety.captureEnabled !== false
    || safety.memoryWriteEnabled !== false
    || safety.feedbackReingestionEnabled !== false
  ) {
    throw new Error("Shadow executor does not satisfy the non-recursive safety contract");
  }
}

export interface ShadowObservationStore {
  has(dedupeKey: string): Promise<boolean>;
  append(event: ShadowObservationEvent): Promise<void>;
}

export class InMemoryShadowObservationStore implements ShadowObservationStore {
  readonly events: ShadowObservationEvent[] = [];
  private readonly keys = new Set<string>();

  async has(dedupeKey: string): Promise<boolean> {
    return this.keys.has(dedupeKey);
  }

  async append(event: ShadowObservationEvent): Promise<void> {
    if (this.keys.has(event.dedupeKey)) throw new Error(`Duplicate observation event ${event.dedupeKey}`);
    this.events.push(structuredClone(event));
    this.keys.add(event.dedupeKey);
  }
}

export class JsonlShadowObservationStore implements ShadowObservationStore {
  readonly filePath: string;
  private readonly keys = new Set<string>();

  constructor(rootDirectory: string, fileName = "shadow-observations.v2.jsonl") {
    if (!rootDirectory.trim()) throw new Error("Observation root directory is required");
    if (!/^[a-zA-Z0-9._-]+\.jsonl$/.test(fileName)) {
      throw new Error("Observation filename must be a plain .jsonl basename");
    }
    mkdirSync(rootDirectory, { recursive: true, mode: 0o700 });
    this.filePath = resolve(rootDirectory, fileName);
    try {
      const raw = readFileSync(this.filePath, "utf8");
      for (const [index, line] of raw.split("\n").filter(Boolean).entries()) {
        const event = JSON.parse(line) as Partial<ShadowObservationEvent>;
        if (!event.dedupeKey || event.memoryIngestionAllowed !== false) {
          throw new Error(`Malformed observation row ${index + 1}`);
        }
        this.keys.add(event.dedupeKey);
      }
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
  }

  async has(dedupeKey: string): Promise<boolean> {
    return this.keys.has(dedupeKey);
  }

  async append(event: ShadowObservationEvent): Promise<void> {
    if (event.memoryIngestionAllowed !== false) throw new Error("Observation plane output cannot enter Memory ingestion");
    if (this.keys.has(event.dedupeKey)) throw new Error(`Duplicate observation event ${event.dedupeKey}`);
    appendFileSync(this.filePath, `${JSON.stringify(event)}\n`, { encoding: "utf8", mode: 0o600 });
    this.keys.add(event.dedupeKey);
  }
}

export interface ObservationCollectResult {
  accepted: boolean;
  duplicate: boolean;
  observation: RootObservation;
}

export class LayerObservationPlane {
  constructor(
    private readonly store: ShadowObservationStore,
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async collect(input: RootObservationInput): Promise<ObservationCollectResult> {
    const observation = createRootObservation(input, this.now());
    if (await this.store.has(observation.dedupeKey)) {
      return { accepted: false, duplicate: true, observation };
    }
    await this.store.append(observation);
    return { accepted: true, duplicate: false, observation };
  }

  async recordReplay(
    parent: RootObservation,
    executionContext: ShadowExecutionContext,
    result: ShadowReplayResult,
  ): Promise<ShadowReplayAuditEvent> {
    assertShadowExecutionContext(executionContext);
    if (executionContext.parentObservationId !== parent.observationId) {
      throw new Error("Replay context does not belong to the parent observation");
    }
    if (result.traceId !== parent.observationId && result.traceId !== parent.taskRunId) {
      throw new Error("Replay result is not bound to the parent observation/task run");
    }
    const dedupeKey = canonicalHash({ parentObservationId: parent.observationId, snapshotId: result.snapshotId });
    const event: ShadowReplayAuditEvent = {
      schemaVersion: "tdai-shadow-observation.v2",
      eventType: "shadow_replay_result",
      replayEventId: `replay-${dedupeKey.slice(0, 24)}`,
      parentObservationId: parent.observationId,
      recordedAt: this.now(),
      dedupeKey,
      executionContext: structuredClone(executionContext),
      result: structuredClone(result),
      dataClassification: "shadow_telemetry",
      memoryIngestionAllowed: false,
      mayEnqueueFeedback: false,
    };
    if (!(await this.store.has(dedupeKey))) await this.store.append(event);
    return event;
  }
}
