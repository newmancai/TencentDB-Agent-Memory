export type {
  FeedbackSidecarStore,
  LayerFeedbackSidecarStore,
} from "./sidecar-store.js";
export {
  InMemoryFeedbackSidecarStore,
  JsonlFeedbackSidecarStore,
  InMemoryLayerFeedbackSidecarStore,
  JsonlLayerFeedbackSidecarStore,
} from "./sidecar-store.js";
export type { ShadowReplayExecutor } from "./shadow-replay.js";
export { buildInterventionArms, executeShadowReplay } from "./shadow-replay.js";
export { buildStructuredRecallTrace } from "./recall-trace.js";
export { abstentionDraft, createSelfSupervisionSignal } from "./signal-factory.js";
export { SelfSupervisionOrchestrator } from "./orchestrator.js";
export {
  LayerObservationPlane,
  InMemoryShadowObservationStore,
  JsonlShadowObservationStore,
  assertExecutorSafety,
  assertFeedbackTarget,
  assertMemoryGraph,
  assertRootObservation,
  assertShadowExecutionContext,
  canonicalHash,
  createRootObservation,
  createShadowExecutionContext,
  memoryRelevanceSubjectBindingHash,
} from "./observation-plane.js";
export type { ObservationCollectResult, ShadowObservationStore } from "./observation-plane.js";
export { createLayerAwareSignal, layerAbstentionDraft } from "./layer-signal.js";
export type { LayerSignalDraft } from "./layer-signal.js";
export {
  evaluateIndependentMemoryRelevance,
  unavailableMemoryRelevance,
} from "./memory-relevance.js";
export type {
  IndependentMemoryRelevanceEvaluator,
  PreRetrievalMemoryRelevanceSubject,
} from "./memory-relevance.js";
export {
  assertCertificateIdentifiesTuple,
  assertCompleteTupleIdentifiabilityCertificate,
  completeFeedbackCandidateSetHash,
  completeFeedbackTupleKey,
  createCompleteTupleIdentifiabilityCertificate,
} from "./identifiability.js";
export {
  ExactLocalizationDatasetStore,
  buildGroundTruthGraph,
  createExactLocalizationExample,
  qualifyExactLocalizationExample,
} from "./ground-truth.js";
export { buildLayerExposures, buildTdaiMemoryGraph } from "./tdai-adapter.js";
export type {
  BuildTdaiGraphInput,
  BuildTdaiGraphResult,
  L2ExposureObservation,
  L2LineageRecord,
} from "./tdai-adapter.js";
export { GatedCascadeLayerRouter } from "./layer-router.js";
export type {
  CandidateReplayVerifier,
  CompleteTupleIdentifiabilityVerifier,
  ConfidenceCalibrator,
  GatedCascadeConfig,
  LayerRouterGateTrace,
  LayerRouterResult,
  IdentifiabilityCandidate,
  IdentifiabilityObservationView,
  LocalCandidateRanker,
  RouteCandidate,
  StrongCandidateJudge,
  StructuralCandidateInspector,
} from "./layer-router.js";
export {
  assertShadowCaptureEvent,
  auditCaptureCompleteness,
  captureEventIdentity,
  captureEventIntegrityDigest,
  createAggregationManifest,
  createMemoryUseTrace,
  createVersionedMemoryRecord,
  freezeAggregationInputs,
  materializeL0Authority,
} from "./capture-contracts.js";
export type * from "./capture-contracts.js";
export {
  InMemoryShadowCaptureSidecarStore,
  JsonlShadowCaptureSidecarStore,
} from "./capture-sidecar.js";
export type { ShadowCaptureSidecarStore } from "./capture-sidecar.js";
export type {
  EdgeFaultInjection,
  ExactFaultInjection,
  ExactLocalizationExample,
  ExactLocalizationLabel,
  ExactMutationManifest,
  GroundTruthGraphEdge,
  GroundTruthGraphNode,
  GroundTruthMemoryGraph,
  LocalizationDetectorView,
  LocalizationTaskSpec,
  NodeFaultInjection,
  QualificationRuns,
  RawGraphEdge,
  RawGraphNode,
} from "./ground-truth.js";
export type { BuildRecallTraceInput, RecallRenderObservation } from "./recall-trace.js";
export {
  applyStructuredRecallBudget,
  assertRecallShadowObservation,
  createRecallShadowDraft,
  dispatchRecallShadowObservation,
  finalizeRecallShadowObservation,
  JsonlRecallShadowObserver,
} from "./recall-shadow-adapter.js";
export type {
  BudgetedRecallCandidate,
  RecallBudgetLimits,
  RecallIdentityAuthorityInput,
  RecallNotExposedReason,
  RecallRetrievalStage,
  RecallSearchFacts,
  RecallShadowCandidateObservation,
  RecallShadowDraft,
  RecallShadowLogger,
  RecallShadowObservation,
  RecallShadowObserver,
  StructuredRecallCandidate,
} from "./recall-shadow-adapter.js";
export {
  InMemoryL0L1CaptureAuditStore,
  PassiveL0L1ShadowCaptureAdapter,
} from "./l0-l1-shadow-adapter.js";
export type {
  L0L1CaptureAudit,
  L0L1CaptureAuditStore,
  L0L1CaptureReason,
  L0L1CaptureStatus,
  PassiveL0L1ShadowCaptureOptions,
} from "./l0-l1-shadow-adapter.js";
export {
  createStrongL2CommitReadbackReceipt,
  InMemoryL2StagedAggregationAuditStore,
  L2_COMMIT_READBACK_VERIFIED_FIELDS,
  L2StagedShadowAggregationCoordinator,
  l2CommitReadbackVerifiedFieldSetHash,
} from "./l2-staged-shadow-adapter.js";
export type * from "./l2-staged-shadow-adapter.js";
export * from "./profile-commit-conformance.js";
export * from "./profile-commit-sqlite-reference.js";
export type { SignalDraft } from "./signal-factory.js";
export type { SelfSupervisionSignalGenerator } from "./orchestrator.js";
export type * from "./types.js";
export { applyEvidenceScopedAdmission } from "./evidence-scoped-admission.js";
export { assessTaskEvidence, buildObjectiveTaskOutcome, repairMissingOutputPrefix } from "./execution-feedback.js";
export type {
  FeedbackStage,
  LocalExecutionStatus,
  TaskEvidenceAssessment,
  TaskEvidenceInput,
  ObjectiveTaskOutcomeInput,
  MissingPrefixRepairInput,
  MissingPrefixRepairResult,
} from "./execution-feedback.js";
export { executionCaptureMessages, observeToolExecutions } from "./tool-execution.js";
export type {
  ToolExecutionContext,
  ToolExecutionObservation,
  ToolResultContract,
} from "./tool-execution.js";
export type {
  AdmissionDisposition,
  AdmissionValidity,
  EvidenceScopedAdmissionResult,
  MemoryAdmissionDecision,
} from "./evidence-scoped-admission.js";
