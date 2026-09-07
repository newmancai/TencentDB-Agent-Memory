import type {
  InterventionArm,
  ShadowExecutorSafetyDeclaration,
  ShadowArmOutput,
  ShadowReplayRequest,
  ShadowReplayResult,
  ShadowReplaySnapshot
} from "./types.js";
import { assertExecutorSafety, assertShadowExecutionContext, canonicalHash } from "./observation-plane.js";

export interface ShadowReplayExecutor {
  readonly safety: ShadowExecutorSafetyDeclaration;
  capture(request: ShadowReplayRequest): Promise<ShadowReplaySnapshot>;
  execute(snapshot: ShadowReplaySnapshot, arm: InterventionArm): Promise<ShadowArmOutput>;
}

function assertCandidates(request: ShadowReplayRequest): void {
  assertShadowExecutionContext(request.executionContext);
  const injectedIds = new Set(
    request.trace.candidates.filter((candidate) => candidate.injected).map((candidate) => candidate.recordId)
  );
  for (const candidateId of request.candidateMemoryIds) {
    if (!injectedIds.has(candidateId)) {
      throw new Error(`Cannot intervene on non-injected candidate ${candidateId}`);
    }
  }
  for (const [targetId, replacementId] of Object.entries(request.replacements ?? {})) {
    if (!injectedIds.has(targetId)) throw new Error(`Replacement target is not injected: ${targetId}`);
    if (!replacementId) throw new Error(`Replacement ID is empty for ${targetId}`);
  }
}

export function buildInterventionArms(request: ShadowReplayRequest): InterventionArm[] {
  assertCandidates(request);
  const arms: InterventionArm[] = [
    { armId: `${request.trace.traceId}:full`, kind: "full" },
    { armId: `${request.trace.traceId}:mask-all`, kind: "mask_all" }
  ];
  for (const candidateId of request.candidateMemoryIds) {
    arms.push({
      armId: `${request.trace.traceId}:mask:${candidateId}`,
      kind: "mask_candidate",
      targetMemoryId: candidateId
    });
    const replacement = request.replacements?.[candidateId];
    if (replacement) {
      arms.push({
        armId: `${request.trace.traceId}:replace:${candidateId}`,
        kind: "replace_candidate",
        targetMemoryId: candidateId,
        replacementMemoryId: replacement
      });
    }
  }
  if (request.negativeControlMemoryId) {
    arms.push({
      armId: `${request.trace.traceId}:negative-control`,
      kind: "negative_control",
      controlMemoryId: request.negativeControlMemoryId
    });
  }
  return arms;
}

export async function executeShadowReplay(
  executor: ShadowReplayExecutor,
  request: ShadowReplayRequest
): Promise<ShadowReplayResult> {
  try {
    assertExecutorSafety(executor.safety);
    assertShadowExecutionContext(request.executionContext);
  } catch (error) {
    return {
      traceId: request.trace.traceId,
      snapshotId: "safety-check-failed",
      arms: [],
      comparable: false,
      abstainReason: `unsafe_shadow_executor:${(error as Error).message}`,
    };
  }
  let snapshot: ShadowReplaySnapshot;
  try {
    snapshot = await executor.capture(request);
  } catch (error) {
    return {
      traceId: request.trace.traceId,
      snapshotId: "capture-failed",
      arms: [],
      comparable: false,
      abstainReason: `snapshot_capture_failed:${(error as Error).message}`
    };
  }

  const expectedContextHash = canonicalHash(request.executionContext);
  if (
    snapshot.traceId !== request.trace.traceId
    || snapshot.modelId !== request.modelId
    || snapshot.seed !== request.seed
    || snapshot.executionContextHash !== expectedContextHash
  ) {
    return {
      traceId: request.trace.traceId,
      snapshotId: snapshot.snapshotId,
      arms: [],
      comparable: false,
      abstainReason: "snapshot_identity_or_safety_mismatch",
    };
  }

  const arms = buildInterventionArms(request);
  const outputs: ShadowArmOutput[] = [];
  for (const arm of arms) {
    try {
      const output = await executor.execute(snapshot, arm);
      outputs.push(output.armId === arm.armId ? output : {
        armId: arm.armId,
        status: "error",
        outputHash: null,
        validatorScore: null,
        validatorPassed: null,
        latencyMs: output.latencyMs,
        errorCode: "arm_id_mismatch"
      });
    } catch (error) {
      outputs.push({
        armId: arm.armId,
        status: "error",
        outputHash: null,
        validatorScore: null,
        validatorPassed: null,
        latencyMs: 0,
        errorCode: `executor_error:${(error as Error).message}`
      });
    }
  }

  const full = outputs.find((output) => output.armId.endsWith(":full"));
  const maskAll = outputs.find((output) => output.armId.endsWith(":mask-all"));
  const comparable = Boolean(
    full?.status === "ok"
    && maskAll?.status === "ok"
    && outputs.every((output) => output.status === "ok")
  );
  return {
    traceId: request.trace.traceId,
    snapshotId: snapshot.snapshotId,
    arms: outputs,
    comparable,
    abstainReason: comparable ? undefined : "one_or_more_shadow_arms_failed"
  };
}
