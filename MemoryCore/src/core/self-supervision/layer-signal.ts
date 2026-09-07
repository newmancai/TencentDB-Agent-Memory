import { assertFeedbackTarget, assertRootObservation, canonicalHash } from "./observation-plane.js";
import { assertCertificateIdentifiesTuple } from "./identifiability.js";
import type {
  CompleteTupleIdentifiabilityCertificate,
  LayerAwareFeedbackSignal,
  LayerFaultType,
  LayerSignalEvidence,
  MemoryFailureOwner,
  MemoryFeedbackTarget,
  MemoryUtility,
  MemoryValidity,
  ReplayStatus,
  RootObservation,
  SignalDecision,
  SuggestedAction,
} from "./types.js";

export interface LayerSignalDraft {
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
}

const NON_MEMORY_FAILURE_OWNERS = new Set<MemoryFailureOwner>(["model", "tool", "environment"]);
const VALIDITIES = new Set<MemoryValidity>(["supported", "refuted", "expired", "unverifiable"]);
const UTILITIES = new Set<MemoryUtility>(["helpful", "harmful", "redundant", "untested"]);
const FAILURE_OWNERS = new Set<MemoryFailureOwner>([
  "memory_content", "derivation", "retrieval", "use", "model", "tool", "environment", "unknown",
]);

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

function assertSupportingIds(observation: RootObservation, supportingIds: string[]): void {
  const known = new Set([
    ...observation.graph.nodes.map((node) => node.id),
    ...observation.graph.edges.map((edge) => edge.edgeId),
  ]);
  const unknown = supportingIds.find((id) => !known.has(id));
  if (unknown) throw new Error(`Unknown supporting ID ${unknown}`);
}

export function createLayerAwareSignal(
  observation: RootObservation,
  draft: LayerSignalDraft,
  createdAt: string,
): LayerAwareFeedbackSignal {
  assertRootObservation(observation);
  if (!Number.isFinite(draft.confidence) || draft.confidence < 0 || draft.confidence > 1) {
    throw new Error("Signal confidence must be within [0,1]");
  }
  if (!draft.calibrationVersion.trim()) throw new Error("calibrationVersion is required");
  if (!VALIDITIES.has(draft.validity)) throw new Error("Unknown Memory validity");
  if (!UTILITIES.has(draft.utility)) throw new Error("Unknown Memory utility");
  if (!FAILURE_OWNERS.has(draft.failureOwner)) throw new Error("Unknown failure owner");
  if (draft.faultType === "environment_or_model_failure") {
    if (draft.target !== null) throw new Error("Environment/model failure cannot carry a Memory target");
    if (!NON_MEMORY_FAILURE_OWNERS.has(draft.failureOwner)) {
      throw new Error("Environment/model failure requires model, tool, or environment ownership");
    }
    if (draft.suggestedAction !== "no_action") {
      throw new Error("Environment/model failure cannot suggest a Memory action");
    }
  }
  if (NON_MEMORY_FAILURE_OWNERS.has(draft.failureOwner) && draft.target !== null) {
    throw new Error("Non-Memory failure owner cannot carry a Memory target");
  }
  if (draft.decision === "abstain") {
    if (draft.target !== null || draft.supportingIds.length > 0) {
      throw new Error("Abstention cannot carry target or supporting IDs");
    }
    if (draft.suggestedAction !== "no_action") throw new Error("Abstention must use no_action");
  } else {
    if (observation.memoryRelevance.decision !== "memory_relevant") {
      throw new Error("Emitted Memory feedback requires an independent memory_relevant decision");
    }
    if (!draft.target) throw new Error("Emitted layer-aware signal requires a target");
    if (draft.evidence.length === 0) throw new Error("Emitted signal requires evidence");
    if (!draft.identifiabilityCertificate) {
      throw new Error("Emitted signal requires a complete-tuple identifiability certificate");
    }
    assertCertificateIdentifiesTuple(draft.identifiabilityCertificate, {
      target: draft.target,
      faultType: draft.faultType,
      suggestedAction: draft.suggestedAction,
    });
    assertFeedbackTarget(observation.graph, draft.target);
    assertSupportingIds(observation, draft.supportingIds);
    if (draft.faultType === "task_harmful" && draft.replayStatus !== "replay_verified") {
      throw new Error("task_harmful requires replay_verified evidence");
    }
    if (draft.faultType === "task_harmful" && draft.utility !== "harmful") {
      throw new Error("task_harmful requires utility=harmful");
    }
    if (draft.utility === "harmful" && draft.replayStatus !== "replay_verified") {
      throw new Error("utility=harmful requires replay_verified evidence");
    }
    if (draft.utility === "harmful" && !draft.evidence.some((item) => item.kind === "task_intervention")) {
      throw new Error("utility=harmful requires task_intervention evidence");
    }
    if ((draft.faultType === "task_harmful" || draft.utility === "harmful")
      && !targetWasExposedOrUsed(observation, draft.target)) {
      throw new Error("Harmful utility requires the exact target version to be exposed or used");
    }
  }
  const signalHash = canonicalHash({
    observationId: observation.observationId,
    createdAt,
    target: draft.target,
    faultType: draft.faultType,
    suggestedAction: draft.suggestedAction,
    validity: draft.validity,
    utility: draft.utility,
    failureOwner: draft.failureOwner,
  });
  return {
    schemaVersion: "tdai-layer-feedback-signal.v2",
    signalId: `layer-signal-${signalHash.slice(0, 24)}`,
    observationId: observation.observationId,
    createdAt,
    decision: draft.decision,
    target: draft.target ? exactTarget(draft.target) : null,
    supportingIds: [...draft.supportingIds],
    faultType: draft.faultType,
    suggestedAction: draft.suggestedAction,
    validity: draft.validity,
    utility: draft.utility,
    failureOwner: draft.failureOwner,
    confidence: draft.confidence,
    calibrationVersion: draft.calibrationVersion,
    evidence: draft.evidence.map((evidence) => ({
      kind: evidence.kind,
      supportingIds: [...evidence.supportingIds],
      claim: evidence.claim,
      evidenceHash: evidence.evidenceHash,
      verifierId: evidence.verifierId,
    })),
    identifiabilityCertificate: draft.identifiabilityCertificate
      ? structuredClone(draft.identifiabilityCertificate)
      : null,
    replayStatus: draft.replayStatus,
    reasonCodes: [...draft.reasonCodes],
    optimizationReady: false,
  };
}

export function layerAbstentionDraft(
  reasonCode: string,
  faultType: LayerFaultType = "insufficient_evidence",
  overrides: Partial<Pick<
    LayerSignalDraft,
    "validity" | "utility" | "failureOwner" | "identifiabilityCertificate"
  >> = {},
): LayerSignalDraft {
  return {
    decision: "abstain",
    target: null,
    supportingIds: [],
    faultType,
    suggestedAction: "no_action",
    validity: overrides.validity ?? "unverifiable",
    utility: overrides.utility ?? "untested",
    failureOwner: overrides.failureOwner ?? "unknown",
    confidence: 0,
    calibrationVersion: "unavailable",
    evidence: [],
    identifiabilityCertificate: overrides.identifiabilityCertificate ?? null,
    replayStatus: "not_run",
    reasonCodes: [reasonCode],
  };
}
