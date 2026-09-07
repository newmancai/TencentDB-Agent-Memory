import {
  createVersionedMemoryRecord,
  type CaptureJsonValue,
  type MemoryCaptureScope,
} from "./capture-contracts.js";
import {
  createStrongL2CommitReadbackReceipt,
  l2CommitReadbackVerifiedFieldSetHash,
  type L2CommitReadbackAuthority,
  type StrongL2CommitReadbackReceipt,
} from "./l2-staged-shadow-adapter.js";
import { canonicalHash } from "./observation-plane.js";

/**
 * Evidence label carried by every outcome from this store.
 *
 * This implementation is deliberately an isolated, in-memory reference model.
 * Passing its conformance suite proves the protocol invariants only; it is not
 * evidence that TCVDB, SQLite, profile-sync, or a production deployment offers
 * atomic compare-and-swap or durable readback receipts.
 */
export const REFERENCE_PROFILE_COMMIT_EVIDENCE = Object.freeze({
  backendKind: "isolated_in_memory_reference" as const,
  evidenceLevel: "protocol_conformance_only" as const,
  durable: false as const,
  productionReady: false as const,
  optimizationReady: false as const,
});

export type ReferenceProfileCommitAction = "create" | "update";

export interface ReferenceExactProfileCommitRequest {
  schemaVersion: "tdai-reference-exact-profile-commit.v1";
  action: ReferenceProfileCommitAction;
  commitOperationId: string;
  aggregationRunId: string;
  runTokenHash: string;
  stagedTokenHash: string;
  stableOutputId: string;
  logicalId: string;
  content: string;
  metadata: CaptureJsonValue;
  scope: MemoryCaptureScope;
  entityBindings: Record<string, string>;
  expectedPriorVersion: number | null;
  baselineRecordDigest: string | null;
  createdAt: string;
}

export interface ReferenceExactProfileRow {
  stableOutputId: string;
  logicalId: string;
  version: number;
  content: string;
  metadata: CaptureJsonValue;
  scope: MemoryCaptureScope;
  entityBindings: Record<string, string>;
  createdAt: string;
  committedAt: string;
  commitOperationId: string;
  storageRevision: string;
  /** Immutable digest used by the next exact-baseline CAS, never inferred from version alone. */
  recordDigest: string;
}

export type ReferenceProfileConflictReason =
  | "CREATE_TARGET_EXISTS"
  | "UPDATE_TARGET_MISSING"
  | "CAS_VERSION_MISMATCH"
  | "CAS_BASELINE_DIGEST_MISMATCH"
  | "STABLE_CHAIN_MISMATCH"
  | "OPERATION_ID_REUSE_MISMATCH";

export type ReferenceProfileUnresolvedReason =
  | "INVALID_REQUEST"
  | "LEGACY_VERSION_ZERO"
  | "FAULT_BEFORE_COMMIT"
  | "FAULT_AFTER_COMMIT_BEFORE_ACK"
  | "FAULT_AFTER_ACK_BEFORE_READBACK"
  | "FAULT_READBACK_MISMATCH"
  | "STALE_COMMIT_RECEIPT";

interface ReferenceOutcomeBase {
  evidence: typeof REFERENCE_PROFILE_COMMIT_EVIDENCE;
  optimizationReady: false;
}

export interface ReferenceProfileCommittedOutcome extends ReferenceOutcomeBase {
  status: "committed";
  reason: null;
  exactReadbackAvailable: true;
  row: ReferenceExactProfileRow;
  receipt: StrongL2CommitReadbackReceipt;
}

export interface ReferenceProfileConflictOutcome extends ReferenceOutcomeBase {
  status: "conflict";
  reason: ReferenceProfileConflictReason;
  exactReadbackAvailable: false;
  observedVersion: number | null;
}

export interface ReferenceProfileUnresolvedOutcome extends ReferenceOutcomeBase {
  status: "unresolved";
  reason: ReferenceProfileUnresolvedReason;
  exactReadbackAvailable: false;
  mutationState: "none" | "may_have_committed";
}

export type ReferenceProfileCommitOutcome =
  | ReferenceProfileCommittedOutcome
  | ReferenceProfileConflictOutcome
  | ReferenceProfileUnresolvedOutcome;

export type ReferenceProfileCommitFaultPoint =
  | "before_commit"
  | "after_commit_before_ack"
  | "after_ack_before_readback"
  | "readback_mismatch";

export interface ReferenceExactProfileCommitStoreOptions {
  instanceId?: string;
  authorityId?: string;
  authorityVersion?: string;
  now?: () => string;
}

interface CommittedOperation {
  requestHash: string;
  outcome: ReferenceProfileCommittedOutcome;
}

interface RejectedOperation {
  requestHash: string;
  outcome: ReferenceProfileConflictOutcome;
}

type OperationEntry = CommittedOperation | RejectedOperation;

interface RevisionEntry {
  stableOutputId: string;
  rowDigest: string;
  receiptHash: string;
  commitOperationId: string;
}

/** Handle returned by the deterministic test-only CAS rendezvous. */
export interface ReferenceCasBarrier {
  /** Resolves once every configured participant is blocked immediately before CAS. */
  allArrived: Promise<void>;
}

interface InternalCasBarrier {
  participants: number;
  arrived: number;
  release: Promise<void>;
  releaseAll: () => void;
  allArrived: Promise<void>;
  markAllArrived: () => void;
}

/**
 * Isolated executable specification for the exact profile commit protocol.
 *
 * The synchronous section after `awaitCasBarrier()` is the reference atomic CAS
 * point. The reference authority checks private operation and revision ledgers
 * plus the currently committed row; accepting a publicly recomputed receipt
 * hash is intentionally insufficient.
 */
export class ReferenceExactProfileCommitStore {
  readonly backendBindingHash: string;
  readonly authority: L2CommitReadbackAuthority;

  private readonly now: () => string;
  private readonly rows = new Map<string, ReferenceExactProfileRow>();
  private readonly operations = new Map<string, OperationEntry>();
  private readonly revisions = new Map<string, RevisionEntry>();
  private revisionCounter = 0;
  private readCounter = 0;
  private faultOnce: ReferenceProfileCommitFaultPoint | null = null;
  private casBarrier: InternalCasBarrier | null = null;

  constructor(options: ReferenceExactProfileCommitStoreOptions = {}) {
    const instanceId = options.instanceId ?? "reference-instance";
    const authorityId = options.authorityId ?? "reference-profile-readback";
    const authorityVersion = options.authorityVersion ?? "v1";
    this.now = options.now ?? (() => new Date().toISOString());
    this.backendBindingHash = canonicalHash({
      backendKind: REFERENCE_PROFILE_COMMIT_EVIDENCE.backendKind,
      instanceId,
      schemaVersion: "tdai-reference-exact-profile-store.v1",
    });
    this.authority = Object.freeze({
      authorityId,
      authorityVersion,
      authorityBindingHash: this.backendBindingHash,
      verifyCommittedSnapshot: async (receipt: StrongL2CommitReadbackReceipt) => (
        this.verifyAgainstPrivateLedgers(receipt)
      ),
    });
  }

  /** Seed an isolated baseline. Version zero is allowed only to exercise legacy rejection. */
  seedForConformance(row: ReferenceExactProfileRow): void {
    assertReferenceRow(row, true);
    if (this.rows.has(row.stableOutputId)) throw new Error(`duplicate seed ${row.stableOutputId}`);
    this.rows.set(row.stableOutputId, cloneFreeze(row));
  }

  readRowForConformance(stableOutputId: string): ReferenceExactProfileRow | null {
    const row = this.rows.get(stableOutputId);
    return row ? cloneFreeze(row) : null;
  }

  /** Inject one deterministic failure into the next new operation reaching its point. */
  injectFaultOnce(point: ReferenceProfileCommitFaultPoint): void {
    if (this.faultOnce !== null) throw new Error("a reference fault is already armed");
    this.faultOnce = point;
  }

  /**
   * Force the next N valid operations to rendezvous immediately before the live
   * row is checked. This makes single-winner concurrency tests deterministic.
   */
  holdNextCasAttempts(participants: number): ReferenceCasBarrier {
    if (!Number.isSafeInteger(participants) || participants < 2) {
      throw new Error("CAS barrier participants must be an integer >= 2");
    }
    if (this.casBarrier) throw new Error("a CAS barrier is already active");
    let releaseAll!: () => void;
    let markAllArrived!: () => void;
    const release = new Promise<void>((resolve) => { releaseAll = resolve; });
    const allArrived = new Promise<void>((resolve) => { markAllArrived = resolve; });
    this.casBarrier = { participants, arrived: 0, release, releaseAll, allArrived, markAllArrived };
    return { allArrived };
  }

  async commitAndReadback(request: ReferenceExactProfileCommitRequest): Promise<ReferenceProfileCommitOutcome> {
    const requestError = validateRequest(request);
    if (requestError) return this.unresolved("INVALID_REQUEST", "none");
    const requestHash = canonicalHash(request);

    const priorOperation = this.operations.get(request.commitOperationId);
    if (priorOperation) {
      if (priorOperation.requestHash !== requestHash) {
        return this.conflict("OPERATION_ID_REUSE_MISMATCH", this.rows.get(request.stableOutputId)?.version ?? null);
      }
      if (priorOperation.outcome.status === "committed") {
        if (!this.verifyAgainstPrivateLedgers(priorOperation.outcome.receipt)) {
          return this.unresolved("STALE_COMMIT_RECEIPT", "may_have_committed");
        }
      }
      return cloneFreeze(priorOperation.outcome);
    }

    await this.awaitCasBarrier();

    if (this.consumeFault("before_commit")) {
      return this.unresolved("FAULT_BEFORE_COMMIT", "none");
    }

    // This section intentionally has no await: it is the reference atomic CAS.
    const current = this.rows.get(request.stableOutputId);
    if (current?.version === 0) {
      return this.unresolved("LEGACY_VERSION_ZERO", "none");
    }
    if (request.action === "create") {
      if (current) {
        return this.rememberConflict(request, requestHash, "CREATE_TARGET_EXISTS", current.version);
      }
    } else {
      if (!current) {
        return this.rememberConflict(request, requestHash, "UPDATE_TARGET_MISSING", null);
      }
      if (current.version !== request.expectedPriorVersion) {
        return this.rememberConflict(request, requestHash, "CAS_VERSION_MISMATCH", current.version);
      }
      if (current.recordDigest !== request.baselineRecordDigest) {
        return this.rememberConflict(request, requestHash, "CAS_BASELINE_DIGEST_MISMATCH", current.version);
      }
      if (current.logicalId !== request.logicalId
        || current.createdAt !== request.createdAt
        || canonicalHash(current.scope) !== canonicalHash(request.scope)
        || canonicalHash(current.entityBindings) !== canonicalHash(request.entityBindings)) {
        return this.rememberConflict(request, requestHash, "STABLE_CHAIN_MISMATCH", current.version);
      }
    }

    const priorVersion = current?.version ?? null;
    const committedVersion = current ? current.version + 1 : 1;
    const committedAt = this.checkedNow("commit");
    if (Date.parse(committedAt) < Date.parse(request.createdAt)) {
      return this.unresolved("INVALID_REQUEST", "none");
    }
    const storageRevision = `reference-revision:${++this.revisionCounter}`;
    const readOperationId = `reference-read:${++this.readCounter}`;
    const rowBody = {
      stableOutputId: request.stableOutputId,
      logicalId: request.logicalId,
      version: committedVersion,
      content: request.content,
      metadata: structuredClone(request.metadata),
      scope: structuredClone(request.scope),
      entityBindings: sortedBindings(request.entityBindings),
      createdAt: request.createdAt,
      committedAt,
      commitOperationId: request.commitOperationId,
      storageRevision,
    };
    const row = cloneFreeze<ReferenceExactProfileRow>({
      ...rowBody,
      recordDigest: l2CaptureRecordDigest({
        stableOutputId: rowBody.stableOutputId,
        logicalId: rowBody.logicalId,
        committedVersion: rowBody.version,
        priorVersion,
        content: rowBody.content,
        metadata: rowBody.metadata,
        scope: rowBody.scope,
        entityBindings: rowBody.entityBindings,
        createdAt: rowBody.createdAt,
        committedAt: rowBody.committedAt,
      }),
    });
    const readbackAt = this.checkedNow("readback");
    if (Date.parse(readbackAt) < Date.parse(committedAt)) {
      return this.unresolved("INVALID_REQUEST", "none");
    }
    const receipt = createStrongL2CommitReadbackReceipt({
      schemaVersion: "tdai-l2-commit-readback-receipt.v1",
      acknowledgementBasis: "committed_row_readback",
      aggregationRunId: request.aggregationRunId,
      runTokenHash: request.runTokenHash,
      stagedTokenHash: request.stagedTokenHash,
      stableOutputId: row.stableOutputId,
      logicalId: row.logicalId,
      committedVersion: row.version,
      contentHash: canonicalHash(row.content),
      metadataHash: canonicalHash(row.metadata),
      scopeHash: canonicalHash(row.scope),
      entityBindingHash: canonicalHash(row.entityBindings),
      priorVersion,
      baselineRecordDigest: request.baselineRecordDigest,
      createdAt: row.createdAt,
      committedAt: row.committedAt,
      readbackAt,
      commitOperationId: request.commitOperationId,
      storageRevision,
      backendBindingHash: this.backendBindingHash,
      readOperationId,
      verifiedFieldSetHash: l2CommitReadbackVerifiedFieldSetHash(),
      readerAuthorityId: this.authority.authorityId,
      readerAuthorityVersion: this.authority.authorityVersion,
    });
    const committed = cloneFreeze<ReferenceProfileCommittedOutcome>({
      ...this.base(),
      status: "committed",
      reason: null,
      exactReadbackAvailable: true,
      row,
      receipt,
    });

    // Model a storage transaction: row + operation ledger + revision ledger
    // become visible together before any acknowledgement/readback fault.
    this.rows.set(row.stableOutputId, row);
    this.operations.set(request.commitOperationId, { requestHash, outcome: committed });
    this.revisions.set(storageRevision, {
      stableOutputId: row.stableOutputId,
      rowDigest: canonicalHash(row),
      receiptHash: receipt.receiptHash,
      commitOperationId: request.commitOperationId,
    });

    if (this.consumeFault("after_commit_before_ack")) {
      return this.unresolved("FAULT_AFTER_COMMIT_BEFORE_ACK", "may_have_committed");
    }
    if (this.consumeFault("after_ack_before_readback")) {
      return this.unresolved("FAULT_AFTER_ACK_BEFORE_READBACK", "may_have_committed");
    }
    if (this.consumeFault("readback_mismatch")) {
      return this.unresolved("FAULT_READBACK_MISMATCH", "may_have_committed");
    }
    return cloneFreeze(committed);
  }

  private async awaitCasBarrier(): Promise<void> {
    const barrier = this.casBarrier;
    if (!barrier) return;
    barrier.arrived += 1;
    if (barrier.arrived === barrier.participants) {
      barrier.markAllArrived();
      this.casBarrier = null;
      barrier.releaseAll();
    }
    await barrier.release;
  }

  private consumeFault(point: ReferenceProfileCommitFaultPoint): boolean {
    if (this.faultOnce !== point) return false;
    this.faultOnce = null;
    return true;
  }

  private rememberConflict(
    request: ReferenceExactProfileCommitRequest,
    requestHash: string,
    reason: ReferenceProfileConflictReason,
    observedVersion: number | null,
  ): ReferenceProfileConflictOutcome {
    const outcome = this.conflict(reason, observedVersion);
    this.operations.set(request.commitOperationId, { requestHash, outcome });
    return outcome;
  }

  private verifyAgainstPrivateLedgers(receipt: StrongL2CommitReadbackReceipt): boolean {
    try {
      if (receipt.readerAuthorityId !== this.authority.authorityId
        || receipt.readerAuthorityVersion !== this.authority.authorityVersion
        || receipt.backendBindingHash !== this.backendBindingHash
        || receipt.verifiedFieldSetHash !== l2CommitReadbackVerifiedFieldSetHash()) return false;
      const operation = this.operations.get(receipt.commitOperationId);
      if (!operation || operation.outcome.status !== "committed") return false;
      if (canonicalHash(operation.outcome.receipt) !== canonicalHash(receipt)) return false;
      const revision = this.revisions.get(receipt.storageRevision);
      if (!revision
        || revision.stableOutputId !== receipt.stableOutputId
        || revision.receiptHash !== receipt.receiptHash
        || revision.commitOperationId !== receipt.commitOperationId) return false;
      const committed = operation.outcome.row;
      if (revision.rowDigest !== canonicalHash(committed)) return false;
      return committed.storageRevision === receipt.storageRevision
        && committed.logicalId === receipt.logicalId
        && committed.version === receipt.committedVersion
        && committed.createdAt === receipt.createdAt
        && committed.committedAt === receipt.committedAt
        && canonicalHash(committed.content) === receipt.contentHash
        && canonicalHash(committed.metadata) === receipt.metadataHash
        && canonicalHash(committed.scope) === receipt.scopeHash
        && canonicalHash(committed.entityBindings) === receipt.entityBindingHash;
    } catch {
      return false;
    }
  }

  private conflict(reason: ReferenceProfileConflictReason, observedVersion: number | null): ReferenceProfileConflictOutcome {
    return cloneFreeze({
      ...this.base(),
      status: "conflict" as const,
      reason,
      exactReadbackAvailable: false as const,
      observedVersion,
    });
  }

  private unresolved(
    reason: ReferenceProfileUnresolvedReason,
    mutationState: ReferenceProfileUnresolvedOutcome["mutationState"],
  ): ReferenceProfileUnresolvedOutcome {
    return cloneFreeze({
      ...this.base(),
      status: "unresolved" as const,
      reason,
      exactReadbackAvailable: false as const,
      mutationState,
    });
  }

  private base(): ReferenceOutcomeBase {
    return {
      evidence: REFERENCE_PROFILE_COMMIT_EVIDENCE,
      optimizationReady: false,
    };
  }

  private checkedNow(label: string): string {
    const value = this.now();
    if (typeof value !== "string" || !Number.isFinite(Date.parse(value))) {
      throw new Error(`reference ${label} clock returned an invalid timestamp`);
    }
    return value;
  }
}

function validateRequest(request: ReferenceExactProfileCommitRequest): string | null {
  try {
    if (!request || typeof request !== "object") return "request must be an object";
    if (request.schemaVersion !== "tdai-reference-exact-profile-commit.v1") return "invalid schema";
    if (request.action !== "create" && request.action !== "update") return "invalid action";
    for (const value of [
      request.commitOperationId,
      request.aggregationRunId,
      request.stableOutputId,
      request.logicalId,
    ]) {
      if (typeof value !== "string" || !value.trim()) return "missing identity";
    }
    for (const value of [request.runTokenHash, request.stagedTokenHash]) {
      if (typeof value !== "string" || !/^[a-f0-9]{64}$/i.test(value)) return "invalid token hash";
    }
    if (typeof request.content !== "string" || !request.content.trim()) return "missing content";
    assertJsonOnly(request.metadata);
    assertScope(request.scope);
    assertBindings(request.entityBindings);
    if (!Number.isFinite(Date.parse(request.createdAt))) return "invalid createdAt";
    if (request.action === "create") {
      if (request.expectedPriorVersion !== null || request.baselineRecordDigest !== null) {
        return "create must not supply a baseline";
      }
    } else {
      if (!Number.isSafeInteger(request.expectedPriorVersion) || (request.expectedPriorVersion ?? 0) < 1) {
        return "update requires a positive baseline version";
      }
      if (typeof request.baselineRecordDigest !== "string"
        || !/^[a-f0-9]{64}$/i.test(request.baselineRecordDigest)) {
        return "update requires an exact baseline digest";
      }
    }
    canonicalHash(request);
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
}

function assertReferenceRow(row: ReferenceExactProfileRow, allowVersionZero: boolean): void {
  if (!row || typeof row !== "object") throw new Error("reference seed row must be an object");
  if (!row.stableOutputId.trim() || !row.logicalId.trim()) throw new Error("reference seed row identity is required");
  if (!Number.isSafeInteger(row.version) || row.version < (allowVersionZero ? 0 : 1)) {
    throw new Error("reference seed row version is invalid");
  }
  if (!row.content.trim()) throw new Error("reference seed row content is required");
  assertJsonOnly(row.metadata);
  assertScope(row.scope);
  assertBindings(row.entityBindings);
  for (const value of [row.createdAt, row.committedAt]) {
    if (!Number.isFinite(Date.parse(value))) throw new Error("reference seed row timestamp is invalid");
  }
  if (!row.commitOperationId.trim() || !row.storageRevision.trim()) {
    throw new Error("reference seed row commit identity is required");
  }
  if (!/^[a-f0-9]{64}$/i.test(row.recordDigest)) {
    throw new Error("reference seed row recordDigest must be a SHA-256 digest");
  }
}

function assertJsonOnly(value: unknown, path = "metadata", seen = new Set<object>()): void {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error(`${path} contains a non-finite number`);
    return;
  }
  if (typeof value !== "object") throw new Error(`${path} is not JSON-only`);
  if (seen.has(value)) throw new Error(`${path} is cyclic`);
  seen.add(value);
  if (Array.isArray(value)) {
    value.forEach((child, index) => assertJsonOnly(child, `${path}[${index}]`, seen));
  } else {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) throw new Error(`${path} is not a plain object`);
    for (const [key, child] of Object.entries(value)) assertJsonOnly(child, `${path}.${key}`, seen);
  }
  seen.delete(value);
}

function assertScope(scope: MemoryCaptureScope): void {
  if (!scope || typeof scope !== "object" || !scope.teamId?.trim() || !scope.agentId?.trim()) {
    throw new Error("reference profile scope requires teamId and agentId");
  }
  assertJsonOnly(scope, "scope");
}

function assertBindings(bindings: Record<string, string>): void {
  if (!bindings || typeof bindings !== "object" || Array.isArray(bindings)) {
    throw new Error("entity bindings must be an object");
  }
  for (const [key, value] of Object.entries(bindings)) {
    if (!key.trim() || typeof value !== "string" || !value.trim()) {
      throw new Error("entity bindings require non-empty string keys and values");
    }
  }
}

function sortedBindings(bindings: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(bindings).sort(([left], [right]) => left.localeCompare(right)));
}

function l2CaptureRecordDigest(input: {
  stableOutputId: string;
  logicalId: string;
  committedVersion: number;
  priorVersion: number | null;
  content: string;
  metadata: CaptureJsonValue;
  scope: MemoryCaptureScope;
  entityBindings: Record<string, string>;
  createdAt: string;
  committedAt: string;
}): string {
  return createVersionedMemoryRecord({
    context: {
      captureId: "exp-015-reference-record-digest",
      capturedAt: input.committedAt,
      origin: "production_capture",
      feedbackDepth: 0,
      taskRunId: null,
    },
    layer: "L2",
    recordId: input.stableOutputId,
    logicalId: input.logicalId,
    version: input.committedVersion,
    content: input.content,
    metadata: input.metadata,
    scope: input.scope,
    entityBindings: input.entityBindings,
    predecessors: input.priorVersion === null ? [] : [{
      relation: "supersedes",
      record: { layer: "L2", id: input.stableOutputId, version: input.priorVersion },
    }],
    createdAt: input.createdAt,
    observedAt: input.committedAt,
    capturePoint: "l2_profile_commit_receipt",
    persistenceReceiptHash: canonicalHash("exp-015-reference-record-digest"),
  }).payload.recordDigest;
}

function cloneFreeze<T>(value: T): T {
  const clone = structuredClone(value);
  const freeze = (entry: unknown): void => {
    if (!entry || typeof entry !== "object" || Object.isFrozen(entry)) return;
    for (const child of Object.values(entry as Record<string, unknown>)) freeze(child);
    Object.freeze(entry);
  };
  freeze(clone);
  return clone;
}
