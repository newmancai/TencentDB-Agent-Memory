import { describe, expect, it } from "vitest";

import {
  createVersionedMemoryRecord,
  type AggregatorIdentity,
  type MemoryCaptureScope,
  type ShadowCaptureContext,
  type VersionedMemoryRecord,
} from "./capture-contracts.js";
import { InMemoryShadowCaptureSidecarStore } from "./capture-sidecar.js";
import {
  createStrongL2CommitReadbackReceipt,
  InMemoryL2StagedAggregationAuditStore,
  L2StagedShadowAggregationCoordinator,
  type StrongL2CommitReadbackReceipt,
  type StrongL2CommitReadbackReceiptInput,
} from "./l2-staged-shadow-adapter.js";
import { canonicalHash } from "./observation-plane.js";
import {
  REFERENCE_PROFILE_COMMIT_EVIDENCE,
  ReferenceExactProfileCommitStore,
  type ReferenceExactProfileCommitRequest,
  type ReferenceExactProfileRow,
  type ReferenceProfileCommitFaultPoint,
} from "./profile-commit-conformance.js";

const context: ShadowCaptureContext = {
  captureId: "capture-exp-015",
  capturedAt: "2026-09-04T15:55:00.000Z",
  origin: "benchmark_fixture",
  feedbackDepth: 0,
  taskRunId: "task-exp-015",
};

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
  componentId: "exp-015-reference",
  componentVersion: "v1",
  promptId: "scene-extraction",
  promptVersion: "v1",
  promptHash: canonicalHash("prompt"),
  modelId: "fixture",
  modelVersion: "v1",
  seed: 15,
};

function store(instanceId = "exp-015-store"): ReferenceExactProfileCommitStore {
  return new ReferenceExactProfileCommitStore({
    instanceId,
    authorityId: "exp-015-readback",
    authorityVersion: "v1",
    now: () => "2026-09-04T16:02:00.000Z",
  });
}

function request(
  action: "create" | "update" = "create",
  overrides: Partial<ReferenceExactProfileCommitRequest> = {},
): ReferenceExactProfileCommitRequest {
  return {
    schemaVersion: "tdai-reference-exact-profile-commit.v1",
    action,
    commitOperationId: action === "create" ? "operation-create" : "operation-update",
    aggregationRunId: action === "create" ? "aggregation-create" : "aggregation-update",
    runTokenHash: canonicalHash(`${action}:run-token`),
    stagedTokenHash: canonicalHash(`${action}:staged-token`),
    stableOutputId: "profile:v1:atlas-deployment",
    logicalId: "scene-atlas-deployment",
    content: "Atlas 部署区域是上海。",
    metadata: { filename: "atlas-deployment.md" },
    scope,
    entityBindings: { project: "atlas" },
    expectedPriorVersion: action === "create" ? null : 4,
    baselineRecordDigest: action === "create" ? null : canonicalHash("baseline-record-v4"),
    createdAt: action === "create"
      ? "2026-09-04T16:00:30.000Z"
      : "2026-09-01T00:00:00.000Z",
    ...overrides,
  };
}

function seedRow(version = 4, overrides: Partial<ReferenceExactProfileRow> = {}): ReferenceExactProfileRow {
  return {
    stableOutputId: "profile:v1:atlas-deployment",
    logicalId: "scene-atlas-deployment",
    version,
    content: "Atlas 原部署区域未知。",
    metadata: { filename: "atlas-deployment.md" },
    scope,
    entityBindings: { project: "atlas" },
    createdAt: "2026-09-01T00:00:00.000Z",
    committedAt: "2026-09-03T00:00:00.000Z",
    commitOperationId: "seed-operation",
    storageRevision: "seed-revision-4",
    recordDigest: canonicalHash("baseline-record-v4"),
    ...overrides,
  };
}

function l1Record(): VersionedMemoryRecord {
  return createVersionedMemoryRecord({
    context,
    layer: "L1",
    recordId: "l1-atlas-region",
    logicalId: "logical-l1-atlas-region",
    version: 3,
    content: "Atlas 部署区域是上海。",
    metadata: { type: "work_fact" },
    scope,
    entityBindings: { project: "atlas", region: "shanghai" },
    sourceL0: [{ layer: "L0", id: "message-atlas-region", version: 1 }],
    createdAt: "2026-09-04T15:00:00.000Z",
    observedAt: "2026-09-04T15:10:00.000Z",
    capturePoint: "benchmark_fixture",
    persistenceReceiptHash: canonicalHash("l1-receipt"),
  });
}

function baselineRecord(): VersionedMemoryRecord {
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
    capturePoint: "benchmark_fixture",
    persistenceReceiptHash: canonicalHash("l2-baseline-receipt"),
  });
}

function receiptInput(receipt: StrongL2CommitReadbackReceipt): StrongL2CommitReadbackReceiptInput {
  const { receiptHash: _receiptHash, readerSnapshotDigest: _readerSnapshotDigest, ...input } = receipt;
  return input;
}

describe("EXP-015 isolated exact profile commit/readback reference", () => {
  it("labels every outcome as non-durable reference-only evidence", async () => {
    const reference = store();
    const outcome = await reference.commitAndReadback(request());

    expect(outcome.evidence).toEqual(REFERENCE_PROFILE_COMMIT_EVIDENCE);
    expect(outcome.evidence).toMatchObject({
      backendKind: "isolated_in_memory_reference",
      evidenceLevel: "protocol_conformance_only",
      durable: false,
      productionReady: false,
      optimizationReady: false,
    });
    expect(outcome.optimizationReady).toBe(false);
  });

  it.each([
    { action: "create" as const, prior: null, expectedVersion: 1 },
    { action: "update" as const, prior: baselineRecord(), expectedVersion: 5 },
  ])("feeds an authority-backed $action v$expectedVersion receipt into the staged coordinator", async ({ action, prior, expectedVersion }) => {
    const reference = store(`integration-${action}`);
    if (prior) reference.seedForConformance(seedRow(4, { recordDigest: prior.payload.recordDigest }));
    const events = new InMemoryShadowCaptureSidecarStore();
    const audits = new InMemoryL2StagedAggregationAuditStore();
    const coordinator = new L2StagedShadowAggregationCoordinator({
      enabled: true,
      context,
      eventStore: events,
      auditStore: audits,
      scopeAuthority: { teamId: "team-1", agentId: "agent-1" },
      readbackAuthority: reference.authority,
    });
    const runToken = await coordinator.beginRun({
      aggregationRunId: `integration-${action}`,
      frozenAt: "2026-09-04T16:00:00.000Z",
      records: [l1Record()],
      aggregator,
      systemPromptHash: canonicalHash("system prompt"),
      userPromptHash: canonicalHash("user prompt"),
      toolSchemaHash: canonicalHash("tool schema"),
      configHash: canonicalHash("config"),
      baseline: prior,
    });
    expect(runToken).not.toBeNull();
    const content = "Atlas 部署区域是上海。";
    const stagedToken = await coordinator.validateStagedOutput(runToken!, {
      action,
      recordId: "profile:v1:atlas-deployment",
      logicalId: "scene-atlas-deployment",
      content,
      metadata: { filename: "atlas-deployment.md" },
      scope,
      entityBindings: { project: "atlas" },
      createdAt: prior?.payload.createdAt ?? "2026-09-04T16:00:30.000Z",
      claims: [{
        claimId: "atlas-region",
        span: { start: 0, end: content.length },
        sources: [{ layer: "L1", id: "l1-atlas-region", version: 3 }],
      }],
    });
    expect(stagedToken).not.toBeNull();

    const outcome = await reference.commitAndReadback(request(action, {
      commitOperationId: `integration-operation-${action}`,
      aggregationRunId: runToken!.aggregationRunId,
      runTokenHash: runToken!.tokenHash,
      stagedTokenHash: stagedToken!.tokenHash,
      expectedPriorVersion: prior?.payload.record.version ?? null,
      baselineRecordDigest: prior?.payload.recordDigest ?? null,
      createdAt: prior?.payload.createdAt ?? "2026-09-04T16:00:30.000Z",
    }));
    expect(outcome.status).toBe("committed");
    if (outcome.status !== "committed") throw new Error("expected committed reference outcome");

    await expect(coordinator.finalizeAfterCommit(stagedToken!, outcome.receipt)).resolves.toBe(true);
    expect(outcome.receipt.committedVersion).toBe(expectedVersion);
    expect(outcome.receipt.backendBindingHash).toBe(reference.authority.authorityBindingHash);
    expect(await reference.authority.verifyCommittedSnapshot(outcome.receipt)).toBe(true);
    expect(events.events.map((event) => event.eventType)).toEqual([
      "versioned_memory_record",
      "aggregation_manifest",
    ]);
    const capturedOutput = events.events[0];
    expect(capturedOutput?.eventType === "versioned_memory_record"
      ? capturedOutput.payload.recordDigest
      : null).toBe(outcome.row.recordDigest);
    expect(audits.audits.at(-1)).toMatchObject({
      status: "captured",
      exactL2DerivationCaptureReady: true,
      exactLocalizationCaptureReady: false,
      optimizationReady: false,
    });
  });

  it("assigns v1 itself and returns the identical receipt for an exact operation retry", async () => {
    const reference = store();
    const first = await reference.commitAndReadback(request());
    const retry = await reference.commitAndReadback(request());

    expect(first.status).toBe("committed");
    expect(retry.status).toBe("committed");
    if (first.status !== "committed" || retry.status !== "committed") throw new Error("expected committed outcomes");
    expect(first.receipt).toEqual(retry.receipt);
    expect(retry.row.version).toBe(1);
    expect(reference.readRowForConformance(request().stableOutputId)?.version).toBe(1);
  });

  it("rejects operation-id reuse with different bytes without advancing the row", async () => {
    const reference = store();
    await reference.commitAndReadback(request());

    const collision = await reference.commitAndReadback(request("create", { content: "different" }));

    expect(collision).toMatchObject({
      status: "conflict",
      reason: "OPERATION_ID_REUSE_MISMATCH",
      exactReadbackAvailable: false,
      observedVersion: 1,
    });
    expect(reference.readRowForConformance(request().stableOutputId)?.content).toBe("Atlas 部署区域是上海。");
  });

  it("keeps a legacy version-zero row unresolved instead of treating zero as absence", async () => {
    const reference = store();
    reference.seedForConformance(seedRow(0, { storageRevision: "legacy-v0" }));

    const outcome = await reference.commitAndReadback(request("update", { expectedPriorVersion: 1 }));

    expect(outcome).toMatchObject({
      status: "unresolved",
      reason: "LEGACY_VERSION_ZERO",
      exactReadbackAvailable: false,
      mutationState: "none",
    });
    expect(reference.readRowForConformance(request().stableOutputId)?.version).toBe(0);
  });

  it.each([
    {
      name: "create over an existing row",
      seed: true,
      input: request("create"),
      reason: "CREATE_TARGET_EXISTS",
    },
    {
      name: "update of a missing row",
      seed: false,
      input: request("update"),
      reason: "UPDATE_TARGET_MISSING",
    },
    {
      name: "stale update baseline",
      seed: true,
      input: request("update", { expectedPriorVersion: 3 }),
      reason: "CAS_VERSION_MISMATCH",
    },
    {
      name: "mismatched baseline digest",
      seed: true,
      input: request("update", { baselineRecordDigest: canonicalHash("wrong baseline") }),
      reason: "CAS_BASELINE_DIGEST_MISMATCH",
    },
  ])("returns a receipt-free conflict for $name", async ({ seed, input, reason }) => {
    const reference = store(`conflict-${reason}`);
    if (seed) reference.seedForConformance(seedRow());

    const outcome = await reference.commitAndReadback(input);

    expect(outcome.status).toBe("conflict");
    expect(outcome.reason).toBe(reason);
    expect(outcome.exactReadbackAvailable).toBe(false);
    expect("receipt" in outcome).toBe(false);
  });

  it("uses a deterministic CAS barrier so two updates have exactly one winner", async () => {
    const reference = store("concurrent-update");
    reference.seedForConformance(seedRow());
    reference.holdNextCasAttempts(2);
    const left = request("update", {
      commitOperationId: "concurrent-left",
      aggregationRunId: "concurrent-left",
      runTokenHash: canonicalHash("left-run"),
      stagedTokenHash: canonicalHash("left-stage"),
      content: "left wins or loses atomically",
    });
    const right = request("update", {
      commitOperationId: "concurrent-right",
      aggregationRunId: "concurrent-right",
      runTokenHash: canonicalHash("right-run"),
      stagedTokenHash: canonicalHash("right-stage"),
      content: "right wins or loses atomically",
    });

    const outcomes = await Promise.all([
      reference.commitAndReadback(left),
      reference.commitAndReadback(right),
    ]);

    expect(outcomes.map((outcome) => outcome.status).sort()).toEqual(["committed", "conflict"]);
    expect(outcomes.filter((outcome) => outcome.status === "committed")).toHaveLength(1);
    expect(outcomes.find((outcome) => outcome.status === "conflict")).toMatchObject({
      reason: "CAS_VERSION_MISMATCH",
      observedVersion: 5,
    });
    expect(reference.readRowForConformance(left.stableOutputId)?.version).toBe(5);
  });

  it("uses the same CAS point to make concurrent creates single-winner", async () => {
    const reference = store("concurrent-create");
    reference.holdNextCasAttempts(2);
    const left = request("create", { commitOperationId: "create-left", aggregationRunId: "create-left" });
    const right = request("create", {
      commitOperationId: "create-right",
      aggregationRunId: "create-right",
      runTokenHash: canonicalHash("create-right-run"),
      stagedTokenHash: canonicalHash("create-right-stage"),
    });

    const outcomes = await Promise.all([
      reference.commitAndReadback(left),
      reference.commitAndReadback(right),
    ]);

    expect(outcomes.map((outcome) => outcome.status).sort()).toEqual(["committed", "conflict"]);
    expect(outcomes.find((outcome) => outcome.status === "conflict")).toMatchObject({
      reason: "CREATE_TARGET_EXISTS",
      observedVersion: 1,
    });
    expect(reference.readRowForConformance(left.stableOutputId)?.version).toBe(1);
  });

  it("does not silently content-MD5-dedupe an explicit exact update", async () => {
    const reference = store("metadata-update");
    reference.seedForConformance(seedRow(4, { content: "unchanged bytes" }));

    const outcome = await reference.commitAndReadback(request("update", {
      content: "unchanged bytes",
      metadata: { filename: "atlas-deployment.md", policy: "new" },
    }));

    expect(outcome.status).toBe("committed");
    if (outcome.status !== "committed") throw new Error("expected committed update");
    expect(outcome.row.version).toBe(5);
    expect(outcome.row.metadata).toEqual({ filename: "atlas-deployment.md", policy: "new" });
  });

  it("rejects a newly self-consistent receipt that has no matching private ledger entry", async () => {
    const reference = store("ledger-authority");
    const outcome = await reference.commitAndReadback(request());
    if (outcome.status !== "committed") throw new Error("expected committed create");
    const forged = createStrongL2CommitReadbackReceipt({
      ...receiptInput(outcome.receipt),
      readOperationId: "attacker-recomputed-read",
    });

    expect(forged.receiptHash).not.toBe(outcome.receipt.receiptHash);
    expect(await reference.authority.verifyCommittedSnapshot(forged)).toBe(false);
  });

  it("rejects every rehashed committed-row field mismatch against the private ledger", async () => {
    const reference = store("field-mismatch");
    const outcome = await reference.commitAndReadback(request());
    if (outcome.status !== "committed") throw new Error("expected committed create");
    const original = receiptInput(outcome.receipt);
    const mutations: Array<Partial<StrongL2CommitReadbackReceiptInput>> = [
      { stableOutputId: "profile:v1:other" },
      { logicalId: "scene-other" },
      { contentHash: canonicalHash("other-content") },
      { metadataHash: canonicalHash({ other: true }) },
      { scopeHash: canonicalHash({ ...scope, projectId: "other" }) },
      { entityBindingHash: canonicalHash({ project: "other" }) },
      { createdAt: "2026-09-04T16:00:31.000Z" },
      { priorVersion: 1 },
      { baselineRecordDigest: canonicalHash("other-baseline") },
      { committedVersion: 2 },
      { commitOperationId: "other-operation" },
      { storageRevision: "other-revision" },
      { backendBindingHash: canonicalHash("other-backend") },
      { readOperationId: "other-read" },
      { verifiedFieldSetHash: canonicalHash(["partial"]) },
    ];

    for (const mutation of mutations) {
      const forged = createStrongL2CommitReadbackReceipt({ ...original, ...mutation });
      expect(await reference.authority.verifyCommittedSnapshot(forged), JSON.stringify(mutation)).toBe(false);
    }
    expect(await reference.authority.verifyCommittedSnapshot(outcome.receipt)).toBe(true);
  });

  it("keeps an earlier receipt verifiable through the immutable commit ledger", async () => {
    const reference = store("stale-receipt");
    const createRequest = request();
    const created = await reference.commitAndReadback(createRequest);
    if (created.status !== "committed") throw new Error("expected committed create");
    const updated = await reference.commitAndReadback(request("update", {
      expectedPriorVersion: 1,
      baselineRecordDigest: created.row.recordDigest,
      createdAt: createRequest.createdAt,
    }));
    if (updated.status !== "committed") throw new Error("expected committed update");

    expect(await reference.authority.verifyCommittedSnapshot(created.receipt)).toBe(true);
    expect(await reference.authority.verifyCommittedSnapshot(updated.receipt)).toBe(true);
    await expect(reference.commitAndReadback(createRequest)).resolves.toMatchObject({
      status: "committed",
      receipt: created.receipt,
    });
  });

  it("fails before commit without mutation and can safely retry the same operation", async () => {
    const reference = store("before-commit-fault");
    reference.injectFaultOnce("before_commit");

    const failed = await reference.commitAndReadback(request());
    expect(failed).toMatchObject({
      status: "unresolved",
      reason: "FAULT_BEFORE_COMMIT",
      mutationState: "none",
      exactReadbackAvailable: false,
    });
    expect(reference.readRowForConformance(request().stableOutputId)).toBeNull();

    const retried = await reference.commitAndReadback(request());
    expect(retried.status).toBe("committed");
    expect(reference.readRowForConformance(request().stableOutputId)?.version).toBe(1);
  });

  it.each([
    ["after_commit_before_ack", "FAULT_AFTER_COMMIT_BEFORE_ACK"],
    ["after_ack_before_readback", "FAULT_AFTER_ACK_BEFORE_READBACK"],
    ["readback_mismatch", "FAULT_READBACK_MISMATCH"],
  ] as const)("keeps a %s fault unresolved until an idempotent ledger recovery", async (fault, reason) => {
    const reference = store(`fault-${fault}`);
    reference.injectFaultOnce(fault as ReferenceProfileCommitFaultPoint);

    const failed = await reference.commitAndReadback(request());
    expect(failed).toMatchObject({
      status: "unresolved",
      reason,
      mutationState: "may_have_committed",
      exactReadbackAvailable: false,
    });
    expect("receipt" in failed).toBe(false);
    expect(reference.readRowForConformance(request().stableOutputId)?.version).toBe(1);

    const recovered = await reference.commitAndReadback(request());
    expect(recovered.status).toBe("committed");
    if (recovered.status !== "committed") throw new Error("expected idempotent recovery");
    expect(recovered.row.version).toBe(1);
    expect(await reference.authority.verifyCommittedSnapshot(recovered.receipt)).toBe(true);
  });
});
