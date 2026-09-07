/**
 * Durable SQLite reference for the EXP-015 exact-profile commit contract.
 *
 * This is deliberately NOT an adapter for the production profile store.  Its
 * only claim is REFERENCE_SQLITE_PASS_BACKEND_UNVERIFIED: it gives the
 * conformance suite a small, inspectable implementation with real
 * transactions, durable immutable commits, operation idempotency, and
 * post-reopen readback.
 */

import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import type { DatabaseSync, SQLInputValue } from "node:sqlite";
import { isMainThread, parentPort, Worker, workerData } from "node:worker_threads";

import {
  createVersionedMemoryRecord,
  type CaptureJsonValue,
  type MemoryCaptureScope,
} from "./capture-contracts.js";
import {
  l2CommitReadbackVerifiedFieldSetHash,
  type L2CommitReadbackAuthority,
  type StrongL2CommitReadbackReceipt,
} from "./l2-staged-shadow-adapter.js";
import { canonicalHash } from "./observation-plane.js";

const require = createRequire(import.meta.url);

export const SQLITE_PROFILE_REFERENCE_RESULT = "REFERENCE_SQLITE_PASS_BACKEND_UNVERIFIED" as const;
export const SQLITE_PROFILE_REFERENCE_CLAIM_BOUNDARY =
  "SQLITE_DURABLE_REFERENCE_ONLY_NOT_TCVDB_LIVE_OR_PRODUCTION_READY" as const;

const SCHEMA_VERSION = "tdai-profile-commit-sqlite-reference.v1" as const;
const REQUEST_SCHEMA_VERSION = "tdai-exact-l2-profile-commit.v1" as const;
const SNAPSHOT_SCHEMA_VERSION = "tdai-sqlite-profile-commit-snapshot.v1" as const;
const AUTHORITY_ID = "tdai-profile-commit-sqlite-reference";
const AUTHORITY_VERSION = "v1";

export interface SqliteReferenceL2ProfilePayload {
  stableOutputId: string;
  logicalId: string;
  content: string;
  metadata: CaptureJsonValue;
  scope: MemoryCaptureScope;
  entityBindings: Record<string, string>;
  createdAt: string;
}

export interface SqliteReferenceExactL2ProfileCommitRequest {
  schemaVersion: typeof REQUEST_SCHEMA_VERSION;
  aggregationRunId: string;
  runTokenHash: string;
  stagedTokenHash: string;
  commitOperationId: string;
  expectedPriorVersion: number | null;
  baselineRecordDigest: string | null;
  payload: SqliteReferenceL2ProfilePayload;
}

interface SqliteReferenceResultEnvelope {
  evidenceClass: typeof SQLITE_PROFILE_REFERENCE_RESULT;
  claimBoundary: typeof SQLITE_PROFILE_REFERENCE_CLAIM_BOUNDARY;
  stableOutputId: string;
  commitOperationId: string;
  requestHash: string;
  idempotentReplay: boolean;
}

export interface SqliteReferenceCommittedResult extends SqliteReferenceResultEnvelope {
  status: "committed";
  priorVersion: number | null;
  committedVersion: number;
  storageRevision: string;
  committedAt: string;
  recordDigest: string;
}

export interface SqliteReferenceConflictResult extends SqliteReferenceResultEnvelope {
  status: "conflict";
  reason: "CREATE_ALREADY_EXISTS" | "STALE_BASELINE" | "BASELINE_DIGEST_MISMATCH";
  observedVersion: number | null;
  observedRecordDigest: string | null;
}

export interface SqliteReferenceRejectedResult extends SqliteReferenceResultEnvelope {
  status: "rejected";
  reason:
    | "INVALID_REQUEST"
    | "LEGACY_VERSION_ZERO_UNSUPPORTED"
    | "CREATE_BASELINE_DIGEST_PRESENT"
    | "UPDATE_BASELINE_DIGEST_MISSING"
    | "LOGICAL_ID_MISMATCH"
    | "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST";
}

export interface SqliteReferenceUnresolvedResult extends SqliteReferenceResultEnvelope {
  status: "unresolved";
  reason: "SQLITE_TRANSACTION_FAILED" | "SQLITE_READ_FAILED";
}

export type SqliteReferenceProfileCommitResult =
  | SqliteReferenceCommittedResult
  | SqliteReferenceConflictResult
  | SqliteReferenceRejectedResult
  | SqliteReferenceUnresolvedResult;

export interface SqliteReferenceCommittedSnapshot {
  schemaVersion: typeof SNAPSHOT_SCHEMA_VERSION;
  evidenceClass: typeof SQLITE_PROFILE_REFERENCE_RESULT;
  claimBoundary: typeof SQLITE_PROFILE_REFERENCE_CLAIM_BOUNDARY;
  backendBindingHash: string;
  aggregationRunId: string;
  runTokenHash: string;
  stagedTokenHash: string;
  stableOutputId: string;
  logicalId: string;
  committedVersion: number;
  priorVersion: number | null;
  baselineRecordDigest: string | null;
  contentHash: string;
  metadataHash: string;
  scopeHash: string;
  entityBindingHash: string;
  payload: SqliteReferenceL2ProfilePayload;
  createdAt: string;
  committedAt: string;
  commitOperationId: string;
  storageRevision: string;
  recordDigest: string;
  readbackAt: string;
  readOperationId: string;
  verifiedFieldSetHash: string;
}

export type SqliteReferenceReadbackResult =
  | { status: "found"; snapshot: SqliteReferenceCommittedSnapshot }
  | { status: "not_found"; evidenceClass: typeof SQLITE_PROFILE_REFERENCE_RESULT }
  | {
      status: "unavailable";
      evidenceClass: typeof SQLITE_PROFILE_REFERENCE_RESULT;
      reason: "SQLITE_READ_FAILED";
    };

export interface SqliteReferenceReadLocator {
  stableOutputId: string;
  committedVersion: number;
  commitOperationId: string;
  storageRevision: string;
}

export type SqliteReferenceFaultPoint =
  | "after_commit_insert"
  | "after_head_update"
  | "before_commit";

export interface SqliteProfileCommitReferenceOptions {
  now?: () => Date;
  idFactory?: () => string;
  faultInjector?: (point: SqliteReferenceFaultPoint) => void;
}

interface SqliteReferenceWorkerData {
  kind: "tdai-exp015-sqlite-reference-commit-worker.v1";
  dbPath: string;
  request: SqliteReferenceExactL2ProfileCommitRequest;
  barrier: SharedArrayBuffer;
}

interface SqliteReferenceWorkerMessage {
  ok: boolean;
  result?: SqliteReferenceProfileCommitResult;
  error?: string;
}

/**
 * Test-only contention harness. Each request is executed in its own worker and
 * DatabaseSync connection after both workers have reached a shared barrier.
 */
export async function commitPairWithWorkerBarrierForConformance(
  dbPath: string,
  requests: readonly [
    SqliteReferenceExactL2ProfileCommitRequest,
    SqliteReferenceExactL2ProfileCommitRequest,
  ],
): Promise<readonly [SqliteReferenceProfileCommitResult, SqliteReferenceProfileCommitResult]> {
  const barrier = new SharedArrayBuffer(Int32Array.BYTES_PER_ELEMENT * 2);
  const state = new Int32Array(barrier);
  const workerUrl = new URL(import.meta.url);
  const startWorker = (request: SqliteReferenceExactL2ProfileCommitRequest) => new Promise<SqliteReferenceProfileCommitResult>(
    (resolve, reject) => {
      let settled = false;
      const worker = new Worker(workerUrl, {
        execArgv: ["--import", "tsx"],
        workerData: {
          kind: "tdai-exp015-sqlite-reference-commit-worker.v1",
          dbPath,
          request: clone(request),
          barrier,
        } satisfies SqliteReferenceWorkerData,
      });
      worker.once("message", (message: SqliteReferenceWorkerMessage) => {
        settled = true;
        if (message.ok && message.result) resolve(message.result);
        else reject(new Error(message.error ?? "SQLite reference worker failed"));
      });
      worker.once("error", (error) => {
        settled = true;
        reject(error);
      });
      worker.once("exit", (code) => {
        if (!settled) reject(new Error(`SQLite reference worker exited before result (${code})`));
      });
    },
  );
  const first = startWorker(requests[0]);
  const second = startWorker(requests[1]);
  const both = Promise.all([first, second]);
  await Promise.race([
    waitForWorkerBarrier(state, 2, 10_000),
    both.then(() => { throw new Error("workers exited before the shared commit barrier was released"); }),
  ]);
  Atomics.store(state, 1, 1);
  Atomics.notify(state, 1, 2);
  const [left, right] = await both;
  return [left, right] as const;
}

type SqlRow = Record<string, SQLInputValue>;

interface StoredHead {
  stable_output_id: string;
  logical_id: string;
  committed_version: number;
  record_digest: string;
  revision_id: number;
}

interface StoredCommit extends SqlRow {
  revision_id: number;
  stable_output_id: string;
  logical_id: string;
  committed_version: number;
  prior_version: number | null;
  baseline_record_digest: string | null;
  aggregation_run_id: string;
  run_token_hash: string;
  staged_token_hash: string;
  commit_operation_id: string;
  request_hash: string;
  payload_json: string;
  content_hash: string;
  metadata_hash: string;
  scope_hash: string;
  entity_binding_hash: string;
  created_at: string;
  committed_at: string;
  record_digest: string;
}

interface StoredOperation extends SqlRow {
  request_hash: string;
  result_json: string;
}

interface StoredRead extends SqlRow {
  read_operation_id: string;
  revision_id: number;
  readback_at: string;
  verified_field_set_hash: string;
}

/**
 * Reference implementation only.  It never implements IMemoryStore and is
 * intentionally impossible to register as SceneExtractor/profile-sync output.
 */
export class SqliteProfileCommitReference {
  private readonly db: DatabaseSync;
  private readonly now: () => Date;
  private readonly idFactory: () => string;
  private readonly faultInjector?: (point: SqliteReferenceFaultPoint) => void;
  private closed = false;
  readonly backendBindingHash: string;

  constructor(readonly dbPath: string, options: SqliteProfileCommitReferenceOptions = {}) {
    if (!dbPath.trim()) throw new Error("dbPath is required");
    if (dbPath !== ":memory:") mkdirSync(path.dirname(dbPath), { recursive: true });
    const { DatabaseSync } = require("node:sqlite") as typeof import("node:sqlite");
    this.db = new DatabaseSync(dbPath);
    this.now = options.now ?? (() => new Date());
    this.idFactory = options.idFactory ?? randomUUID;
    this.faultInjector = options.faultInjector;
    this.db.exec("PRAGMA busy_timeout = 5000");
    this.db.exec("PRAGMA foreign_keys = ON");
    this.db.exec("PRAGMA journal_mode = WAL");
    this.createSchema();
    const instanceId = this.ensureInstanceId();
    this.backendBindingHash = canonicalHash({
      backendKind: "sqlite_durable_reference",
      instanceId,
      schemaVersion: SCHEMA_VERSION,
      tables: [
        "shadow_profile_reference_heads",
        "shadow_profile_reference_commits",
        "shadow_profile_reference_operations",
        "shadow_profile_reference_reads",
      ],
    });
  }

  close(): void {
    if (this.closed) return;
    this.db.close();
    this.closed = true;
  }

  commitProfileExact(
    request: SqliteReferenceExactL2ProfileCommitRequest,
  ): SqliteReferenceProfileCommitResult {
    const stableOutputId = nonEmptyString(request?.payload?.stableOutputId) ?? "<invalid>";
    const commitOperationId = nonEmptyString(request?.commitOperationId) ?? "<invalid>";
    let requestHash: string;
    try {
      requestHash = canonicalHash(request);
    } catch {
      requestHash = canonicalHash("invalid-request");
    }
    const base = (): SqliteReferenceResultEnvelope => ({
      evidenceClass: SQLITE_PROFILE_REFERENCE_RESULT,
      claimBoundary: SQLITE_PROFILE_REFERENCE_CLAIM_BOUNDARY,
      stableOutputId,
      commitOperationId,
      requestHash,
      idempotentReplay: false,
    });

    try {
      this.assertOpen();
      return this.immediateTransaction(() => {
        if (commitOperationId !== "<invalid>") {
          const existing = this.db.prepare(`
            SELECT request_hash, result_json
            FROM shadow_profile_reference_operations
            WHERE commit_operation_id = ?
          `).get(commitOperationId) as StoredOperation | undefined;
          if (existing) {
            if (existing.request_hash !== requestHash) {
              return freezeResult({
                ...base(),
                status: "rejected",
                reason: "OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
              });
            }
            const replay = JSON.parse(existing.result_json) as SqliteReferenceProfileCommitResult;
            return freezeResult({ ...replay, idempotentReplay: true });
          }
        }

        const invalidReason = validateRequest(request);
        if (invalidReason) {
          const result = freezeResult({ ...base(), status: "rejected" as const, reason: invalidReason });
          this.persistOperationIfAddressable(request, requestHash, result);
          return result;
        }

        const exactRequest = request as SqliteReferenceExactL2ProfileCommitRequest;
        const head = this.getStoredHead(exactRequest.payload.stableOutputId);
        let conflict: SqliteReferenceConflictResult | null = null;
        if (exactRequest.expectedPriorVersion === null) {
          if (head) {
            conflict = {
              ...base(),
              status: "conflict",
              reason: "CREATE_ALREADY_EXISTS",
              observedVersion: head.committed_version,
              observedRecordDigest: head.record_digest,
            };
          }
        } else if (!head || head.committed_version !== exactRequest.expectedPriorVersion) {
          conflict = {
            ...base(),
            status: "conflict",
            reason: "STALE_BASELINE",
            observedVersion: head?.committed_version ?? null,
            observedRecordDigest: head?.record_digest ?? null,
          };
        } else if (head.record_digest !== exactRequest.baselineRecordDigest) {
          conflict = {
            ...base(),
            status: "conflict",
            reason: "BASELINE_DIGEST_MISMATCH",
            observedVersion: head.committed_version,
            observedRecordDigest: head.record_digest,
          };
        } else if (head.logical_id !== exactRequest.payload.logicalId) {
          const rejected = freezeResult({
            ...base(),
            status: "rejected" as const,
            reason: "LOGICAL_ID_MISMATCH" as const,
          });
          this.persistOperationIfAddressable(exactRequest, requestHash, rejected);
          return rejected;
        }
        if (conflict) {
          const result = freezeResult(conflict);
          this.persistOperationIfAddressable(exactRequest, requestHash, result);
          return result;
        }

        const priorVersion = exactRequest.expectedPriorVersion;
        const committedVersion = priorVersion === null ? 1 : priorVersion + 1;
        const committedAt = this.nowIso();
        const payload = clone(exactRequest.payload);
        const hashes = payloadHashes(payload);
        const recordDigest = l2CaptureRecordDigest(payload, committedVersion, priorVersion, committedAt);
        const inserted = this.db.prepare(`
          INSERT INTO shadow_profile_reference_commits (
            stable_output_id, logical_id, committed_version, prior_version,
            baseline_record_digest, aggregation_run_id, run_token_hash,
            staged_token_hash, commit_operation_id, request_hash, payload_json,
            content_hash, metadata_hash, scope_hash, entity_binding_hash,
            created_at, committed_at, record_digest
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(
          payload.stableOutputId,
          payload.logicalId,
          committedVersion,
          priorVersion,
          exactRequest.baselineRecordDigest,
          exactRequest.aggregationRunId,
          exactRequest.runTokenHash,
          exactRequest.stagedTokenHash,
          exactRequest.commitOperationId,
          requestHash,
          JSON.stringify(payload),
          hashes.contentHash,
          hashes.metadataHash,
          hashes.scopeHash,
          hashes.entityBindingHash,
          payload.createdAt,
          committedAt,
          recordDigest,
        );
        const revisionId = Number(inserted.lastInsertRowid);
        if (!Number.isSafeInteger(revisionId) || revisionId < 1) {
          throw new Error("SQLite did not assign a valid durable revision");
        }
        this.faultInjector?.("after_commit_insert");

        if (priorVersion === null) {
          this.db.prepare(`
            INSERT INTO shadow_profile_reference_heads (
              stable_output_id, logical_id, committed_version, record_digest, revision_id
            ) VALUES (?, ?, ?, ?, ?)
          `).run(payload.stableOutputId, payload.logicalId, committedVersion, recordDigest, revisionId);
        } else {
          const updated = this.db.prepare(`
            UPDATE shadow_profile_reference_heads
            SET committed_version = ?, record_digest = ?, revision_id = ?
            WHERE stable_output_id = ? AND logical_id = ?
              AND committed_version = ? AND record_digest = ?
          `).run(
            committedVersion,
            recordDigest,
            revisionId,
            payload.stableOutputId,
            payload.logicalId,
            priorVersion,
            exactRequest.baselineRecordDigest,
          );
          if (updated.changes !== 1) throw new Error("CAS head update lost its transaction invariant");
        }
        this.faultInjector?.("after_head_update");

        const result = freezeResult({
          ...base(),
          status: "committed" as const,
          priorVersion,
          committedVersion,
          storageRevision: storageRevision(revisionId),
          committedAt,
          recordDigest,
        });
        this.persistOperationIfAddressable(exactRequest, requestHash, result);
        this.faultInjector?.("before_commit");
        return result;
      });
    } catch {
      return freezeResult({
        ...base(),
        status: "unresolved",
        reason: "SQLITE_TRANSACTION_FAILED",
      });
    }
  }

  readCommittedProfile(locator: SqliteReferenceReadLocator): SqliteReferenceReadbackResult {
    try {
      this.assertOpen();
      return this.immediateTransaction(() => {
        const revisionId = parseStorageRevision(locator.storageRevision);
        if (revisionId === null) {
          return { status: "not_found", evidenceClass: SQLITE_PROFILE_REFERENCE_RESULT } as const;
        }
        const row = this.db.prepare(`
          SELECT * FROM shadow_profile_reference_commits
          WHERE revision_id = ? AND stable_output_id = ? AND committed_version = ?
            AND commit_operation_id = ?
        `).get(
          revisionId,
          locator.stableOutputId,
          locator.committedVersion,
          locator.commitOperationId,
        ) as StoredCommit | undefined;
        if (!row) return { status: "not_found", evidenceClass: SQLITE_PROFILE_REFERENCE_RESULT } as const;

        const readOperationId = `sqlite-ref-read:${this.idFactory()}`;
        const readbackAt = this.nowIso();
        const verifiedFieldSetHash = l2CommitReadbackVerifiedFieldSetHash();
        this.db.prepare(`
          INSERT INTO shadow_profile_reference_reads (
            read_operation_id, revision_id, readback_at, verified_field_set_hash
          ) VALUES (?, ?, ?, ?)
        `).run(readOperationId, revisionId, readbackAt, verifiedFieldSetHash);
        return {
          status: "found",
          snapshot: freezeSnapshot(rowToSnapshot(
            row,
            this.backendBindingHash,
            readOperationId,
            readbackAt,
            verifiedFieldSetHash,
          )),
        } as const;
      });
    } catch {
      return {
        status: "unavailable",
        evidenceClass: SQLITE_PROFILE_REFERENCE_RESULT,
        reason: "SQLITE_READ_FAILED",
      };
    }
  }

  createReadbackAuthority(): L2CommitReadbackAuthority {
    return Object.freeze({
      authorityId: AUTHORITY_ID,
      authorityVersion: AUTHORITY_VERSION,
      authorityBindingHash: this.backendBindingHash,
      verifyCommittedSnapshot: (receipt: StrongL2CommitReadbackReceipt): boolean => {
        try {
          this.assertOpen();
          if (receipt.readerAuthorityId !== AUTHORITY_ID
            || receipt.readerAuthorityVersion !== AUTHORITY_VERSION
            || receipt.backendBindingHash !== this.backendBindingHash
            || receipt.verifiedFieldSetHash !== l2CommitReadbackVerifiedFieldSetHash()) return false;
          const revisionId = parseStorageRevision(receipt.storageRevision);
          if (revisionId === null) return false;
          const row = this.db.prepare(`
            SELECT c.*, r.read_operation_id, r.readback_at, r.verified_field_set_hash
            FROM shadow_profile_reference_commits c
            JOIN shadow_profile_reference_reads r ON r.revision_id = c.revision_id
            WHERE c.revision_id = ? AND r.read_operation_id = ?
          `).get(revisionId, receipt.readOperationId) as (StoredCommit & StoredRead) | undefined;
          if (!row) return false;
          const expected = rowToSnapshot(
            row,
            this.backendBindingHash,
            row.read_operation_id,
            row.readback_at,
            row.verified_field_set_hash,
          );
          return receiptMatchesSnapshot(receipt, expected);
        } catch {
          return false;
        }
      },
    });
  }

  /** Test-only accounting; never presented as production telemetry. */
  diagnosticCounts(): { heads: number; commits: number; operations: number; reads: number } {
    this.assertOpen();
    const count = (table: string): number => {
      const row = this.db.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get() as { count: number };
      return Number(row.count);
    };
    return {
      heads: count("shadow_profile_reference_heads"),
      commits: count("shadow_profile_reference_commits"),
      operations: count("shadow_profile_reference_operations"),
      reads: count("shadow_profile_reference_reads"),
    };
  }

  private createSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS shadow_profile_reference_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      ) STRICT;

      CREATE TABLE IF NOT EXISTS shadow_profile_reference_commits (
        revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stable_output_id TEXT NOT NULL,
        logical_id TEXT NOT NULL,
        committed_version INTEGER NOT NULL CHECK (committed_version >= 1),
        prior_version INTEGER CHECK (prior_version IS NULL OR prior_version >= 1),
        baseline_record_digest TEXT,
        aggregation_run_id TEXT NOT NULL,
        run_token_hash TEXT NOT NULL,
        staged_token_hash TEXT NOT NULL,
        commit_operation_id TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        metadata_hash TEXT NOT NULL,
        scope_hash TEXT NOT NULL,
        entity_binding_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        committed_at TEXT NOT NULL,
        record_digest TEXT NOT NULL,
        UNIQUE (stable_output_id, committed_version)
      ) STRICT;

      CREATE TABLE IF NOT EXISTS shadow_profile_reference_heads (
        stable_output_id TEXT PRIMARY KEY,
        logical_id TEXT NOT NULL,
        committed_version INTEGER NOT NULL CHECK (committed_version >= 1),
        record_digest TEXT NOT NULL,
        revision_id INTEGER NOT NULL UNIQUE,
        FOREIGN KEY (revision_id) REFERENCES shadow_profile_reference_commits(revision_id)
      ) STRICT;

      CREATE TABLE IF NOT EXISTS shadow_profile_reference_operations (
        commit_operation_id TEXT PRIMARY KEY,
        request_hash TEXT NOT NULL,
        stable_output_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('committed', 'conflict', 'rejected')),
        result_json TEXT NOT NULL
      ) STRICT;

      CREATE TABLE IF NOT EXISTS shadow_profile_reference_reads (
        read_operation_id TEXT PRIMARY KEY,
        revision_id INTEGER NOT NULL,
        readback_at TEXT NOT NULL,
        verified_field_set_hash TEXT NOT NULL,
        FOREIGN KEY (revision_id) REFERENCES shadow_profile_reference_commits(revision_id)
      ) STRICT;

      CREATE TRIGGER IF NOT EXISTS shadow_profile_reference_commits_no_update
      BEFORE UPDATE ON shadow_profile_reference_commits
      BEGIN SELECT RAISE(ABORT, 'profile commits are immutable'); END;

      CREATE TRIGGER IF NOT EXISTS shadow_profile_reference_commits_no_delete
      BEFORE DELETE ON shadow_profile_reference_commits
      BEGIN SELECT RAISE(ABORT, 'profile commits are immutable'); END;

      CREATE TRIGGER IF NOT EXISTS shadow_profile_reference_operations_no_update
      BEFORE UPDATE ON shadow_profile_reference_operations
      BEGIN SELECT RAISE(ABORT, 'profile operations are immutable'); END;

      CREATE TRIGGER IF NOT EXISTS shadow_profile_reference_operations_no_delete
      BEFORE DELETE ON shadow_profile_reference_operations
      BEGIN SELECT RAISE(ABORT, 'profile operations are immutable'); END;

      CREATE TRIGGER IF NOT EXISTS shadow_profile_reference_reads_no_update
      BEFORE UPDATE ON shadow_profile_reference_reads
      BEGIN SELECT RAISE(ABORT, 'profile reads are immutable'); END;

      CREATE TRIGGER IF NOT EXISTS shadow_profile_reference_reads_no_delete
      BEFORE DELETE ON shadow_profile_reference_reads
      BEGIN SELECT RAISE(ABORT, 'profile reads are immutable'); END;
    `);
  }

  private ensureInstanceId(): string {
    this.db.prepare(`
      INSERT OR IGNORE INTO shadow_profile_reference_meta (key, value)
      VALUES ('instance_id', ?)
    `).run(randomUUID());
    const row = this.db.prepare(`
      SELECT value FROM shadow_profile_reference_meta WHERE key = 'instance_id'
    `).get() as { value: string } | undefined;
    if (!row?.value) throw new Error("SQLite reference instance ID is unavailable");
    return row.value;
  }

  private getStoredHead(stableOutputId: string): StoredHead | undefined {
    return this.db.prepare(`
      SELECT stable_output_id, logical_id, committed_version, record_digest, revision_id
      FROM shadow_profile_reference_heads WHERE stable_output_id = ?
    `).get(stableOutputId) as StoredHead | undefined;
  }

  private persistOperationIfAddressable(
    request: SqliteReferenceExactL2ProfileCommitRequest,
    requestHash: string,
    result: Exclude<SqliteReferenceProfileCommitResult, SqliteReferenceUnresolvedResult>,
  ): void {
    const operationId = nonEmptyString(request?.commitOperationId);
    const stableOutputId = nonEmptyString(request?.payload?.stableOutputId);
    if (!operationId || !stableOutputId) return;
    this.db.prepare(`
      INSERT INTO shadow_profile_reference_operations (
        commit_operation_id, request_hash, stable_output_id, status, result_json
      ) VALUES (?, ?, ?, ?, ?)
    `).run(operationId, requestHash, stableOutputId, result.status, JSON.stringify(result));
  }

  private immediateTransaction<T>(body: () => T): T {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = body();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      try {
        this.db.exec("ROLLBACK");
      } catch {
        // Preserve the original error; fail closed at the public boundary.
      }
      throw error;
    }
  }

  private nowIso(): string {
    const value = this.now();
    if (!(value instanceof Date) || !Number.isFinite(value.getTime())) throw new Error("invalid reference clock");
    return value.toISOString();
  }

  private assertOpen(): void {
    if (this.closed) throw new Error("SQLite reference is closed");
  }
}

function validateRequest(
  request: SqliteReferenceExactL2ProfileCommitRequest,
): SqliteReferenceRejectedResult["reason"] | null {
  if (!request || typeof request !== "object"
    || request.schemaVersion !== REQUEST_SCHEMA_VERSION
    || !nonEmptyString(request.aggregationRunId)
    || !sha256(request.runTokenHash)
    || !sha256(request.stagedTokenHash)
    || !nonEmptyString(request.commitOperationId)
    || !request.payload
    || typeof request.payload !== "object"
    || !nonEmptyString(request.payload.stableOutputId)
    || !nonEmptyString(request.payload.logicalId)
    || typeof request.payload.content !== "string"
    || !request.payload.content.trim()
    || !validIso(request.payload.createdAt)
    || !validJson(request.payload.metadata)
    || !validScope(request.payload.scope)
    || !validBindings(request.payload.entityBindings)) return "INVALID_REQUEST";
  if (request.expectedPriorVersion === 0) return "LEGACY_VERSION_ZERO_UNSUPPORTED";
  if (request.expectedPriorVersion !== null
    && (!Number.isSafeInteger(request.expectedPriorVersion) || request.expectedPriorVersion < 1)) {
    return "INVALID_REQUEST";
  }
  if (request.expectedPriorVersion === null && request.baselineRecordDigest !== null) {
    return "CREATE_BASELINE_DIGEST_PRESENT";
  }
  if (request.expectedPriorVersion !== null && !sha256(request.baselineRecordDigest)) {
    return "UPDATE_BASELINE_DIGEST_MISSING";
  }
  return null;
}

function payloadHashes(payload: SqliteReferenceL2ProfilePayload) {
  return {
    contentHash: canonicalHash(payload.content),
    metadataHash: canonicalHash(payload.metadata),
    scopeHash: canonicalHash(payload.scope),
    entityBindingHash: canonicalHash(payload.entityBindings),
  };
}

function l2CaptureRecordDigest(
  payload: SqliteReferenceL2ProfilePayload,
  committedVersion: number,
  priorVersion: number | null,
  committedAt: string,
): string {
  return createVersionedMemoryRecord({
    context: {
      captureId: "exp-015-sqlite-reference-record-digest",
      capturedAt: committedAt,
      origin: "production_capture",
      feedbackDepth: 0,
      taskRunId: null,
    },
    layer: "L2",
    recordId: payload.stableOutputId,
    logicalId: payload.logicalId,
    version: committedVersion,
    content: payload.content,
    metadata: payload.metadata,
    scope: payload.scope,
    entityBindings: payload.entityBindings,
    predecessors: priorVersion === null ? [] : [{
      relation: "supersedes",
      record: { layer: "L2", id: payload.stableOutputId, version: priorVersion },
    }],
    createdAt: payload.createdAt,
    observedAt: committedAt,
    capturePoint: "l2_profile_commit_receipt",
    persistenceReceiptHash: canonicalHash("exp-015-sqlite-reference-record-digest"),
  }).payload.recordDigest;
}

function rowToSnapshot(
  row: StoredCommit,
  backendBindingHash: string,
  readOperationId: string,
  readbackAt: string,
  verifiedFieldSetHash: string,
): SqliteReferenceCommittedSnapshot {
  const payload = JSON.parse(row.payload_json) as SqliteReferenceL2ProfilePayload;
  return {
    schemaVersion: SNAPSHOT_SCHEMA_VERSION,
    evidenceClass: SQLITE_PROFILE_REFERENCE_RESULT,
    claimBoundary: SQLITE_PROFILE_REFERENCE_CLAIM_BOUNDARY,
    backendBindingHash,
    aggregationRunId: row.aggregation_run_id,
    runTokenHash: row.run_token_hash,
    stagedTokenHash: row.staged_token_hash,
    stableOutputId: row.stable_output_id,
    logicalId: row.logical_id,
    committedVersion: Number(row.committed_version),
    priorVersion: row.prior_version === null ? null : Number(row.prior_version),
    baselineRecordDigest: row.baseline_record_digest,
    contentHash: row.content_hash,
    metadataHash: row.metadata_hash,
    scopeHash: row.scope_hash,
    entityBindingHash: row.entity_binding_hash,
    payload: clone(payload),
    createdAt: row.created_at,
    committedAt: row.committed_at,
    commitOperationId: row.commit_operation_id,
    storageRevision: storageRevision(Number(row.revision_id)),
    recordDigest: row.record_digest,
    readbackAt,
    readOperationId,
    verifiedFieldSetHash,
  };
}

function receiptMatchesSnapshot(
  receipt: StrongL2CommitReadbackReceipt,
  snapshot: SqliteReferenceCommittedSnapshot,
): boolean {
  return receipt.aggregationRunId === snapshot.aggregationRunId
    && receipt.runTokenHash === snapshot.runTokenHash
    && receipt.stagedTokenHash === snapshot.stagedTokenHash
    && receipt.stableOutputId === snapshot.stableOutputId
    && receipt.logicalId === snapshot.logicalId
    && receipt.committedVersion === snapshot.committedVersion
    && receipt.contentHash === snapshot.contentHash
    && receipt.metadataHash === snapshot.metadataHash
    && receipt.scopeHash === snapshot.scopeHash
    && receipt.entityBindingHash === snapshot.entityBindingHash
    && receipt.priorVersion === snapshot.priorVersion
    && receipt.baselineRecordDigest === snapshot.baselineRecordDigest
    && receipt.createdAt === snapshot.createdAt
    && receipt.committedAt === snapshot.committedAt
    && receipt.readbackAt === snapshot.readbackAt
    && receipt.commitOperationId === snapshot.commitOperationId
    && receipt.storageRevision === snapshot.storageRevision
    && receipt.backendBindingHash === snapshot.backendBindingHash
    && receipt.readOperationId === snapshot.readOperationId
    && receipt.verifiedFieldSetHash === snapshot.verifiedFieldSetHash;
}

function storageRevision(revisionId: number): string {
  return `sqlite-profile-reference-revision:${revisionId}`;
}

function parseStorageRevision(value: string): number | null {
  const match = /^sqlite-profile-reference-revision:([1-9]\d*)$/.exec(value);
  if (!match) return null;
  const parsed = Number(match[1]);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function sha256(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/i.test(value);
}

function validIso(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0 && Number.isFinite(Date.parse(value));
}

function validScope(value: unknown): value is MemoryCaptureScope {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const row = value as Record<string, unknown>;
  const keys = ["agentId", "projectId", "sceneName", "sessionId", "sessionKey", "taskId", "teamId", "userId"];
  if (Object.keys(row).sort().join("\0") !== [...keys].sort().join("\0")) return false;
  return keys.every((key) => row[key] === null || typeof row[key] === "string");
}

function validBindings(value: unknown): value is Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  return Object.entries(value).every(([key, item]) => key.trim() && typeof item === "string" && item.trim());
}

function validJson(value: unknown): value is CaptureJsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(validJson);
  if (!value || typeof value !== "object") return false;
  const prototype = Object.getPrototypeOf(value);
  return (prototype === Object.prototype || prototype === null) && Object.values(value).every(validJson);
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function deepFreeze<T>(value: T, seen = new Set<object>()): T {
  if (!value || typeof value !== "object" || seen.has(value as object)) return value;
  seen.add(value as object);
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function freezeResult<T extends SqliteReferenceProfileCommitResult>(value: T): T {
  return deepFreeze(value);
}

function freezeSnapshot(value: SqliteReferenceCommittedSnapshot): SqliteReferenceCommittedSnapshot {
  return deepFreeze(value);
}

async function waitForWorkerBarrier(state: Int32Array, participants: number, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Atomics.load(state, 0) < participants) {
    if (Date.now() >= deadline) throw new Error("timed out waiting for SQLite reference commit workers");
    await new Promise<void>((resolve) => setTimeout(resolve, 5));
  }
}

function isSqliteReferenceWorkerData(value: unknown): value is SqliteReferenceWorkerData {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<SqliteReferenceWorkerData>;
  return row.kind === "tdai-exp015-sqlite-reference-commit-worker.v1"
    && typeof row.dbPath === "string"
    && row.barrier instanceof SharedArrayBuffer
    && Boolean(row.request);
}

if (!isMainThread && isSqliteReferenceWorkerData(workerData)) {
  let workerStore: SqliteProfileCommitReference | null = null;
  try {
    workerStore = new SqliteProfileCommitReference(workerData.dbPath);
    const state = new Int32Array(workerData.barrier);
    Atomics.add(state, 0, 1);
    Atomics.notify(state, 0);
    while (Atomics.load(state, 1) === 0) Atomics.wait(state, 1, 0);
    const result = workerStore.commitProfileExact(workerData.request);
    parentPort?.postMessage({ ok: true, result } satisfies SqliteReferenceWorkerMessage);
  } catch (error) {
    parentPort?.postMessage({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    } satisfies SqliteReferenceWorkerMessage);
  } finally {
    workerStore?.close();
  }
}
