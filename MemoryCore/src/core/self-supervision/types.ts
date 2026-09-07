export type MemoryValidity = "supported" | "refuted" | "expired" | "unverifiable";
export type MemoryUtility = "helpful" | "harmful" | "redundant" | "untested";
export type MemoryFailureOwner =
  | "memory_content"
  | "derivation"
  | "retrieval"
  | "use"
  | "model"
  | "tool"
  | "environment"
  | "unknown";
export type SignalDecision = "emit" | "abstain";
export type SignalFaultType =
  | "direct_update"
  | "propagated_invalidation"
  | "retrieval_scope"
  | "representation"
  | "environment_failure"
  | "unknown";

/** Layer-aware protocol used by the multi-layer shadow observation plane. */
export type MemoryLayer = "L0" | "L1" | "L2";
export type FeedbackTargetType = "L1_NODE" | "L2_NODE" | "L1_L2_EDGE";
export type LayerFaultType =
  | "unsupported_content"
  | "stale_or_conflicting"
  | "wrong_scope"
  | "wrong_entity_binding"
  | "retrieval_mismatch"
  | "incorrect_abstraction"
  | "missing_constraint"
  | "over_generalization"
  | "broken_derivation"
  | "task_harmful"
  | "environment_or_model_failure"
  | "insufficient_evidence";

export type SuggestedAction =
  | "retain"
  | "quarantine_candidate"
  | "replace_candidate"
  | "repair_scope"
  | "repair_entity_binding"
  | "repair_retrieval"
  | "rederive_l2"
  | "repair_derivation"
  | "no_action";

export interface MemoryNodeRef {
  layer: MemoryLayer;
  id: string;
  version: number;
}

export interface L1NodeTarget {
  targetType: "L1_NODE";
  targetId: string;
  targetVersion: number;
}

export interface L2NodeTarget {
  targetType: "L2_NODE";
  targetId: string;
  targetVersion: number;
}

export interface L1L2EdgeTarget {
  targetType: "L1_L2_EDGE";
  /** Stable edge ID, not either endpoint's ID. */
  targetId: string;
  targetVersion: number;
  from: MemoryNodeRef & { layer: "L1" };
  to: MemoryNodeRef & { layer: "L2" };
}

export type MemoryFeedbackTarget = L1NodeTarget | L2NodeTarget | L1L2EdgeTarget;

/** The complete unit that must be identifiable before an exact signal may emit. */
export interface CompleteFeedbackTuple {
  target: MemoryFeedbackTarget;
  faultType: LayerFaultType;
  suggestedAction: SuggestedAction;
}

export type IdentifiabilityBasis = "capture_authority" | "deterministic_graph" | "objective_oracle";
export type IdentifiabilityStatus = "identified" | "ambiguous" | "insufficient_evidence";

export interface LayerMemoryNode extends MemoryNodeRef {
  contentHash: string;
  metadataHash: string;
  scopeHash: string;
  entityBindingHash: string;
  observedAt: string;
}

export type MemoryRelation =
  | "L0_SUPPORTS_L1"
  | "L1_SUPERSEDES_L1"
  | "L1_DERIVES_L2"
  | "L2_SUPERSEDES_L2";

export interface MemoryGraphEdge {
  edgeId: string;
  version: number;
  relation: MemoryRelation;
  from: MemoryNodeRef;
  to: MemoryNodeRef;
  metadataHash: string;
}

export interface MemoryGraphSnapshot {
  nodes: LayerMemoryNode[];
  edges: MemoryGraphEdge[];
}

/** Version is mandatory because one stable edge ID may have several revisions. */
export interface VersionedDerivationEdgeRef {
  edgeId: string;
  edgeVersion: number;
}

export type ExposureState = "retrieved" | "exposed" | "used";
export type ExposureChannel = "prompt_l1" | "system_l2_navigation" | "l2_file_read";

export interface LayerExposure {
  exposureId: string;
  node: MemoryNodeRef & { layer: "L1" | "L2" };
  state: ExposureState;
  channel: ExposureChannel;
  rank: number | null;
  score: number | null;
  renderedHash: string | null;
  truncated: boolean;
  /** Exact derivation edges known to have supplied the exposed L2 content. */
  derivationEdges: VersionedDerivationEdgeRef[];
}

export type MemoryRelevanceDecision = "memory_relevant" | "no_match" | "unknown";
export type MemoryRelevanceBasis =
  | "deterministic_task_contract"
  | "objective_oracle"
  | "calibrated_no_match_model"
  | "unavailable";

export interface MemoryRelevanceAuthorityRef {
  authorityId: string;
  authorityVersion: string;
  effectiveAt: string;
  authoritySnapshotDigest: string;
}

/**
 * Independent no-match/relevance observation for Gate 0. It must not be
 * reconstructed from the production retriever's candidate count or score.
 */
export interface MemoryRelevanceObservation {
  schemaVersion: "tdai-memory-relevance.v1";
  decision: MemoryRelevanceDecision;
  basis: MemoryRelevanceBasis;
  evaluatorId: string;
  evaluatorVersion: string;
  evaluatorDigest: string;
  policyDigest: string;
  evaluatedAt: string;
  evidenceHash: string | null;
  authority: MemoryRelevanceAuthorityRef | null;
  calibrationArtifactDigest: string | null;
  /** H(taskRunId, sessionId, pre-retrieval context, complete authority ref); checked by the root builder. */
  subjectBindingHash: string;
  independentOfProductionRetrieval: true;
  evaluationSurface: "pre_retrieval_subject_and_authority_only";
}

export interface ValidatorObservation {
  validatorId: string;
  validatorVersion: string;
  oracleKind: "exact" | "schema" | "database" | "compiler" | "test" | "constraint" | "blind_judge";
  status: "pass" | "fail" | "error" | "unverifiable";
  score: number | null;
  evidenceHash: string;
}

export interface TaskOutcomeObservation {
  status: "success" | "failure" | "partial" | "unknown";
  outputHash: string;
  environmentHash: string;
  modelId: string;
  validators: ValidatorObservation[];
}

/**
 * A root observation may only come from a production task or an offline benchmark.
 * Self-supervision/replay output is deliberately not a valid origin here.
 */
export interface RootObservationInput {
  origin: "production" | "benchmark_fault_injection";
  feedbackDepth: 0;
  taskRunId: string;
  sessionId: string;
  /** Hash of task/query context before any production Memory retrieval result is available. */
  preRetrievalContextHash: string;
  contextHash: string;
  memoryRelevance: MemoryRelevanceObservation;
  graph: MemoryGraphSnapshot;
  exposures: LayerExposure[];
  outcome: TaskOutcomeObservation | null;
}

export interface RootObservation extends RootObservationInput {
  schemaVersion: "tdai-shadow-observation.v2";
  eventType: "root_observation";
  observationId: string;
  recordedAt: string;
  graphSnapshotHash: string;
  dedupeKey: string;
  dataClassification: "shadow_telemetry";
  memoryIngestionAllowed: false;
  mayEnqueueFeedback: true;
}

/** Hard capability declaration required of every replay executor. */
export interface ShadowExecutorSafetyDeclaration {
  isolatedState: true;
  productionMemoryReadOnly: true;
  recallEnabled: false;
  captureEnabled: false;
  memoryWriteEnabled: false;
  feedbackReingestionEnabled: false;
}

/** A replay is exactly one level below a root observation and cannot spawn work. */
export interface ShadowExecutionContext {
  origin: "self_supervision";
  parentObservationId: string;
  feedbackDepth: 1;
  recallEnabled: false;
  captureEnabled: false;
  memoryWriteEnabled: false;
  feedbackReingestionEnabled: false;
}

export interface RecallCandidateTrace {
  recordId: string;
  logicalId: string | null;
  version: number;
  contentHash: string;
  renderedHash: string;
  observedAt: string;
  rank: number;
  score: number;
  injected: boolean;
  truncated: boolean;
  sourceIds: string[];
  metadataHash: string;
}

export interface StructuredRecallTrace {
  schemaVersion: "tdai-recall-trace.v1";
  traceId: string;
  recordedAt: string;
  sessionId: string;
  sessionKey: string;
  userId: string;
  agentId: string;
  taskId: string;
  queryHash: string;
  renderedPromptHash: string;
  candidates: RecallCandidateTrace[];
  warnings: string[];
}

export interface SignalEvidence {
  kind: "provenance" | "state_alignment" | "dependency" | "validator" | "intervention";
  sourceId: string;
  claim: string;
  valueHash: string;
}

export interface LayerSignalEvidence {
  kind:
    | "l0_l1_provenance"
    | "l1_l1_consistency"
    | "l1_l2_derivation"
    | "l2_l2_consistency"
    | "task_intervention"
    | "negative_control"
    | "environment";
  supportingIds: string[];
  claim: string;
  evidenceHash: string;
  verifierId: string;
}

/**
 * Score-free proof obligation for exact localization. The candidate-set hash
 * binds the certificate to the structural inspector output; models cannot
 * substitute confidence for this certificate.
 */
export interface CompleteTupleIdentifiabilityCertificate {
  schemaVersion: "tdai-complete-tuple-identifiability.v1";
  verifierId: string;
  basis: IdentifiabilityBasis;
  status: IdentifiabilityStatus;
  candidateSetHash: string;
  candidateTupleKeys: string[];
  identifiedTupleKey: string | null;
  competingTupleKeys: string[];
  noSignalWorldExcluded: boolean;
  evidence: LayerSignalEvidence[];
  reasonCodes: string[];
}

export type ReplayStatus = "not_run" | "incomplete" | "replay_verified" | "not_comparable";

export interface LayerAwareFeedbackSignal {
  schemaVersion: "tdai-layer-feedback-signal.v2";
  signalId: string;
  observationId: string;
  createdAt: string;
  decision: SignalDecision;
  target: MemoryFeedbackTarget | null;
  supportingIds: string[];
  faultType: LayerFaultType;
  suggestedAction: SuggestedAction;
  validity: MemoryValidity;
  utility: MemoryUtility;
  failureOwner: MemoryFailureOwner;
  confidence: number;
  calibrationVersion: string;
  evidence: LayerSignalEvidence[];
  identifiabilityCertificate: CompleteTupleIdentifiabilityCertificate | null;
  replayStatus: ReplayStatus;
  reasonCodes: string[];
  /** Literal false until a separately versioned offline safety gate is passed. */
  optimizationReady: false;
}

export interface SignalCost {
  calls: number;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  estimatedCostUsd: number;
}

export interface SelfSupervisionSignal {
  schemaVersion: "tdai-self-supervision-signal.v1";
  signalId: string;
  traceId: string;
  createdAt: string;
  decision: SignalDecision;
  targetMemoryId: string | null;
  supportingMemoryIds: string[];
  validity: MemoryValidity;
  utility: MemoryUtility;
  faultType: SignalFaultType;
  confidence: number;
  calibrationVersion: string;
  evidence: SignalEvidence[];
  cost: SignalCost;
  reasonCodes: string[];
  /** Phase 1 is shadow-only. This literal prevents accidental production action. */
  optimizationReady: false;
}

export type InterventionArmKind =
  | "full"
  | "mask_all"
  | "mask_candidate"
  | "replace_candidate"
  | "negative_control";

export interface InterventionArm {
  armId: string;
  kind: InterventionArmKind;
  targetMemoryId?: string;
  replacementMemoryId?: string;
  controlMemoryId?: string;
}

export interface ShadowReplaySnapshot {
  snapshotId: string;
  traceId: string;
  modelId: string;
  seed: number;
  toolStateHash: string;
  environmentHash: string;
  executionContextHash: string;
}

export interface ShadowReplayRequest {
  trace: StructuredRecallTrace;
  executionContext: ShadowExecutionContext;
  modelId: string;
  seed: number;
  candidateMemoryIds: string[];
  replacements?: Record<string, string>;
  negativeControlMemoryId?: string;
}

export interface ShadowArmOutput {
  armId: string;
  status: "ok" | "error";
  outputHash: string | null;
  validatorScore: number | null;
  validatorPassed: boolean | null;
  latencyMs: number;
  errorCode?: string;
}

export interface ShadowReplayResult {
  traceId: string;
  snapshotId: string;
  arms: ShadowArmOutput[];
  comparable: boolean;
  abstainReason?: string;
}

export interface ShadowReplayAuditEvent {
  schemaVersion: "tdai-shadow-observation.v2";
  eventType: "shadow_replay_result";
  replayEventId: string;
  parentObservationId: string;
  recordedAt: string;
  dedupeKey: string;
  executionContext: ShadowExecutionContext;
  result: ShadowReplayResult;
  dataClassification: "shadow_telemetry";
  memoryIngestionAllowed: false;
  mayEnqueueFeedback: false;
}

export type ShadowObservationEvent = RootObservation | ShadowReplayAuditEvent;
