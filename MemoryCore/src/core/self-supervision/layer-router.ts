import { layerAbstentionDraft, type LayerSignalDraft } from "./layer-signal.js";
import {
  assertCompleteTupleIdentifiabilityCertificate,
  completeFeedbackTupleKey,
} from "./identifiability.js";
import { assertFeedbackTarget, assertRootObservation } from "./observation-plane.js";
import type {
  CompleteTupleIdentifiabilityCertificate,
  IdentifiabilityBasis,
  LayerExposure,
  LayerFaultType,
  LayerSignalEvidence,
  MemoryFailureOwner,
  MemoryFeedbackTarget,
  MemoryUtility,
  MemoryValidity,
  ReplayStatus,
  RootObservation,
  SuggestedAction,
  TaskOutcomeObservation,
} from "./types.js";

export interface RouteCandidate {
  target: MemoryFeedbackTarget;
  faultType: LayerFaultType;
  suggestedAction: SuggestedAction;
  validity: MemoryValidity;
  utility: MemoryUtility;
  failureOwner: MemoryFailureOwner;
  rawScore: number;
  supportingIds: string[];
  evidence: LayerSignalEvidence[];
  reasonCodes: string[];
}

export interface StructuralCandidateInspector {
  readonly id: string;
  readonly enumerationMode: "complete_admissible_tuple_universe";
  readonly authorityVersion: string;
  inspect(observation: IdentifiabilityObservationView): Promise<RouteCandidate[]>;
}

/** Proof input is the tuple universe only; inspector prose/scores never enter it. */
export type IdentifiabilityCandidate = Pick<
  RouteCandidate,
  "target" | "faultType" | "suggestedAction"
>;

type ScoreFreeTaskOutcome = Omit<TaskOutcomeObservation, "validators"> & {
  validators: Array<Omit<TaskOutcomeObservation["validators"][number], "score">>;
};

/** Whitelist-shaped view shared by tuple enumeration and authority verification. */
export type IdentifiabilityObservationView = Omit<RootObservation, "exposures" | "outcome"> & {
  exposures: Array<Omit<LayerExposure, "score" | "rank">>;
  outcome: ScoreFreeTaskOutcome | null;
};

export interface CompleteTupleIdentifiabilityVerifier {
  readonly id: string;
  readonly basis: IdentifiabilityBasis;
  readonly authorityVersion: string;
  verify(
    observation: IdentifiabilityObservationView,
    candidates: IdentifiabilityCandidate[],
  ): Promise<CompleteTupleIdentifiabilityCertificate>;
}

export interface LocalCandidateRanker {
  readonly id: string;
  rank(observation: RootObservation, candidates: RouteCandidate[]): Promise<RouteCandidate[]>;
}

export interface StrongCandidateJudge {
  readonly id: string;
  adjudicate(observation: RootObservation, candidates: RouteCandidate[]): Promise<RouteCandidate | null>;
}

export interface CandidateReplayVerifier {
  readonly id: string;
  verify(
    observation: RootObservation,
    candidate: RouteCandidate,
  ): Promise<{ status: ReplayStatus; score: number; evidence: LayerSignalEvidence[] }>;
}

export interface ConfidenceCalibrator {
  readonly version: string;
  calibrate(input: { rawScore: number; faultType: LayerFaultType; targetType: MemoryFeedbackTarget["targetType"] }): number;
}

export interface LayerRouterGateTrace {
  gate:
    | "memory_relevance"
    | "layer_and_fault"
    | "tuple_identifiability"
    | "target_localization"
    | "escalation"
    | "replay"
    | "emit";
  decision: string;
  componentId: string;
}

export interface LayerRouterResult {
  draft: LayerSignalDraft;
  gateTrace: LayerRouterGateTrace[];
}

export interface GatedCascadeConfig {
  minimumCandidateScore: number;
  minimumTopMargin: number;
  emitConfidence: number;
  requireReplayFor: LayerFaultType[];
}

const DEFAULT_CONFIG: GatedCascadeConfig = {
  minimumCandidateScore: 0.55,
  minimumTopMargin: 0.08,
  emitConfidence: 0.9,
  requireReplayFor: ["task_harmful"],
};

function finiteProbability(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function deepFreeze<T>(value: T, seen = new Set<object>()): T {
  if (!value || typeof value !== "object" || seen.has(value as object)) return value;
  seen.add(value as object);
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function exactTarget(target: MemoryFeedbackTarget): MemoryFeedbackTarget {
  if (target.targetType === "L1_NODE" || target.targetType === "L2_NODE") {
    return {
      targetType: target.targetType,
      targetId: target.targetId,
      targetVersion: target.targetVersion,
    };
  }
  return {
    targetType: "L1_L2_EDGE",
    targetId: target.targetId,
    targetVersion: target.targetVersion,
    from: { layer: "L1", id: target.from.id, version: target.from.version },
    to: { layer: "L2", id: target.to.id, version: target.to.version },
  };
}

function scoreFreeObservation(observation: RootObservation): IdentifiabilityObservationView {
  const relevance = observation.memoryRelevance;
  const view: IdentifiabilityObservationView = {
    schemaVersion: "tdai-shadow-observation.v2",
    eventType: "root_observation",
    observationId: observation.observationId,
    recordedAt: observation.recordedAt,
    graphSnapshotHash: observation.graphSnapshotHash,
    dedupeKey: observation.dedupeKey,
    dataClassification: "shadow_telemetry",
    memoryIngestionAllowed: false,
    mayEnqueueFeedback: true,
    origin: observation.origin,
    feedbackDepth: 0,
    taskRunId: observation.taskRunId,
    sessionId: observation.sessionId,
    preRetrievalContextHash: observation.preRetrievalContextHash,
    contextHash: observation.contextHash,
    memoryRelevance: {
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
    },
    graph: {
      nodes: observation.graph.nodes.map((node) => ({
        layer: node.layer,
        id: node.id,
        version: node.version,
        contentHash: node.contentHash,
        metadataHash: node.metadataHash,
        scopeHash: node.scopeHash,
        entityBindingHash: node.entityBindingHash,
        observedAt: node.observedAt,
      })),
      edges: observation.graph.edges.map((edge) => ({
        edgeId: edge.edgeId,
        version: edge.version,
        relation: edge.relation,
        from: { layer: edge.from.layer, id: edge.from.id, version: edge.from.version },
        to: { layer: edge.to.layer, id: edge.to.id, version: edge.to.version },
        metadataHash: edge.metadataHash,
      })),
    },
    exposures: observation.exposures.map((exposure) => ({
      exposureId: exposure.exposureId,
      node: { layer: exposure.node.layer, id: exposure.node.id, version: exposure.node.version },
      state: exposure.state,
      channel: exposure.channel,
      renderedHash: exposure.renderedHash,
      truncated: exposure.truncated,
      derivationEdges: exposure.derivationEdges.map((edge) => ({
        edgeId: edge.edgeId,
        edgeVersion: edge.edgeVersion,
      })),
    })),
    outcome: observation.outcome
    ? {
      status: observation.outcome.status,
      outputHash: observation.outcome.outputHash,
      environmentHash: observation.outcome.environmentHash,
      modelId: observation.outcome.modelId,
      validators: observation.outcome.validators.map((validator) => ({
        validatorId: validator.validatorId,
        validatorVersion: validator.validatorVersion,
        oracleKind: validator.oracleKind,
        status: validator.status,
        evidenceHash: validator.evidenceHash,
      })),
    }
    : null,
  };
  return deepFreeze(view);
}

function scoreFreeCandidates(candidates: RouteCandidate[]): IdentifiabilityCandidate[] {
  return deepFreeze(candidates.map((candidate) => ({
    target: exactTarget(candidate.target),
    faultType: candidate.faultType,
    suggestedAction: candidate.suggestedAction,
  })));
}

function abstain(
  reason: string,
  trace: LayerRouterGateTrace[],
  certificate: CompleteTupleIdentifiabilityCertificate | null = null,
  faultType: LayerFaultType = "insufficient_evidence",
  failureOwner: MemoryFailureOwner = "unknown",
): LayerRouterResult {
  return {
    draft: layerAbstentionDraft(reason, faultType, {
      identifiabilityCertificate: certificate,
      failureOwner,
    }),
    gateTrace: trace,
  };
}

const NON_MEMORY_FAILURE_OWNERS = new Set<MemoryFailureOwner>(["model", "tool", "environment"]);

function targetWasExposedOrUsed(observation: RootObservation, target: MemoryFeedbackTarget): boolean {
  return observation.exposures.some((exposure) => {
    if (exposure.state !== "exposed" && exposure.state !== "used") return false;
    if (exposure.truncated) return false;
    if (target.targetType === "L1_NODE" || target.targetType === "L2_NODE") {
      const layer = target.targetType === "L1_NODE" ? "L1" : "L2";
      return exposure.node.layer === layer
        && exposure.node.id === target.targetId
        && exposure.node.version === target.targetVersion;
    }
    return exposure.node.layer === "L2"
      && exposure.node.id === target.to.id
      && exposure.node.version === target.to.version
      && exposure.derivationEdges.some((edge) => (
        edge.edgeId === target.targetId && edge.edgeVersion === target.targetVersion
      ));
  });
}

/**
 * Layer-aware gated cascade. Stages are injected so rule, local-model and API
 * implementations share one fail-closed protocol. The router never writes Memory.
 */
export class GatedCascadeLayerRouter {
  private readonly config: GatedCascadeConfig;

  constructor(
    private readonly inspector: StructuralCandidateInspector,
    private readonly identifiabilityVerifier: CompleteTupleIdentifiabilityVerifier,
    private readonly calibrator: ConfidenceCalibrator,
    private readonly localRanker?: LocalCandidateRanker,
    private readonly strongJudge?: StrongCandidateJudge,
    private readonly replayVerifier?: CandidateReplayVerifier,
    config?: Partial<GatedCascadeConfig>,
  ) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  async route(observation: RootObservation): Promise<LayerRouterResult> {
    const gateTrace: LayerRouterGateTrace[] = [];
    try {
      assertRootObservation(observation);
    } catch (error) {
      gateTrace.push({ gate: "memory_relevance", decision: "abstain:invalid_root", componentId: "root-v2-validator" });
      return abstain(`gate0_invalid_root_observation:${(error as Error).message}`, gateTrace);
    }
    if (observation.memoryRelevance.decision === "no_match") {
      gateTrace.push({
        gate: "memory_relevance",
        decision: "abstain:independent_no_match",
        componentId: observation.memoryRelevance.evaluatorId,
      });
      return abstain("gate0_independent_no_match", gateTrace);
    }
    if (observation.memoryRelevance.decision === "unknown") {
      gateTrace.push({
        gate: "memory_relevance",
        decision: "abstain:independent_relevance_unknown",
        componentId: observation.memoryRelevance.evaluatorId,
      });
      return abstain("gate0_independent_memory_relevance_unknown", gateTrace);
    }
    if (observation.graph.nodes.length === 0 || observation.exposures.length === 0) {
      gateTrace.push({ gate: "memory_relevance", decision: "abstain:no_exposure", componentId: "router" });
      return abstain("gate0_no_memory_exposure", gateTrace);
    }
    gateTrace.push({ gate: "memory_relevance", decision: "continue", componentId: "router" });

    let candidates: RouteCandidate[];
    try {
      if (
        this.inspector.enumerationMode !== "complete_admissible_tuple_universe"
        || !this.inspector.authorityVersion.trim()
      ) {
        throw new Error("Inspector lacks complete-universe enumeration capability");
      }
      candidates = await this.inspector.inspect(scoreFreeObservation(observation));
    } catch (error) {
      gateTrace.push({ gate: "layer_and_fault", decision: "abstain:inspector_failure", componentId: this.inspector.id });
      return abstain(`gate1_inspector_failure:${(error as Error).message}`, gateTrace);
    }
    candidates = candidates
      .map((candidate) => ({
        ...candidate,
        target: exactTarget(candidate.target),
        rawScore: finiteProbability(candidate.rawScore),
      }));
    if (candidates.length === 0) {
      gateTrace.push({ gate: "layer_and_fault", decision: "abstain:no_candidate", componentId: this.inspector.id });
      return abstain("gate1_no_supported_candidate", gateTrace);
    }
    gateTrace.push({ gate: "layer_and_fault", decision: `${candidates.length}_candidates`, componentId: this.inspector.id });

    const memoryCandidates = candidates.filter((candidate) => (
      candidate.faultType !== "environment_or_model_failure"
      && !NON_MEMORY_FAILURE_OWNERS.has(candidate.failureOwner)
    ));
    if (memoryCandidates.length !== candidates.length) {
      gateTrace.push({
        gate: "layer_and_fault",
        decision: `${candidates.length - memoryCandidates.length}_non_memory_candidates_excluded`,
        componentId: "router",
      });
      if (memoryCandidates.length > 0) {
        return abstain("gate1_memory_vs_non_memory_failure_ambiguous", gateTrace);
      }
    }
    if (memoryCandidates.length === 0) {
      const owner = candidates.find((candidate) => NON_MEMORY_FAILURE_OWNERS.has(candidate.failureOwner))?.failureOwner
        ?? "unknown";
      return abstain(
        "gate1_non_memory_failure_has_no_memory_target",
        gateTrace,
        null,
        "environment_or_model_failure",
        owner,
      );
    }
    candidates = memoryCandidates;

    const exactVersionCandidates = candidates.filter((candidate) => {
      try {
        assertFeedbackTarget(observation.graph, candidate.target);
        return true;
      } catch {
        return false;
      }
    });
    if (exactVersionCandidates.length !== candidates.length) {
      gateTrace.push({
        gate: "layer_and_fault",
        decision: `${candidates.length - exactVersionCandidates.length}_unresolved_or_invalid_targets_excluded`,
        componentId: "router",
      });
    }
    if (exactVersionCandidates.length === 0) {
      return abstain("gate1_no_exact_version_candidate", gateTrace);
    }
    candidates = exactVersionCandidates;

    let identifiabilityCertificate: CompleteTupleIdentifiabilityCertificate;
    try {
      identifiabilityCertificate = await this.identifiabilityVerifier.verify(
        scoreFreeObservation(observation),
        scoreFreeCandidates(candidates),
      );
      assertCompleteTupleIdentifiabilityCertificate(
        identifiabilityCertificate,
        candidates,
        this.identifiabilityVerifier.id,
      );
      if (identifiabilityCertificate.basis !== this.identifiabilityVerifier.basis) {
        throw new Error("Identifiability certificate basis does not match verifier capability");
      }
      if (!this.identifiabilityVerifier.authorityVersion.trim()) {
        throw new Error("Identifiability verifier authorityVersion is required");
      }
    } catch (error) {
      gateTrace.push({
        gate: "tuple_identifiability",
        decision: "abstain:invalid_certificate",
        componentId: this.identifiabilityVerifier.id,
      });
      return abstain(`gate2_identifiability_failure:${(error as Error).message}`, gateTrace);
    }
    if (identifiabilityCertificate.status !== "identified") {
      gateTrace.push({
        gate: "tuple_identifiability",
        decision: `abstain:${identifiabilityCertificate.status}`,
        componentId: this.identifiabilityVerifier.id,
      });
      const reason = identifiabilityCertificate.status === "ambiguous"
        ? "gate2_complete_tuple_ambiguous"
        : "gate2_complete_tuple_insufficient_evidence";
      return abstain(reason, gateTrace, identifiabilityCertificate);
    }
    candidates = candidates.filter(
      (candidate) => completeFeedbackTupleKey(candidate) === identifiabilityCertificate.identifiedTupleKey,
    );
    if (candidates.length === 0) {
      gateTrace.push({
        gate: "tuple_identifiability",
        decision: "abstain:identified_tuple_missing",
        componentId: this.identifiabilityVerifier.id,
      });
      return abstain("gate2_identified_tuple_missing", gateTrace, identifiabilityCertificate);
    }
    gateTrace.push({
      gate: "tuple_identifiability",
      decision: "identified:complete_tuple",
      componentId: this.identifiabilityVerifier.id,
    });

    if (this.localRanker) {
      try {
        const ranked = await this.localRanker.rank(observation, candidates);
        if (ranked.length === 0) throw new Error("Local ranker returned no candidate");
        candidates = ranked.map((rankedCandidate) => {
          const tupleKey = completeFeedbackTupleKey(rankedCandidate);
          const original = candidates.find((candidate) => completeFeedbackTupleKey(candidate) === tupleKey);
          if (!original) throw new Error("Local ranker returned a candidate outside the certified set");
          return { ...original, rawScore: finiteProbability(rankedCandidate.rawScore) };
        });
      } catch (error) {
        gateTrace.push({ gate: "target_localization", decision: "abstain:ranker_failure", componentId: this.localRanker.id });
        return abstain(`gate3_ranker_failure:${(error as Error).message}`, gateTrace, identifiabilityCertificate);
      }
    }
    candidates = [...candidates].sort((left, right) => right.rawScore - left.rawScore);
    let selected = candidates[0]!;
    const margin = selected.rawScore - (candidates[1]?.rawScore ?? 0);
    const uncertain = selected.rawScore < this.config.minimumCandidateScore || margin < this.config.minimumTopMargin;
    gateTrace.push({
      gate: "target_localization",
      decision: `top=${selected.target.targetType}:${selected.rawScore.toFixed(4)}:margin=${margin.toFixed(4)}`,
      componentId: this.localRanker?.id ?? this.inspector.id,
    });

    if (uncertain) {
      if (!this.strongJudge) {
        gateTrace.push({ gate: "escalation", decision: "abstain:no_strong_judge", componentId: "router" });
        return abstain("gate3_ambiguous_without_escalation", gateTrace, identifiabilityCertificate);
      }
      try {
        const adjudicated = await this.strongJudge.adjudicate(observation, candidates);
        if (!adjudicated) {
          gateTrace.push({ gate: "escalation", decision: "abstain:judge_abstained", componentId: this.strongJudge.id });
          return abstain("gate3_strong_judge_abstained", gateTrace, identifiabilityCertificate);
        }
        const adjudicatedTupleKey = completeFeedbackTupleKey(adjudicated);
        const existingCandidate = candidates.find(
          (candidate) => completeFeedbackTupleKey(candidate) === adjudicatedTupleKey,
        );
        if (!existingCandidate) {
          gateTrace.push({
            gate: "escalation",
            decision: "abstain:judge_out_of_set",
            componentId: this.strongJudge.id,
          });
          return abstain("gate3_strong_judge_out_of_set", gateTrace, identifiabilityCertificate);
        }
        selected = { ...existingCandidate, rawScore: finiteProbability(adjudicated.rawScore) };
        gateTrace.push({ gate: "escalation", decision: "candidate_selected", componentId: this.strongJudge.id });
      } catch (error) {
        gateTrace.push({ gate: "escalation", decision: "abstain:judge_failure", componentId: this.strongJudge.id });
        return abstain(`gate3_strong_judge_failure:${(error as Error).message}`, gateTrace, identifiabilityCertificate);
      }
    }

    if (selected.faultType === "task_harmful" && selected.utility !== "harmful") {
      gateTrace.push({ gate: "replay", decision: "abstain:utility_not_harmful", componentId: "router" });
      return abstain("gate4_task_harmful_requires_harmful_utility", gateTrace, identifiabilityCertificate);
    }
    const harmfulUtility = selected.faultType === "task_harmful" || selected.utility === "harmful";
    if (harmfulUtility && !targetWasExposedOrUsed(observation, selected.target)) {
      gateTrace.push({ gate: "replay", decision: "abstain:target_not_exposed_or_used", componentId: "router" });
      return abstain("gate4_harmful_target_not_exposed_or_used", gateTrace, identifiabilityCertificate);
    }

    let replayStatus: ReplayStatus = "not_run";
    if (this.config.requireReplayFor.includes(selected.faultType) || selected.utility === "harmful") {
      if (!this.replayVerifier) {
        gateTrace.push({ gate: "replay", decision: "abstain:required_unavailable", componentId: "router" });
        return abstain("gate4_required_replay_unavailable", gateTrace, identifiabilityCertificate);
      }
      try {
        const replay = await this.replayVerifier.verify(observation, selected);
        replayStatus = replay.status;
        selected = {
          ...selected,
          rawScore: Math.min(selected.rawScore, finiteProbability(replay.score)),
          evidence: [...selected.evidence, ...replay.evidence],
        };
        gateTrace.push({ gate: "replay", decision: replay.status, componentId: this.replayVerifier.id });
        if (replay.status !== "replay_verified") {
          return abstain("gate4_replay_not_verified", gateTrace, identifiabilityCertificate);
        }
        if (selected.utility === "harmful" && !replay.evidence.some((item) => item.kind === "task_intervention")) {
          return abstain("gate4_replay_missing_intervention_evidence", gateTrace, identifiabilityCertificate);
        }
      } catch (error) {
        gateTrace.push({ gate: "replay", decision: "abstain:replay_failure", componentId: this.replayVerifier.id });
        return abstain(`gate4_replay_failure:${(error as Error).message}`, gateTrace, identifiabilityCertificate);
      }
    }

    const confidence = finiteProbability(this.calibrator.calibrate({
      rawScore: selected.rawScore,
      faultType: selected.faultType,
      targetType: selected.target.targetType,
    }));
    if (confidence < this.config.emitConfidence) {
      gateTrace.push({ gate: "emit", decision: `abstain:confidence=${confidence.toFixed(4)}`, componentId: this.calibrator.version });
      return abstain("gate4_below_calibrated_emit_threshold", gateTrace, identifiabilityCertificate);
    }
    gateTrace.push({ gate: "emit", decision: `emit:confidence=${confidence.toFixed(4)}`, componentId: this.calibrator.version });
    return {
      draft: {
        decision: "emit",
        target: structuredClone(selected.target),
        supportingIds: [...selected.supportingIds],
        faultType: selected.faultType,
        suggestedAction: selected.suggestedAction,
        confidence,
        calibrationVersion: this.calibrator.version,
        evidence: structuredClone([
          ...identifiabilityCertificate.evidence,
          ...selected.evidence,
        ]),
        identifiabilityCertificate: structuredClone(identifiabilityCertificate),
        validity: selected.validity,
        utility: selected.utility,
        failureOwner: selected.failureOwner,
        replayStatus,
        reasonCodes: [...selected.reasonCodes],
      },
      gateTrace,
    };
  }
}
