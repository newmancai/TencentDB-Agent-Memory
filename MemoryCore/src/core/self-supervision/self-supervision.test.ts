import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { JsonlFeedbackSidecarStore } from "./sidecar-store.js";
import { InMemoryFeedbackSidecarStore } from "./sidecar-store.js";
import { buildInterventionArms, executeShadowReplay, type ShadowReplayExecutor } from "./shadow-replay.js";
import { buildStructuredRecallTrace } from "./recall-trace.js";
import { SelfSupervisionOrchestrator } from "./orchestrator.js";
import { canonicalHash, createShadowExecutionContext } from "./observation-plane.js";
import type { L1SearchResult } from "../store/types.js";
import type {
  SelfSupervisionSignal,
  ShadowReplayRequest,
  StructuredRecallTrace
} from "./types.js";

const trace: StructuredRecallTrace = {
  schemaVersion: "tdai-recall-trace.v1",
  traceId: "trace-1",
  recordedAt: "2026-08-31T00:00:00.000Z",
  sessionId: "session-1",
  sessionKey: "key-1",
  userId: "user-1",
  agentId: "agent-1",
  taskId: "task-1",
  queryHash: "query-hash",
  renderedPromptHash: "prompt-hash",
  warnings: [],
  candidates: [{
    recordId: "memory-1",
    logicalId: "logical-1",
    version: 1,
    contentHash: "content-hash",
    renderedHash: "rendered-hash",
    observedAt: "2026-08-01T00:00:00.000Z",
    rank: 1,
    score: 0.9,
    injected: true,
    truncated: false,
    sourceIds: ["source-1"],
    metadataHash: "metadata-hash"
  }]
};

function request(): ShadowReplayRequest {
  return {
    trace,
    executionContext: createShadowExecutionContext("obs-1"),
    modelId: "model-fixed",
    seed: 7,
    candidateMemoryIds: ["memory-1"],
    replacements: { "memory-1": "memory-2" },
    negativeControlMemoryId: "memory-control"
  };
}

function signal(): SelfSupervisionSignal {
  return {
    schemaVersion: "tdai-self-supervision-signal.v1",
    signalId: "signal-1",
    traceId: trace.traceId,
    createdAt: "2026-08-31T00:00:01.000Z",
    decision: "emit",
    targetMemoryId: "memory-1",
    supportingMemoryIds: ["memory-2"],
    validity: "expired",
    utility: "untested",
    faultType: "direct_update",
    confidence: 0.95,
    calibrationVersion: "calibration-dev",
    evidence: [],
    cost: { calls: 0, inputTokens: 0, outputTokens: 0, latencyMs: 1, estimatedCostUsd: 0 },
    reasonCodes: ["test"],
    optimizationReady: false
  };
}

describe("self-supervision sidecar", () => {
  it("writes and reads shadow-only JSONL signals", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-self-supervision-test-"));
    try {
      const store = new JsonlFeedbackSidecarStore(root);
      await store.append(signal());
      expect(store.readAll()).toEqual([signal()]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("rejects emitted signals without a target", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-self-supervision-test-"));
    try {
      const store = new JsonlFeedbackSidecarStore(root);
      await expect(store.append({ ...signal(), targetMemoryId: null })).rejects.toThrow(/requires target/);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

describe("structured recall trace", () => {
  const searchResult: L1SearchResult = {
    record_id: "memory-1",
    content: "User currently works in Harbor City.",
    type: "fact",
    priority: 1,
    scene_name: "work",
    score: 0.9,
    timestamp_str: "2026-08-01T00:00:00.000Z",
    timestamp_start: "2026-08-01T00:00:00.000Z",
    timestamp_end: "2026-08-01T00:00:00.000Z",
    version: 2,
    session_key: "key-1",
    session_id: "session-1",
    team_id: "team-1",
    task_id: "task-1",
    user_id: "user-1",
    agent_id: "agent-1",
    metadata_json: JSON.stringify({
      _tdai_provenance: { logicalId: "work-location", sourceIds: ["l0-1"] }
    })
  };

  it("maps actual L1 identity and render decisions without storing raw query text", () => {
    const built = buildStructuredRecallTrace({
      traceId: "trace-built",
      recordedAt: "2026-08-31T00:00:00.000Z",
      sessionId: "session-1",
      sessionKey: "key-1",
      userId: "user-1",
      agentId: "agent-1",
      taskId: "task-1",
      query: "Where should I commute tomorrow?",
      renderedPrompt: "prompt with memory",
      recalled: [searchResult],
      renderObservations: [{
        recordId: "memory-1",
        renderedText: "rendered memory",
        injected: true,
        truncated: false
      }]
    });
    expect(built.queryHash).toMatch(/^[a-f0-9]{64}$/);
    expect(built.candidates[0]).toMatchObject({
      recordId: "memory-1",
      logicalId: "work-location",
      version: 2,
      injected: true,
      sourceIds: ["l0-1"]
    });
    expect(JSON.stringify(built)).not.toContain("Where should I commute tomorrow?");
  });

  it("requires an observation for every recalled row", () => {
    expect(() => buildStructuredRecallTrace({
      traceId: "trace-built",
      recordedAt: "2026-08-31T00:00:00.000Z",
      sessionId: "session-1",
      sessionKey: "key-1",
      userId: "user-1",
      agentId: "agent-1",
      taskId: "task-1",
      query: "q",
      renderedPrompt: "p",
      recalled: [searchResult],
      renderObservations: []
    })).toThrow(/Missing render observation/);
  });
});

describe("self-supervision orchestrator", () => {
  it("converts invalid generator output into a persisted abstention", async () => {
    const sidecar = new InMemoryFeedbackSidecarStore();
    const orchestrator = new SelfSupervisionOrchestrator({
      id: "invalid-generator",
      async generate() {
        return {
          decision: "emit",
          targetMemoryId: "not-injected",
          supportingMemoryIds: [],
          validity: "expired",
          utility: "untested",
          faultType: "direct_update",
          confidence: 1,
          calibrationVersion: "test",
          evidence: [],
          cost: { calls: 0, inputTokens: 0, outputTokens: 0, latencyMs: 0, estimatedCostUsd: 0 },
          reasonCodes: []
        };
      }
    }, sidecar, () => "2026-08-31T00:00:02.000Z");
    const result = await orchestrator.process(trace);
    expect(result.decision).toBe("abstain");
    expect(result.reasonCodes[0]).toContain("invalid_generator_output");
    expect(sidecar.signals).toEqual([result]);
  });
});

describe("shadow replay boundary", () => {
  it("builds all five intervention arm kinds from injected candidates", () => {
    expect(buildInterventionArms(request()).map((arm) => arm.kind)).toEqual([
      "full", "mask_all", "mask_candidate", "replace_candidate", "negative_control"
    ]);
  });

  it("fails closed when any arm fails", async () => {
    const executor: ShadowReplayExecutor = {
      safety: {
        isolatedState: true,
        productionMemoryReadOnly: true,
        recallEnabled: false,
        captureEnabled: false,
        memoryWriteEnabled: false,
        feedbackReingestionEnabled: false,
      },
      async capture(input) {
        return {
          snapshotId: "snapshot-1",
          traceId: input.trace.traceId,
          modelId: input.modelId,
          seed: input.seed,
          toolStateHash: "tools",
          environmentHash: "environment",
          executionContextHash: canonicalHash(input.executionContext),
        };
      },
      async execute(_snapshot, arm) {
        if (arm.kind === "mask_candidate") throw new Error("forced");
        return {
          armId: arm.armId,
          status: "ok",
          outputHash: `output-${arm.kind}`,
          validatorScore: 1,
          validatorPassed: true,
          latencyMs: 1
        };
      }
    };
    const result = await executeShadowReplay(executor, request());
    expect(result.comparable).toBe(false);
    expect(result.abstainReason).toBe("one_or_more_shadow_arms_failed");
    expect(result.arms.find((arm) => arm.armId.includes(":mask:"))?.status).toBe("error");
  });
});
