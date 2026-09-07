import { describe, expect, it } from "vitest";

import {
  createVersionedMemoryRecord,
  type AggregatorIdentity,
  type MemoryCaptureScope,
  type ShadowCaptureContext,
  type ShadowCaptureEvent,
  type VersionedMemoryRecord,
} from "./capture-contracts.js";
import {
  InMemoryShadowCaptureSidecarStore,
  type ShadowCaptureSidecarStore,
} from "./capture-sidecar.js";
import {
  createStrongL2CommitReadbackReceipt,
  InMemoryL2StagedAggregationAuditStore,
  l2CommitReadbackVerifiedFieldSetHash,
  L2StagedShadowAggregationCoordinator,
  type L2AggregationBeginInput,
  type L2AggregationRunToken,
  type StagedL2OutputInput,
  type StrongL2CommitReadbackReceiptInput,
  type ValidatedL2StagedToken,
} from "./l2-staged-shadow-adapter.js";
import { canonicalHash } from "./observation-plane.js";

const context: ShadowCaptureContext = {
  captureId: "capture-l2-stage-1",
  capturedAt: "2026-09-04T15:55:00.000Z",
  origin: "production_capture",
  feedbackDepth: 0,
  taskRunId: "task-atlas-1",
};

const backendBindingHash = canonicalHash({
  backend: "exp015-reference",
  collection: "profiles-test",
  schemaVersion: "v1",
});

const scope: MemoryCaptureScope = {
  teamId: "team-1",
  userId: null,
  agentId: "agent-1",
  sessionKey: null,
  sessionId: null,
  taskId: null,
  projectId: "atlas",
  sceneName: "atlas-deployment",
};

const aggregator: AggregatorIdentity = {
  componentId: "scene-extractor",
  componentVersion: "shadow-stage-v1",
  promptId: "scene-extraction",
  promptVersion: "v3",
  promptHash: canonicalHash("aggregate prompt template"),
  modelId: "qwen3-4b",
  modelVersion: "Qwen3-4B-Instruct-2507",
  seed: 7,
};

function l1Record(id = "l1-atlas-region", version = 3): VersionedMemoryRecord {
  return createVersionedMemoryRecord({
    context,
    layer: "L1",
    recordId: id,
    logicalId: `logical-${id}`,
    version,
    content: "Atlas 部署区域是上海。",
    metadata: { type: "work_fact" },
    scope,
    entityBindings: { project: "atlas", region: "shanghai" },
    sourceL0: [{ layer: "L0", id: "msg-atlas-region", version: 1 }],
    createdAt: "2026-09-04T15:00:00.000Z",
    observedAt: "2026-09-04T15:10:00.000Z",
    capturePoint: "l1_write_receipt",
    persistenceReceiptHash: canonicalHash("l1 receipt"),
  });
}

function baseline(): VersionedMemoryRecord {
  return createVersionedMemoryRecord({
    context,
    layer: "L2",
    recordId: "profile:v1:atlas-deployment",
    logicalId: "scene-atlas-deployment",
    version: 4,
    content: "Atlas 原部署区域未知。",
    metadata: { filename: "atlas-deployment.md" },
    scope,
    entityBindings: { project: "atlas" },
    createdAt: "2026-09-01T00:00:00.000Z",
    observedAt: "2026-09-03T00:00:00.000Z",
    capturePoint: "l2_profile_commit_receipt",
    persistenceReceiptHash: canonicalHash("prior l2 receipt"),
  });
}

function beginInput(prior: VersionedMemoryRecord | null = null): L2AggregationBeginInput {
  return {
    aggregationRunId: prior ? "aggregate-atlas-update" : "aggregate-atlas-create",
    frozenAt: "2026-09-04T16:00:00.000Z",
    records: [l1Record()],
    aggregator,
    systemPromptHash: canonicalHash("system prompt bytes"),
    userPromptHash: canonicalHash("user prompt bytes"),
    toolSchemaHash: canonicalHash("tool schema bytes"),
    configHash: canonicalHash("generation config bytes"),
    baseline: prior,
  };
}

function staged(action: "create" | "update" = "create"): StagedL2OutputInput {
  const content = "Atlas 部署区域是上海。";
  return {
    action,
    recordId: "profile:v1:atlas-deployment",
    logicalId: "scene-atlas-deployment",
    content,
    metadata: { filename: "atlas-deployment.md" },
    scope,
    entityBindings: { project: "atlas" },
    createdAt: action === "update" ? "2026-09-01T00:00:00.000Z" : "2026-09-04T16:00:30.000Z",
    claims: [{
      claimId: "atlas-region",
      span: { start: 0, end: content.length },
      sources: [{ layer: "L1", id: "l1-atlas-region", version: 3 }],
    }],
  };
}

function coordinator(
  eventStore: ShadowCaptureSidecarStore = new InMemoryShadowCaptureSidecarStore(),
  verifyCommittedSnapshot: () => boolean = () => true,
) {
  const auditStore = new InMemoryL2StagedAggregationAuditStore();
  return {
    auditStore,
    eventStore,
    coordinator: new L2StagedShadowAggregationCoordinator({
      enabled: true,
      context,
      eventStore,
      auditStore,
      scopeAuthority: { teamId: "team-1", agentId: "agent-1" },
      readbackAuthority: {
        authorityId: "tcvdb-profile-readback",
        authorityVersion: "v1",
        authorityBindingHash: backendBindingHash,
        verifyCommittedSnapshot,
      },
    }),
  };
}

async function prepareAndValidate(
  harness: ReturnType<typeof coordinator>,
  prior: VersionedMemoryRecord | null = null,
  output = staged(prior ? "update" : "create"),
) {
  const runToken = await harness.coordinator.beginRun(beginInput(prior));
  expect(runToken).not.toBeNull();
  const stagedToken = await harness.coordinator.validateStagedOutput(runToken!, output);
  return { runToken: runToken!, stagedToken };
}

function readbackInput(
  runToken: L2AggregationRunToken,
  stagedToken: ValidatedL2StagedToken,
  prior: VersionedMemoryRecord | null = null,
  overrides: Partial<StrongL2CommitReadbackReceiptInput> = {},
): StrongL2CommitReadbackReceiptInput {
  return {
    schemaVersion: "tdai-l2-commit-readback-receipt.v1",
    acknowledgementBasis: "committed_row_readback",
    aggregationRunId: runToken.aggregationRunId,
    runTokenHash: runToken.tokenHash,
    stagedTokenHash: stagedToken.tokenHash,
    stableOutputId: stagedToken.outputId,
    logicalId: stagedToken.logicalId,
    committedVersion: prior ? prior.payload.record.version + 1 : 1,
    contentHash: stagedToken.contentHash,
    metadataHash: stagedToken.metadataHash,
    scopeHash: stagedToken.scopeHash,
    entityBindingHash: stagedToken.entityBindingHash,
    priorVersion: prior?.payload.record.version ?? null,
    baselineRecordDigest: prior?.payload.recordDigest ?? null,
    createdAt: prior?.payload.createdAt ?? "2026-09-04T16:00:30.000Z",
    committedAt: "2026-09-04T16:02:00.000Z",
    readbackAt: "2026-09-04T16:02:01.000Z",
    commitOperationId: prior ? "commit-atlas-update" : "commit-atlas-create",
    storageRevision: prior ? "profile-revision-5" : "profile-revision-1",
    backendBindingHash,
    readOperationId: prior ? "read-atlas-update" : "read-atlas-create",
    verifiedFieldSetHash: l2CommitReadbackVerifiedFieldSetHash(),
    readerAuthorityId: "tcvdb-profile-readback",
    readerAuthorityVersion: "v1",
    ...overrides,
  };
}

describe("L2 staged shadow aggregation coordinator", () => {
  it("captures an exact update only after a matching strong commit readback", async () => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const harness = coordinator(events);
    const prior = baseline();
    const { runToken, stagedToken } = await prepareAndValidate(harness, prior);
    expect(stagedToken).not.toBeNull();
    expect(harness.auditStore.audits.map((audit) => audit.status)).toEqual(["prepared", "validated"]);
    expect(Object.isFrozen(runToken)).toBe(true);

    const receipt = createStrongL2CommitReadbackReceipt(readbackInput(runToken, stagedToken!, prior));

    await expect(harness.coordinator.finalizeAfterCommit(stagedToken!, receipt)).resolves.toBe(true);
    await harness.coordinator.drain();

    expect(events.events.map((event) => event.eventType)).toEqual([
      "versioned_memory_record",
      "aggregation_manifest",
    ]);
    const output = events.events[0];
    expect(output?.eventType === "versioned_memory_record" && output.payload).toMatchObject({
      record: { layer: "L2", id: "profile:v1:atlas-deployment", version: 5 },
      content: "Atlas 部署区域是上海。",
      persistenceReceiptHash: receipt.receiptHash,
      predecessors: [{ relation: "supersedes", record: { layer: "L2", id: prior.payload.record.id, version: 4 } }],
    });
    const manifest = events.events[1];
    expect(manifest?.eventType === "aggregation_manifest" && manifest).toMatchObject({
      aggregationRunId: "aggregate-atlas-update",
      claimCoverage: { complete: true },
      claims: [{
        claimId: "atlas-region",
        lineageStatus: "attributed",
        derivations: [{
          edgeVersion: 1,
          source: { layer: "L1", id: "l1-atlas-region", version: 3 },
        }],
      }],
    });
    expect(manifest?.eventType === "aggregation_manifest" && manifest.edges[0]?.edgeId).toMatch(/^edge:l1-l2:v1:[a-f0-9]{64}$/);
    expect(harness.auditStore.audits.at(-1)).toMatchObject({
      phase: "commit",
      status: "captured",
      exactLocalizationCaptureReady: false,
      exactL2DerivationCaptureReady: true,
      feedbackDepth: 0,
      optimizationReady: false,
      memoryIngestionAllowed: false,
    });
  });

  it("is default-off and produces neither prepared audit nor sidecar data", async () => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const audits = new InMemoryL2StagedAggregationAuditStore();
    const adapter = new L2StagedShadowAggregationCoordinator({ context, eventStore: events, auditStore: audits });

    await expect(adapter.beginRun(beginInput())).resolves.toBeNull();
    await adapter.drain();
    expect(events.events).toEqual([]);
    expect(audits.audits).toEqual([]);
  });

  it("refuses a recursive/untrusted context before it can mint a depth-0 prepared audit", async () => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const audits = new InMemoryL2StagedAggregationAuditStore();
    const recursiveContext = {
      ...context,
      origin: "self_supervision",
      feedbackDepth: 1,
    } as unknown as ShadowCaptureContext;
    const adapter = new L2StagedShadowAggregationCoordinator({
      enabled: true,
      context: recursiveContext,
      eventStore: events,
      auditStore: audits,
      scopeAuthority: { teamId: "team-1", agentId: "agent-1" },
      readbackAuthority: {
        authorityId: "tcvdb-profile-readback",
        authorityVersion: "v1",
        authorityBindingHash: backendBindingHash,
        verifyCommittedSnapshot: () => true,
      },
    });

    await expect(adapter.beginRun(beginInput())).resolves.toBeNull();
    expect(events.events).toEqual([]);
    expect(audits.audits).toEqual([]);
  });

  it("rejects delete/rename/merge before any staged token can be issued", async () => {
    for (const action of ["delete", "rename", "merge"]) {
      const harness = coordinator();
      const output = { ...staged(), action };
      const { stagedToken } = await prepareAndValidate(harness, null, output);
      expect(stagedToken).toBeNull();
      expect(harness.auditStore.audits.at(-1)).toMatchObject({
        status: "unresolved",
        blockers: ["UNSUPPORTED_STAGED_ACTION"],
        optimizationReady: false,
      });
    }
  });

  it("keeps a missing claim source unresolved and writes no capture event", async () => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const harness = coordinator(events);
    const output = staged();
    output.claims[0]!.sources = [];

    const { stagedToken } = await prepareAndValidate(harness, null, output);

    expect(stagedToken).toBeNull();
    expect(events.events).toEqual([]);
    expect(harness.auditStore.audits.at(-1)).toMatchObject({
      phase: "validate",
      status: "unresolved",
      blockers: ["MISSING_CLAIM_SOURCE"],
      exactLocalizationCaptureReady: false,
      exactL2DerivationCaptureReady: false,
    });
  });

  it.each([
    { name: "skipped create version", committedVersion: 2, contentHash: null, reason: "NON_MONOTONIC_COMMITTED_VERSION" },
    { name: "content mismatch", committedVersion: 1, contentHash: canonicalHash("different bytes"), reason: "READBACK_CONTENT_MISMATCH" },
  ])("fails closed on a $name readback receipt", async ({ committedVersion, contentHash, reason }) => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const harness = coordinator(events);
    const { runToken, stagedToken } = await prepareAndValidate(harness);
    const receipt = createStrongL2CommitReadbackReceipt(readbackInput(runToken, stagedToken!, null, {
      committedVersion,
      contentHash: contentHash ?? stagedToken!.contentHash,
    }));

    await expect(harness.coordinator.finalizeAfterCommit(stagedToken!, receipt)).resolves.toBe(false);
    expect(events.events).toEqual([]);
    expect(harness.auditStore.audits.at(-1)).toMatchObject({
      phase: "commit",
      status: "unresolved",
      blockers: [reason],
      optimizationReady: false,
    });
  });

  it("refuses to mint a version-zero readback receipt", async () => {
    const harness = coordinator();
    const { runToken, stagedToken } = await prepareAndValidate(harness);
    expect(() => createStrongL2CommitReadbackReceipt(readbackInput(runToken, stagedToken!, null, {
      committedVersion: 0,
    }))).toThrow(/positive integer/);
  });

  it("rejects a validly hashed receipt from a different aggregation run", async () => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const harness = coordinator(events);
    const { runToken, stagedToken } = await prepareAndValidate(harness);
    const receipt = createStrongL2CommitReadbackReceipt(readbackInput(runToken, stagedToken!, null, {
      aggregationRunId: "aggregate-unrelated-run",
    }));

    await expect(harness.coordinator.finalizeAfterCommit(stagedToken!, receipt)).resolves.toBe(false);
    expect(events.events).toEqual([]);
    expect(harness.auditStore.audits.at(-1)).toMatchObject({
      blockers: ["READBACK_CAUSAL_BINDING_MISMATCH"],
      exactL2DerivationCaptureReady: false,
    });
  });

  it("rejects entity rebinding inside one stable L2 version chain", async () => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const harness = coordinator(events);
    const output = staged("update");
    output.entityBindings = { project: "atlas", region: "shanghai" };

    const { stagedToken } = await prepareAndValidate(harness, baseline(), output);

    expect(stagedToken).toBeNull();
    expect(events.events).toEqual([]);
    expect(harness.auditStore.audits.at(-1)).toMatchObject({
      blockers: ["STAGED_ENTITY_BINDING_MISMATCH"],
      exactL2DerivationCaptureReady: false,
    });
  });

  it("does not treat a self-consistent digest as storage authority", async () => {
    const events = new InMemoryShadowCaptureSidecarStore();
    const harness = coordinator(events, () => false);
    const { runToken, stagedToken } = await prepareAndValidate(harness);
    const receipt = createStrongL2CommitReadbackReceipt(readbackInput(runToken, stagedToken!));

    await expect(harness.coordinator.finalizeAfterCommit(stagedToken!, receipt)).resolves.toBe(false);
    expect(events.events).toEqual([]);
    expect(harness.auditStore.audits.at(-1)).toMatchObject({
      blockers: ["READBACK_AUTHORITY_REJECTED"],
      exactL2DerivationCaptureReady: false,
    });
  });

  it("treats atomic sidecar batch failure as unresolved and never emits one half", async () => {
    class FailingSidecar implements ShadowCaptureSidecarStore {
      readonly events: ShadowCaptureEvent[] = [];
      async append(_event: ShadowCaptureEvent): Promise<void> {
        throw new Error("sidecar unavailable");
      }
      async appendBatch(_events: ShadowCaptureEvent[]): Promise<void> {
        throw new Error("sidecar unavailable");
      }
    }
    const sidecar = new FailingSidecar();
    const harness = coordinator(sidecar);
    const { runToken, stagedToken } = await prepareAndValidate(harness);
    const receipt = createStrongL2CommitReadbackReceipt(readbackInput(runToken, stagedToken!));

    await expect(harness.coordinator.finalizeAfterCommit(stagedToken!, receipt)).resolves.toBe(false);
    expect(sidecar.events).toEqual([]);
    expect(harness.auditStore.audits.at(-1)).toMatchObject({
      status: "unresolved",
      blockers: ["SIDECAR_APPEND_FAILED"],
      exactLocalizationCaptureReady: false,
      exactL2DerivationCaptureReady: false,
    });
  });
});
