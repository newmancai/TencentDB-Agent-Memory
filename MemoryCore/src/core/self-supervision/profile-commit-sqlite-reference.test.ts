import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { createStrongL2CommitReadbackReceipt } from "./l2-staged-shadow-adapter.js";
import { canonicalHash } from "./observation-plane.js";
import {
  SQLITE_PROFILE_REFERENCE_CLAIM_BOUNDARY,
  SQLITE_PROFILE_REFERENCE_RESULT,
  SqliteProfileCommitReference,
  commitPairWithWorkerBarrierForConformance,
  type SqliteReferenceExactL2ProfileCommitRequest,
} from "./profile-commit-sqlite-reference.js";

const tempDirs: string[] = [];

afterEach(() => {
  for (const dir of tempDirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

function databasePath(): string {
  const dir = mkdtempSync(path.join(tmpdir(), "tdai-exp015-sqlite-"));
  tempDirs.push(dir);
  return path.join(dir, "reference.sqlite");
}

function request(
  operationId: string,
  prior: { version: number; digest: string } | null = null,
  content = "Atlas 部署区域是上海。",
): SqliteReferenceExactL2ProfileCommitRequest {
  return {
    schemaVersion: "tdai-exact-l2-profile-commit.v1",
    aggregationRunId: `run:${operationId}`,
    runTokenHash: canonicalHash(`run-token:${operationId}`),
    stagedTokenHash: canonicalHash(`stage-token:${operationId}`),
    commitOperationId: operationId,
    expectedPriorVersion: prior?.version ?? null,
    baselineRecordDigest: prior?.digest ?? null,
    payload: {
      stableOutputId: "profile:v1:atlas",
      logicalId: "scene:atlas",
      content,
      metadata: { filename: "atlas.md" },
      scope: {
        teamId: "team-1",
        userId: null,
        agentId: "agent-1",
        sessionKey: null,
        sessionId: null,
        taskId: null,
        projectId: "atlas",
        sceneName: "atlas-deployment",
      },
      entityBindings: { project: "atlas" },
      createdAt: "2026-09-04T10:00:00.000Z",
    },
  };
}

describe("EXP-015 SQLite durable profile-commit reference", () => {
  it("assigns create v1/update N+1 and labels the result as reference-only", () => {
    const store = new SqliteProfileCommitReference(databasePath());
    const created = store.commitProfileExact(request("op-create"));
    expect(created).toMatchObject({
      status: "committed",
      committedVersion: 1,
      priorVersion: null,
      evidenceClass: SQLITE_PROFILE_REFERENCE_RESULT,
      claimBoundary: SQLITE_PROFILE_REFERENCE_CLAIM_BOUNDARY,
    });
    expect(created.status).toBe("committed");
    if (created.status !== "committed") throw new Error("fixture create failed");

    const updated = store.commitProfileExact(request(
      "op-update",
      { version: created.committedVersion, digest: created.recordDigest },
      "Atlas 部署区域是北京。",
    ));
    expect(updated).toMatchObject({ status: "committed", priorVersion: 1, committedVersion: 2 });
    expect(store.diagnosticCounts()).toMatchObject({ heads: 1, commits: 2, operations: 2 });
    store.close();
  });

  it("replays one operation idempotently and rejects operation-ID payload reuse", () => {
    const store = new SqliteProfileCommitReference(databasePath());
    const input = request("op-idempotent");
    const first = store.commitProfileExact(input);
    const replay = store.commitProfileExact(structuredClone(input));
    const collision = store.commitProfileExact(request("op-idempotent", null, "different payload"));

    expect(first.status).toBe("committed");
    expect(replay).toMatchObject({
      status: "committed",
      idempotentReplay: true,
      committedVersion: 1,
      storageRevision: first.status === "committed" ? first.storageRevision : "",
    });
    expect(collision).toMatchObject({
      status: "rejected",
      reason: "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    });
    expect(store.diagnosticCounts()).toEqual({ heads: 1, commits: 1, operations: 1, reads: 0 });
    store.close();
  });

  it("gives exactly one winner to two worker connections released by one shared barrier", async () => {
    const dbPath = databasePath();
    const setup = new SqliteProfileCommitReference(dbPath);
    const initial = setup.commitProfileExact(request("op-initial"));
    expect(initial.status).toBe("committed");
    if (initial.status !== "committed") throw new Error("fixture create failed");
    setup.close();
    const baseline = { version: initial.committedVersion, digest: initial.recordDigest };

    const results = await commitPairWithWorkerBarrierForConformance(dbPath, [
      request("op-writer-a", baseline, "writer A"),
      request("op-writer-b", baseline, "writer B"),
    ]);
    const winner = results.find((result) => result.status === "committed");
    const loser = results.find((result) => result.status === "conflict");

    expect(winner).toMatchObject({ status: "committed", committedVersion: 2 });
    expect(loser).toMatchObject({
      status: "conflict",
      reason: "STALE_BASELINE",
      observedVersion: 2,
    });
    expect(results.map((result) => result.status).sort()).toEqual(["committed", "conflict"]);
    const inspector = new SqliteProfileCommitReference(dbPath);
    expect(inspector.diagnosticCounts()).toMatchObject({ heads: 1, commits: 2, operations: 3 });
    inspector.close();
  }, 15_000);

  it("keeps an old receipt verifiable through update and close/reopen", () => {
    const dbPath = databasePath();
    const writer = new SqliteProfileCommitReference(dbPath);
    const committed = writer.commitProfileExact(request("op-durable"));
    expect(committed.status).toBe("committed");
    if (committed.status !== "committed") throw new Error("fixture commit failed");
    const backendBindingHash = writer.backendBindingHash;
    const read = writer.readCommittedProfile({
      stableOutputId: committed.stableOutputId,
      committedVersion: committed.committedVersion,
      commitOperationId: committed.commitOperationId,
      storageRevision: committed.storageRevision,
    });
    expect(read.status).toBe("found");
    if (read.status !== "found") throw new Error("durable readback failed");
    expect(read.snapshot.payload.content).toBe("Atlas 部署区域是上海。");

    const authority = writer.createReadbackAuthority();
    const receipt = createStrongL2CommitReadbackReceipt({
      schemaVersion: "tdai-l2-commit-readback-receipt.v1",
      acknowledgementBasis: "committed_row_readback",
      aggregationRunId: read.snapshot.aggregationRunId,
      runTokenHash: read.snapshot.runTokenHash,
      stagedTokenHash: read.snapshot.stagedTokenHash,
      stableOutputId: read.snapshot.stableOutputId,
      logicalId: read.snapshot.logicalId,
      committedVersion: read.snapshot.committedVersion,
      contentHash: read.snapshot.contentHash,
      metadataHash: read.snapshot.metadataHash,
      scopeHash: read.snapshot.scopeHash,
      entityBindingHash: read.snapshot.entityBindingHash,
      priorVersion: read.snapshot.priorVersion,
      baselineRecordDigest: read.snapshot.baselineRecordDigest,
      createdAt: read.snapshot.createdAt,
      committedAt: read.snapshot.committedAt,
      readbackAt: read.snapshot.readbackAt,
      commitOperationId: read.snapshot.commitOperationId,
      storageRevision: read.snapshot.storageRevision,
      backendBindingHash: read.snapshot.backendBindingHash,
      readOperationId: read.snapshot.readOperationId,
      verifiedFieldSetHash: read.snapshot.verifiedFieldSetHash,
      readerAuthorityId: authority.authorityId,
      readerAuthorityVersion: authority.authorityVersion,
    });
    expect(authority.verifyCommittedSnapshot(receipt)).toBe(true);

    const updated = writer.commitProfileExact(request(
      "op-after-old-receipt",
      { version: committed.committedVersion, digest: committed.recordDigest },
      "Atlas 部署区域是北京。",
    ));
    expect(updated).toMatchObject({ status: "committed", committedVersion: 2 });
    expect(authority.verifyCommittedSnapshot(receipt)).toBe(true);
    writer.close();

    const reader = new SqliteProfileCommitReference(dbPath);
    expect(reader.backendBindingHash).toBe(backendBindingHash);
    expect(reader.createReadbackAuthority().verifyCommittedSnapshot(receipt)).toBe(true);
    expect(reader.diagnosticCounts()).toEqual({ heads: 1, commits: 2, operations: 2, reads: 1 });
    reader.close();
  });

  it("rolls back journal/head/commit together and rejects legacy v0", () => {
    const dbPath = databasePath();
    const crashing = new SqliteProfileCommitReference(dbPath, {
      faultInjector(point) {
        if (point === "after_head_update") throw new Error("simulated crash");
      },
    });
    expect(crashing.commitProfileExact(request("op-crash"))).toMatchObject({
      status: "unresolved",
      reason: "SQLITE_TRANSACTION_FAILED",
    });
    expect(crashing.diagnosticCounts()).toEqual({ heads: 0, commits: 0, operations: 0, reads: 0 });
    crashing.close();

    const reopened = new SqliteProfileCommitReference(dbPath);
    const legacy = request("op-v0");
    legacy.expectedPriorVersion = 0;
    legacy.baselineRecordDigest = canonicalHash("legacy-v0");
    expect(reopened.commitProfileExact(legacy)).toMatchObject({
      status: "rejected",
      reason: "LEGACY_VERSION_ZERO_UNSUPPORTED",
    });
    expect(reopened.diagnosticCounts()).toEqual({ heads: 0, commits: 0, operations: 1, reads: 0 });
    reopened.close();
  });
});
