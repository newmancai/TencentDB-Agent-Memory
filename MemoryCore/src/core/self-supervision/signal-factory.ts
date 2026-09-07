import { createHash } from "node:crypto";

import type {
  SelfSupervisionSignal,
  SignalCost,
  SignalDecision,
  SignalEvidence,
  SignalFaultType,
  MemoryUtility,
  MemoryValidity,
  StructuredRecallTrace
} from "./types.js";

export interface SignalDraft {
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
}
function signalId(traceId: string, createdAt: string, targetId: string | null): string {
  const suffix = createHash("sha256")
    .update(`${traceId}\u001f${createdAt}\u001f${targetId ?? "abstain"}`)
    .digest("hex").slice(0, 24);
  return `signal-${suffix}`;
}

export function createSelfSupervisionSignal(
  trace: StructuredRecallTrace,
  draft: SignalDraft,
  createdAt: string
): SelfSupervisionSignal {
  const injectedIds = new Set(
    trace.candidates.filter((candidate) => candidate.injected).map((candidate) => candidate.recordId)
  );
  if (!Number.isFinite(draft.confidence) || draft.confidence < 0 || draft.confidence > 1) {
    throw new Error("Signal confidence must be within [0,1]");
  }
  if (draft.decision === "emit") {
    if (!draft.targetMemoryId || !injectedIds.has(draft.targetMemoryId)) {
      throw new Error("Emitted target must be an actually injected memory");
    }
    const unknownSupport = draft.supportingMemoryIds.find((id) => !injectedIds.has(id));
    if (unknownSupport) throw new Error(`Supporting memory was not injected: ${unknownSupport}`);
  } else if (draft.targetMemoryId !== null || draft.supportingMemoryIds.length > 0) {
    throw new Error("Abstention cannot carry target or supporting memories");
  }
  return {
    schemaVersion: "tdai-self-supervision-signal.v1",
    signalId: signalId(trace.traceId, createdAt, draft.targetMemoryId),
    traceId: trace.traceId,
    createdAt,
    ...draft,
    optimizationReady: false
  };
}

export function abstentionDraft(reasonCode: string, calibrationVersion = "unavailable"): SignalDraft {
  return {
    decision: "abstain",
    targetMemoryId: null,
    supportingMemoryIds: [],
    validity: "unverifiable",
    utility: "untested",
    faultType: "unknown",
    confidence: 0,
    calibrationVersion,
    evidence: [],
    cost: { calls: 0, inputTokens: 0, outputTokens: 0, latencyMs: 0, estimatedCostUsd: 0 },
    reasonCodes: [reasonCode]
  };
}
