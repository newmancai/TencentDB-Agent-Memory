import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  assertShadowCaptureEvent,
  auditCaptureCompleteness,
  createAggregationManifest,
  createMemoryUseTrace,
  createVersionedMemoryRecord,
  freezeAggregationInputs,
  materializeL0Authority,
  type MemoryCaptureScope,
  type ShadowCaptureContext,
  type ShadowCaptureEvent,
  type VersionedMemoryRecord,
} from "./capture-contracts.js";
import {
  InMemoryShadowCaptureSidecarStore,
  JsonlShadowCaptureSidecarStore,
} from "./capture-sidecar.js";
import { canonicalHash } from "./observation-plane.js";

const context: ShadowCaptureContext & { taskRunId: string } = {
  captureId: "capture-atlas-1",
  capturedAt: "2026-09-04T00:05:00.000Z",
  origin: "production_capture",
  feedbackDepth: 0,
  taskRunId: "task-atlas-1",
};

const scope: MemoryCaptureScope = {
  teamId: "team-1",
  userId: "user-1",
  agentId: "agent-1",
  sessionKey: "session-key-1",
  sessionId: "session-1",
  taskId: "task-atlas-1",
  projectId: "atlas",
  sceneName: "atlas-deployment",
};

function l1Record(overrides: Partial<Parameters<typeof createVersionedMemoryRecord>[0]> = {}): VersionedMemoryRecord {
  return createVersionedMemoryRecord({
    context,
    layer: "L1",
    recordId: "l1-atlas-region",
    logicalId: "claim-atlas-region",
    version: 3,
    content: "Atlas 部署区域是上海。",
    metadata: { type: "work_fact", priority: 90 },
    scope,
    entityBindings: { project: "atlas", region: "shanghai" },
    sourceL0: [{ layer: "L0", id: "msg-atlas-1", version: 1 }],
    predecessors: [],
    createdAt: "2026-09-04T00:01:00.000Z",
    observedAt: "2026-09-04T00:02:00.000Z",
    capturePoint: "l1_write_receipt",
    persistenceReceiptHash: canonicalHash("l1-write-receipt"),
    ...overrides,
  });
}

function l2Record(overrides: Partial<Parameters<typeof createVersionedMemoryRecord>[0]> = {}): VersionedMemoryRecord {
  return createVersionedMemoryRecord({
    context,
    layer: "L2",
    recordId: "l2-atlas-deployment",
    logicalId: "scene-atlas-deployment",
    version: 5,
    content: "Atlas 部署区域是上海。",
    metadata: { filename: "atlas-deployment.md" },
    scope,
    entityBindings: { project: "atlas", region: "shanghai" },
    createdAt: "2026-09-04T00:03:00.000Z",
    observedAt: "2026-09-04T00:04:00.000Z",
    capturePoint: "l2_profile_commit_receipt",
    persistenceReceiptHash: canonicalHash("l2-profile-commit"),
    ...overrides,
  });
}

function resignEvent<T extends ShadowCaptureEvent>(event: T): T {
  const clone = structuredClone(event);
  const { eventId: _eventId, eventHash: _eventHash, ...body } = clone;
  const eventHash = canonicalHash(body);
  return {
    ...clone,
    eventHash,
    eventId: `capture:${clone.eventType}:${eventHash.slice(0, 32)}`,
  } as T;
}

function authority(role: "user" | "assistant" = "user") {
  const content = "Atlas 部署区域是上海。";
  return materializeL0Authority({
    context,
    source: {
      recordId: "msg-atlas-1",
      version: 1,
      role,
      content,
      recordedAt: "2026-09-04T00:00:00.000Z",
      scope,
      materializationBasis: "persisted_l0_row",
    },
    assertions: [{
      assertionId: "assert-atlas-region",
      claimId: "atlas-region",
      span: { start: 0, end: content.length },
      supports: [{ layer: "L1", id: "l1-atlas-region", version: 3 }],
    }],
  });
}

function frozenInputs(record = l1Record()) {
  return freezeAggregationInputs({
    aggregationRunId: "aggregate-atlas-1",
    frozenAt: "2026-09-04T00:02:30.000Z",
    aggregator: {
      componentId: "scene-extractor",
      componentVersion: "capture-prototype-v1",
      promptId: "scene-extraction",
      promptVersion: "v1",
      promptHash: canonicalHash("scene prompt"),
      modelId: "qwen3-4b",
      modelVersion: "Qwen3-4B-Instruct-2507",
      seed: 7,
    },
    records: [record],
  });
}

function manifest(l1 = l1Record(), l2 = l2Record()) {
  return createAggregationManifest({
    context,
    manifestId: "manifest-atlas-1",
    manifestVersion: 2,
    frozenInputs: frozenInputs(l1),
    output: l2,
    aggregationCompletedAt: "2026-09-04T00:04:00.000Z",
    claims: [{
      claimId: "atlas-region",
      span: { start: 0, end: l2.payload.content.length },
      sources: [{
        edgeId: "edge-atlas-region-scene",
        edgeVersion: 4,
        source: { layer: "L1", id: "l1-atlas-region", version: 3 },
      }],
    }],
  });
}

function twoClaimManifest(l1 = l1Record(), l2 = l2Record()) {
  return createAggregationManifest({
    context,
    manifestId: "manifest-atlas-two-claims",
    manifestVersion: 1,
    frozenInputs: frozenInputs(l1),
    output: l2,
    aggregationCompletedAt: "2026-09-04T00:04:00.000Z",
    claims: [
      {
        claimId: "z-claim",
        span: { start: 0, end: 5 },
        sources: [{
          edgeId: "edge-atlas-region-scene",
          edgeVersion: 4,
          source: { layer: "L1", id: "l1-atlas-region", version: 3 },
        }],
      },
      {
        claimId: "a-claim",
        span: { start: 5, end: l2.payload.content.length },
        sources: [{
          edgeId: "edge-atlas-region-scene",
          edgeVersion: 4,
          source: { layer: "L1", id: "l1-atlas-region", version: 3 },
        }],
      },
    ],
  });
}

function trace(l1 = l1Record(), l2 = l2Record()) {
  return createMemoryUseTrace({
    context,
    traceId: "trace-atlas-1",
    traceVersion: 1,
    sessionId: "session-1",
    queryHash: canonicalHash("Atlas 部署在哪里？"),
    finalPromptHash: canonicalHash("prompt with memory"),
    modelId: "qwen3-4b",
    modelVersion: "Qwen3-4B-Instruct-2507",
    environmentHash: canonicalHash("environment-1"),
    accesses: [
      {
        accessId: "access-l1-atlas",
        record: l1,
        retrieval: {
          retrievalId: "retrieval-l1-atlas",
          retrievedAt: "2026-09-04T00:05:01.000Z",
          stage: "l1_hybrid",
          queryHash: canonicalHash("Atlas 部署在哪里？"),
          rank: 1,
          score: 0.91,
        },
        exposure: {
          exposureId: "exposure-l1-atlas",
          exposedAt: "2026-09-04T00:05:02.000Z",
          channel: "prompt_l1",
          representation: "l1_rendered_line",
          renderedText: "- [work_fact|atlas-deployment] Atlas 部署区域是上海。",
          truncated: false,
        },
        use: {
          useId: "use-l1-atlas",
          usedAt: "2026-09-04T00:05:03.000Z",
          consumer: "tool_call",
          evidence: [{
            basis: "tool_argument_dependency",
            evidenceId: "tool-deploy-region",
            evidenceHash: canonicalHash("region=shanghai"),
          }],
        },
        notExposedReason: null,
      },
      {
        accessId: "access-l2-atlas",
        record: l2,
        retrieval: {
          retrievalId: "retrieval-l2-atlas",
          retrievedAt: "2026-09-04T00:05:01.500Z",
          stage: "l2_scene_index",
          queryHash: canonicalHash("Atlas 部署在哪里？"),
          rank: 2,
          score: null,
        },
        exposure: null,
        use: null,
        notExposedReason: "budget_pruned",
      },
    ],
  });
}

describe("capture-time version and authority contracts", () => {
  it("seals a positive exact version as a deeply immutable shadow event", () => {
    const inputMetadata = { type: "work_fact" };
    const record = l1Record({ metadata: inputMetadata });
    inputMetadata.type = "mutated-after-capture";

    expect(record.payload.record).toEqual({ layer: "L1", id: "l1-atlas-region", version: 3 });
    expect(record.payload.metadata).toEqual({ type: "work_fact" });
    expect(record.payload.contentHash).toBe(canonicalHash(record.payload.content));
    expect(Object.isFrozen(record)).toBe(true);
    expect(Object.isFrozen(record.payload)).toBe(true);
    expect(record).toMatchObject({
      feedbackDepth: 0,
      memoryIngestionAllowed: false,
      mayWriteProductionMemory: false,
      mayEnqueueFeedback: false,
      feedbackReingestionEnabled: false,
      optimizationReady: false,
    });
  });

  it("rejects unresolved version zero instead of substituting timestamps or hashes", () => {
    expect(() => l1Record({ version: 0 })).toThrow(/positive integer/);
  });

  it("rejects re-signed versioned records outside the strict layer and capture-point enums", () => {
    const wrongLayer = structuredClone(l1Record()) as unknown as VersionedMemoryRecord;
    (wrongLayer.payload.record as { layer: string; version: number }).layer = "L0";
    (wrongLayer.payload.record as { layer: string; version: number }).version = 1;
    expect(() => assertShadowCaptureEvent(resignEvent(wrongLayer))).toThrow(/only support L1 or L2/);

    const wrongCapturePoint = structuredClone(l1Record()) as unknown as VersionedMemoryRecord;
    (wrongCapturePoint.payload as { capturePoint: string }).capturePoint = "post_hoc_guess";
    expect(() => assertShadowCaptureEvent(resignEvent(wrongCapturePoint))).toThrow(/Unsupported versioned record capturePoint/);
  });

  it("derives authority from persisted role and never promotes assistant output to a user fact", () => {
    const user = authority("user");
    const assistant = authority("assistant");
    expect(user.source).toMatchObject({ authorityClass: "user_assertion", eligibleForUserFactSupport: true });
    expect(assistant.source).toMatchObject({
      authorityClass: "assistant_generated_output",
      eligibleForUserFactSupport: false,
    });
    expect(assistant.assertions[0]).toMatchObject({ eligibleForUserFactSupport: false });
  });

  it("rejects unknown roles and non-materialized source spans", () => {
    const badRoleInput = {
      context,
      source: {
        recordId: "msg-atlas-1",
        version: 1 as const,
        role: "unknown",
        content: "Atlas",
        recordedAt: "2026-09-04T00:00:00.000Z",
        scope,
        materializationBasis: "persisted_l0_row" as const,
      },
      assertions: [],
    };
    expect(() => materializeL0Authority(badRoleInput)).toThrow(/Unsupported persisted L0 role/);
    expect(() => materializeL0Authority({
      ...badRoleInput,
      source: { ...badRoleInput.source, role: "user" },
      assertions: [{
        assertionId: "bad-span",
        claimId: "atlas",
        span: { start: 0, end: 99 },
        supports: [{ layer: "L1", id: "l1-atlas-region", version: 3 }],
      }],
    })).toThrow(/outside the materialized content/);
  });
});

describe("capture-time aggregation manifest", () => {
  it("freezes exact L1 inputs and maps every output claim to an independently versioned edge", () => {
    const result = manifest();
    expect(result.frozenInputs.inputs[0]).toMatchObject({
      record: { layer: "L1", id: "l1-atlas-region", version: 3 },
    });
    expect(result.output.record).toEqual({ layer: "L2", id: "l2-atlas-deployment", version: 5 });
    expect(result.claims[0]).toMatchObject({
      claimId: "atlas-region",
      lineageStatus: "attributed",
      derivations: [{
        edgeId: "edge-atlas-region-scene",
        edgeVersion: 4,
        source: { layer: "L1", id: "l1-atlas-region", version: 3 },
      }],
    });
    expect(result.edges[0]).toMatchObject({
      edgeId: "edge-atlas-region-scene",
      version: 4,
      from: { layer: "L1", id: "l1-atlas-region", version: 3 },
      to: { layer: "L2", id: "l2-atlas-deployment", version: 5 },
    });
    expect(result.claimCoverage.complete).toBe(true);
  });

  it("rejects a post-hoc source that was not in the pre-generation frozen set", () => {
    const l2 = l2Record();
    expect(() => createAggregationManifest({
      context,
      manifestId: "manifest-atlas-bad",
      manifestVersion: 1,
      frozenInputs: frozenInputs(),
      output: l2,
      aggregationCompletedAt: "2026-09-04T00:04:00.000Z",
      claims: [{
        claimId: "atlas-region",
        span: { start: 0, end: l2.payload.content.length },
        sources: [{
          edgeId: "edge-invented-after-generation",
          edgeVersion: 1,
          source: { layer: "L1", id: "l1-not-frozen", version: 1 },
        }],
      }],
    })).toThrow(/outside the frozen input set/);
  });

  it("requires every edge claim list to be unique and canonically sorted", () => {
    const duplicate = structuredClone(twoClaimManifest());
    duplicate.edges[0]!.claimIds = ["a-claim", "a-claim"];
    expect(() => assertShadowCaptureEvent(resignEvent(duplicate))).toThrow(/Duplicate aggregation edge claimId/);

    const unsorted = structuredClone(twoClaimManifest());
    unsorted.edges[0]!.claimIds.reverse();
    expect(() => assertShadowCaptureEvent(resignEvent(unsorted))).toThrow(/claim IDs must be sorted/);
  });

  it("requires edge-to-claim and claim-to-edge mappings to agree in both directions", () => {
    const oneWayOnly = structuredClone(manifest());
    oneWayOnly.claims[0]!.derivations = [];
    oneWayOnly.claims[0]!.lineageStatus = "unattributed";
    expect(() => assertShadowCaptureEvent(resignEvent(oneWayOnly))).toThrow(/edge\/claim reverse mapping mismatch/);
  });
});

describe("retrieved / exposed / used trace", () => {
  it("preserves retrieved-only candidates and requires evidence before calling a memory used", () => {
    const result = trace();
    expect(result.accesses.map((access) => access.highestObservedState)).toEqual(["used", "retrieved"]);
    expect(result.accesses[0]).toMatchObject({
      node: { layer: "L1", id: "l1-atlas-region", version: 3 },
      exposure: { exposureId: "exposure-l1-atlas", truncated: false },
      use: { useId: "use-l1-atlas" },
    });
    expect(result.accesses[1]).toMatchObject({ exposure: null, use: null, notExposedReason: "budget_pruned" });
  });

  it("rejects use without exposure and exposure-less retrieval without an explicit reason", () => {
    const base = {
      context,
      traceId: "trace-bad",
      traceVersion: 1,
      sessionId: "session-1",
      queryHash: canonicalHash("query"),
      finalPromptHash: canonicalHash("prompt"),
      modelId: "model",
      modelVersion: "1",
      environmentHash: canonicalHash("env"),
    };
    const retrieval = {
      retrievalId: "retrieval-bad",
      retrievedAt: "2026-09-04T00:05:01.000Z",
      stage: "l1_hybrid" as const,
      queryHash: canonicalHash("query"),
      rank: 1,
      score: 0.9,
    };
    expect(() => createMemoryUseTrace({
      ...base,
      accesses: [{
        accessId: "access-bad",
        record: l1Record(),
        retrieval,
        exposure: null,
        use: {
          useId: "use-bad",
          usedAt: "2026-09-04T00:05:03.000Z",
          consumer: "model_output",
          evidence: [{
            basis: "explicit_citation",
            evidenceId: "citation-1",
            evidenceHash: canonicalHash("citation"),
          }],
        },
        notExposedReason: "retrieval_only",
      }],
    })).toThrow(/cannot exist without exposure/);
    expect(() => createMemoryUseTrace({
      ...base,
      accesses: [{
        accessId: "access-bad",
        record: l1Record(),
        retrieval,
        exposure: null,
        use: null,
        notExposedReason: null,
      }],
    })).toThrow(/requires notExposedReason/);
  });
});

describe("capture packet audit and sidecar", () => {
  it("qualifies a complete addressable packet without claiming semantic correctness", () => {
    const l1 = l1Record();
    const l2 = l2Record();
    const audit = auditCaptureCompleteness([l1, l2, authority(), manifest(l1, l2), trace(l1, l2)]);
    expect(audit).toMatchObject({
      exactLocalizationCaptureReady: true,
      exactNodeIdentityReady: true,
      roleCorrectL0Ready: true,
      exactDerivationReady: true,
      runtimeAttributionReady: true,
      errors: [],
      safety: {
        shadowOnly: true,
        memoryIngestionAllowed: false,
        mayWriteProductionMemory: false,
        mayEnqueueFeedback: false,
        optimizationReady: false,
      },
    });
  });

  it("reports absent authority and unattributed claims instead of inventing edges", () => {
    const l1 = l1Record();
    const l2 = l2Record();
    const unattributed = createAggregationManifest({
      context,
      manifestId: "manifest-unattributed",
      manifestVersion: 1,
      frozenInputs: frozenInputs(l1),
      output: l2,
      aggregationCompletedAt: "2026-09-04T00:04:00.000Z",
      claims: [{ claimId: "atlas-region", span: { start: 0, end: l2.payload.content.length }, sources: [] }],
    });
    const audit = auditCaptureCompleteness([l1, l2, unattributed, trace(l1, l2)]);
    expect(audit.exactLocalizationCaptureReady).toBe(false);
    expect(audit.errors).toContain("missing_materialized_l0:L0\u001fmsg-atlas-1\u001f1->L1\u001fl1-atlas-region\u001f3");
    expect(audit.errors).toContain("unattributed_l2_claim:manifest-unattributed:atlas-region");
  });

  it("compares every frozen L1 identity field against the captured record snapshot", () => {
    const frozenRecord = l1Record();
    const output = l2Record();
    const changedRecord = l1Record({
      logicalId: "claim-atlas-region-other",
      content: "Atlas 部署区域是北京。",
      scope: { ...scope, projectId: "other-project" },
      entityBindings: { project: "other-project", region: "beijing" },
    });
    const audit = auditCaptureCompleteness([changedRecord, output, manifest(frozenRecord, output)]);
    const inputKey = "L1\u001fl1-atlas-region\u001f3";
    expect(audit.errors).toEqual(expect.arrayContaining([
      `missing_or_mismatched_l1_input:${inputKey}`,
      `mismatched_l1_logical_id:${inputKey}`,
      `mismatched_l1_content_hash:${inputKey}`,
      `mismatched_l1_scope_hash:${inputKey}`,
      `mismatched_l1_entity_binding_hash:${inputKey}`,
    ]));
    expect(audit.exactDerivationReady).toBe(false);
  });

  it("compares the manifest L2 logical ID, content hash, and record digest against its snapshot", () => {
    const input = l1Record();
    const manifestedOutput = l2Record();
    const changedOutput = l2Record({
      logicalId: "scene-atlas-deployment-other",
      content: "Atlas 部署区域是北京。",
    });
    const audit = auditCaptureCompleteness([input, changedOutput, manifest(input, manifestedOutput)]);
    const outputKey = "L2\u001fl2-atlas-deployment\u001f5";
    expect(audit.errors).toEqual(expect.arrayContaining([
      `missing_or_mismatched_l2_output:${outputKey}`,
      `mismatched_l2_logical_id:${outputKey}`,
      `mismatched_l2_content_hash:${outputKey}`,
    ]));
    expect(audit.exactDerivationReady).toBe(false);
  });

  it("rejects different manifests that claim the same exact L2 output version", () => {
    const input = l1Record();
    const output = l2Record();
    const secondManifest = createAggregationManifest({
      context,
      manifestId: "manifest-atlas-conflict",
      manifestVersion: 1,
      frozenInputs: frozenInputs(input),
      output,
      aggregationCompletedAt: "2026-09-04T00:04:00.000Z",
      claims: [{
        claimId: "atlas-region",
        span: { start: 0, end: output.payload.content.length },
        sources: [{
          edgeId: "edge-atlas-region-scene",
          edgeVersion: 4,
          source: { layer: "L1", id: "l1-atlas-region", version: 3 },
        }],
      }],
    });
    const audit = auditCaptureCompleteness([input, output, manifest(input, output), secondManifest]);
    expect(audit.errors).toContain("conflicting_aggregation_manifests:L2\u001fl2-atlas-deployment\u001f5");
    expect(audit.exactDerivationReady).toBe(false);
  });

  it("requires every L2 supersedes predecessor snapshot and matching scope/entity bindings", () => {
    const missingPredecessor = l2Record({
      predecessors: [{
        relation: "supersedes",
        record: { layer: "L2", id: "l2-atlas-deployment", version: 4 },
      }],
    });
    const missingAudit = auditCaptureCompleteness([missingPredecessor]);
    expect(missingAudit.errors).toContain(
      "missing_predecessor_snapshot:L2\u001fl2-atlas-deployment\u001f4->L2\u001fl2-atlas-deployment\u001f5",
    );

    const predecessor = l2Record({
      version: 4,
      scope: { ...scope, projectId: "other-project" },
      entityBindings: { project: "other-project", region: "beijing" },
      persistenceReceiptHash: canonicalHash("l2-profile-commit-v4"),
    });
    const current = l2Record({
      predecessors: [{
        relation: "supersedes",
        record: {
          layer: "L2",
          id: predecessor.payload.record.id,
          version: predecessor.payload.record.version,
        },
      }],
    });
    const mismatchAudit = auditCaptureCompleteness([predecessor, current]);
    const relation = "L2\u001fl2-atlas-deployment\u001f4->L2\u001fl2-atlas-deployment\u001f5";
    expect(mismatchAudit.errors).toEqual(expect.arrayContaining([
      `l2_supersedes_scope_mismatch:${relation}`,
      `l2_supersedes_entity_binding_mismatch:${relation}`,
    ]));
    expect(mismatchAudit.exactNodeIdentityReady).toBe(false);
  });

  it("rejects duplicate or conflicting immutable identities before appending", async () => {
    const store = new InMemoryShadowCaptureSidecarStore();
    const first = l1Record();
    const conflict = l1Record({ content: "Atlas 部署区域是北京。" });
    await store.append(first);
    await expect(store.append(first)).rejects.toThrow(/Duplicate capture event/);
    await expect(store.append(conflict)).rejects.toThrow(/Immutable capture identity conflict/);
    expect(store.events).toHaveLength(1);
  });

  it("round-trips an all-or-validated batch through the isolated JSONL sidecar", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-shadow-capture-"));
    try {
      const store = new JsonlShadowCaptureSidecarStore(root);
      const events: ShadowCaptureEvent[] = [l1Record(), l2Record(), authority()];
      await store.appendBatch(events);
      expect(existsSync(store.filePath)).toBe(true);
      expect(store.readAll()).toHaveLength(3);
      const reopened = new JsonlShadowCaptureSidecarStore(root);
      await reopened.append(manifest(events[0] as VersionedMemoryRecord, events[1] as VersionedMemoryRecord));
      expect(reopened.readAll()).toHaveLength(4);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("rejects recursive origins even from an untyped caller", () => {
    expect(() => l1Record({
      context: { ...context, origin: "self_supervision", feedbackDepth: 1 } as unknown as ShadowCaptureContext,
    })).toThrow(/cannot be self-supervision/);
  });

  it("makes the sidecar writer reject recursive depth and origin, not only the builders", async () => {
    const store = new InMemoryShadowCaptureSidecarStore();
    const originRecursive = structuredClone(l1Record()) as unknown as Record<string, unknown>;
    originRecursive.origin = "self_supervision";
    await expect(store.append(originRecursive as unknown as ShadowCaptureEvent)).rejects.toThrow(/cannot be self-supervision/);

    const depthRecursive = structuredClone(l1Record()) as unknown as Record<string, unknown>;
    depthRecursive.feedbackDepth = 1;
    await expect(store.append(depthRecursive as unknown as ShadowCaptureEvent)).rejects.toThrow(/feedbackDepth must be 0/);
    expect(store.events).toEqual([]);
  });
});
