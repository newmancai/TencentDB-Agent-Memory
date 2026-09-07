import type { Logger } from "../types.js";
import {
  assertShadowCaptureEvent,
  createAggregationManifest,
  createVersionedMemoryRecord,
  freezeAggregationInputs,
  type AggregatorIdentity,
  type CaptureJsonValue,
  type ExactL1Ref,
  type FrozenAggregationInputSet,
  type MemoryCaptureScope,
  type ShadowCaptureContext,
  type SourceSpan,
  type VersionedMemoryRecord,
} from "./capture-contracts.js";
import type { ShadowCaptureSidecarStore } from "./capture-sidecar.js";
import { canonicalHash } from "./observation-plane.js";

export type L2StagedAuditStatus = "prepared" | "validated" | "captured" | "unresolved";
export type L2StagedAuditPhase = "begin" | "validate" | "commit";

export type L2StagedFailureReason =
  | "INVALID_BEGIN_INPUT"
  | "INVALID_L1_INPUT"
  | "INVALID_L2_BASELINE"
  | "DUPLICATE_RUN_ID"
  | "UNKNOWN_OR_TAMPERED_RUN_TOKEN"
  | "RUN_NOT_PREPARED"
  | "UNSUPPORTED_STAGED_ACTION"
  | "BASELINE_ACTION_MISMATCH"
  | "STAGED_OUTPUT_ID_MISMATCH"
  | "STAGED_LOGICAL_ID_MISMATCH"
  | "STAGED_SCOPE_MISMATCH"
  | "STAGED_ENTITY_BINDING_MISMATCH"
  | "MISSING_STAGED_CONTENT"
  | "INVALID_STAGED_PAYLOAD"
  | "MISSING_CLAIMS"
  | "DUPLICATE_CLAIM_ID"
  | "INVALID_CLAIM_SPAN"
  | "OVERLAPPING_CLAIM_SPANS"
  | "INCOMPLETE_CLAIM_COVERAGE"
  | "MISSING_CLAIM_SOURCE"
  | "DUPLICATE_CLAIM_SOURCE"
  | "SOURCE_OUTSIDE_FROZEN_SET"
  | "INPUT_OBSERVED_AFTER_FREEZE"
  | "MIXED_CAPTURE_ORIGIN"
  | "SCOPE_AUTHORITY_MISMATCH"
  | "PREPARED_AUDIT_APPEND_FAILED"
  | "VALIDATION_AUDIT_APPEND_FAILED"
  | "UNKNOWN_OR_TAMPERED_STAGED_TOKEN"
  | "RUN_NOT_VALIDATED"
  | "MISSING_READBACK_RECEIPT"
  | "MISSING_READBACK_AUTHORITY"
  | "READBACK_AUTHORITY_MISMATCH"
  | "READBACK_AUTHORITY_REJECTED"
  | "INVALID_READBACK_RECEIPT"
  | "READBACK_OUTPUT_ID_MISMATCH"
  | "READBACK_CAUSAL_BINDING_MISMATCH"
  | "READBACK_CONTENT_MISMATCH"
  | "READBACK_METADATA_MISMATCH"
  | "READBACK_SCOPE_MISMATCH"
  | "READBACK_ENTITY_BINDING_MISMATCH"
  | "READBACK_BASELINE_MISMATCH"
  | "NON_POSITIVE_COMMITTED_VERSION"
  | "NON_MONOTONIC_COMMITTED_VERSION"
  | "COMMIT_PRECEDES_FREEZE"
  | "CAPTURE_CONTRACT_REJECTED"
  | "SIDECAR_APPEND_FAILED"
  | "CAPTURED_AUDIT_APPEND_FAILED";

export interface L2StagedAggregationAudit {
  schemaVersion: "tdai-l2-staged-aggregation-audit.v1";
  auditId: string;
  auditHash: string;
  captureId: string;
  capturedAt: string;
  aggregationRunId: string | null;
  phase: L2StagedAuditPhase;
  status: L2StagedAuditStatus;
  runTokenHash: string | null;
  stagedTokenHash: string | null;
  inputSetHash: string | null;
  generationContractHash: string | null;
  receiptHash: string | null;
  output: { layer: "L2"; id: string; version: number } | null;
  eventIds: string[];
  blockers: L2StagedFailureReason[];
  /** This adapter alone cannot establish role-correct L0, runtime use, or outcome joins. */
  exactLocalizationCaptureReady: false;
  /** True only when this local L2 snapshot + derivation-manifest slice is complete. */
  exactL2DerivationCaptureReady: boolean;
  feedbackDepth: 0;
  memoryIngestionAllowed: false;
  mayWriteProductionMemory: false;
  mayEnqueueFeedback: false;
  feedbackReingestionEnabled: false;
  optimizationReady: false;
}

export interface L2StagedAggregationAuditStore {
  append(audit: L2StagedAggregationAudit): void | Promise<void>;
}

export class InMemoryL2StagedAggregationAuditStore implements L2StagedAggregationAuditStore {
  readonly audits: L2StagedAggregationAudit[] = [];

  append(audit: L2StagedAggregationAudit): void {
    this.audits.push(cloneFreeze(audit));
  }
}

export interface L2AggregationBeginInput {
  aggregationRunId: string;
  frozenAt: string;
  records: VersionedMemoryRecord[];
  aggregator: AggregatorIdentity;
  systemPromptHash: string;
  userPromptHash: string;
  toolSchemaHash: string;
  configHash: string;
  baseline?: VersionedMemoryRecord | null;
}

export interface L2AggregationRunToken {
  schemaVersion: "tdai-l2-aggregation-run-token.v1";
  aggregationRunId: string;
  preparedAt: string;
  inputSetHash: string;
  generationContractHash: string;
  generationInputHashes: {
    systemPromptHash: string;
    userPromptHash: string;
    toolSchemaHash: string;
    configHash: string;
  };
  scopeAuthorityHash: string;
  readbackAuthorityHash: string;
  baseline: null | {
    record: { layer: "L2"; id: string; version: number };
    logicalId: string;
    recordDigest: string;
    scopeHash: string;
  };
  feedbackDepth: 0;
  memoryIngestionAllowed: false;
  mayWriteProductionMemory: false;
  mayEnqueueFeedback: false;
  feedbackReingestionEnabled: false;
  optimizationReady: false;
  tokenHash: string;
}

export interface StagedL2ClaimInput {
  claimId: string;
  span: SourceSpan;
  sources: ExactL1Ref[];
}

export interface StagedL2OutputInput {
  /** Runtime validation deliberately accepts string so forbidden operations fail closed. */
  action: string;
  recordId: string;
  logicalId: string;
  content: string;
  metadata: CaptureJsonValue;
  scope: MemoryCaptureScope;
  entityBindings: Record<string, string>;
  createdAt: string;
  claims: StagedL2ClaimInput[];
}

export interface ValidatedL2StagedToken {
  schemaVersion: "tdai-l2-validated-stage-token.v1";
  aggregationRunId: string;
  runTokenHash: string;
  action: "create" | "update";
  outputId: string;
  logicalId: string;
  contentHash: string;
  metadataHash: string;
  scopeHash: string;
  entityBindingHash: string;
  stagedPayloadHash: string;
  baselineVersion: number | null;
  feedbackDepth: 0;
  memoryIngestionAllowed: false;
  mayWriteProductionMemory: false;
  mayEnqueueFeedback: false;
  feedbackReingestionEnabled: false;
  optimizationReady: false;
  tokenHash: string;
}

export interface StrongL2CommitReadbackReceipt {
  schemaVersion: "tdai-l2-commit-readback-receipt.v1";
  acknowledgementBasis: "committed_row_readback";
  aggregationRunId: string;
  runTokenHash: string;
  stagedTokenHash: string;
  stableOutputId: string;
  logicalId: string;
  committedVersion: number;
  contentHash: string;
  metadataHash: string;
  scopeHash: string;
  entityBindingHash: string;
  priorVersion: number | null;
  baselineRecordDigest: string | null;
  createdAt: string;
  committedAt: string;
  readbackAt: string;
  commitOperationId: string;
  storageRevision: string;
  backendBindingHash: string;
  readOperationId: string;
  verifiedFieldSetHash: string;
  readerAuthorityId: string;
  readerAuthorityVersion: string;
  readerSnapshotDigest: string;
  receiptHash: string;
}

export type StrongL2CommitReadbackReceiptInput = Omit<
  StrongL2CommitReadbackReceipt,
  "receiptHash" | "readerSnapshotDigest"
>;

export const L2_COMMIT_READBACK_VERIFIED_FIELDS = Object.freeze([
  "aggregationRunId",
  "baselineRecordDigest",
  "commitOperationId",
  "committedAt",
  "committedVersion",
  "contentHash",
  "createdAt",
  "entityBindingHash",
  "logicalId",
  "metadataHash",
  "priorVersion",
  "runTokenHash",
  "scopeHash",
  "stableOutputId",
  "stagedTokenHash",
  "storageRevision",
] as const);

export function l2CommitReadbackVerifiedFieldSetHash(): string {
  return canonicalHash(L2_COMMIT_READBACK_VERIFIED_FIELDS);
}

/**
 * Trusted integration boundary for a storage-native committed-row readback.
 * The receipt's public digest is integrity metadata, not authentication; an
 * enabled coordinator therefore also requires this independently configured
 * authority to confirm the committed snapshot.
 */
export interface L2CommitReadbackAuthority {
  authorityId: string;
  authorityVersion: string;
  /** Binds backend instance, collection/table, schema and relevant config. */
  authorityBindingHash: string;
  verifyCommittedSnapshot(
    receipt: StrongL2CommitReadbackReceipt,
  ): boolean | Promise<boolean>;
}

export function createStrongL2CommitReadbackReceipt(
  input: StrongL2CommitReadbackReceiptInput,
): StrongL2CommitReadbackReceipt {
  assertExactKeys(input, [
    "acknowledgementBasis",
    "aggregationRunId",
    "backendBindingHash",
    "baselineRecordDigest",
    "commitOperationId",
    "committedAt",
    "committedVersion",
    "contentHash",
    "entityBindingHash",
    "metadataHash",
    "logicalId",
    "priorVersion",
    "readOperationId",
    "readbackAt",
    "readerAuthorityId",
    "readerAuthorityVersion",
    "runTokenHash",
    "schemaVersion",
    "scopeHash",
    "stagedTokenHash",
    "stableOutputId",
    "storageRevision",
    "verifiedFieldSetHash",
    "createdAt",
  ], "readback receipt input");
  const body = {
    ...input,
    readerSnapshotDigest: canonicalHash(readbackSnapshotBody(input)),
  };
  assertReadbackReceiptBody(body);
  return cloneFreeze({ ...body, receiptHash: canonicalHash(body) });
}

export interface L2StagedShadowCoordinatorOptions {
  /** Default-off. Construction alone performs no capture or audit writes. */
  enabled?: boolean;
  context: ShadowCaptureContext;
  eventStore: ShadowCaptureSidecarStore;
  auditStore: L2StagedAggregationAuditStore;
  /** Required when enabled: the pre-generation runtime's authoritative L2 scope. */
  scopeAuthority?: { teamId: string; agentId: string };
  /** Required when enabled: independently verifies the post-commit readback. */
  readbackAuthority?: L2CommitReadbackAuthority;
  logger?: Logger;
}

interface NormalizedClaim {
  claimId: string;
  span: SourceSpan;
  sources: ExactL1Ref[];
}

interface NormalizedStage {
  action: "create" | "update";
  recordId: string;
  logicalId: string;
  content: string;
  metadata: CaptureJsonValue;
  scope: MemoryCaptureScope;
  entityBindings: Record<string, string>;
  createdAt: string;
  claims: NormalizedClaim[];
}

interface RunState {
  phase: "prepared" | "validated" | "captured" | "unresolved";
  runToken: L2AggregationRunToken;
  frozenInputs: FrozenAggregationInputSet;
  baseline: VersionedMemoryRecord | null;
  scopeAuthority: { teamId: string; agentId: string };
  stage: NormalizedStage | null;
  stagedToken: ValidatedL2StagedToken | null;
}

class L2StageError extends Error {
  constructor(readonly reason: L2StagedFailureReason, message: string) {
    super(message);
  }
}

/**
 * An isolated three-phase capture coordinator. It never receives a production
 * Memory writer: the only mutable dependency is the append-only shadow
 * sidecar. A caller must commit independently and then provide a canonical
 * readback receipt before this coordinator materializes any exact L2 record.
 */
export class L2StagedShadowAggregationCoordinator {
  private readonly enabled: boolean;
  private readonly context: ShadowCaptureContext;
  private readonly eventStore: ShadowCaptureSidecarStore;
  private readonly auditStore: L2StagedAggregationAuditStore;
  private readonly scopeAuthority: { teamId: string; agentId: string } | null;
  private readonly readbackAuthority: L2CommitReadbackAuthority | null;
  private readonly logger?: Logger;
  private readonly runs = new Map<string, RunState>();
  private queue: Promise<void> = Promise.resolve();

  constructor(options: L2StagedShadowCoordinatorOptions) {
    this.enabled = options.enabled ?? false;
    this.context = structuredClone(options.context);
    this.eventStore = options.eventStore;
    this.auditStore = options.auditStore;
    this.scopeAuthority = options.scopeAuthority ? structuredClone(options.scopeAuthority) : null;
    this.readbackAuthority = options.readbackAuthority ?? null;
    this.logger = options.logger;
  }

  beginRun(input: L2AggregationBeginInput): Promise<L2AggregationRunToken | null> {
    if (!this.enabled) return Promise.resolve(null);
    return this.enqueue(() => this.beginRunInternal(input));
  }

  validateStagedOutput(
    runToken: L2AggregationRunToken,
    output: StagedL2OutputInput,
  ): Promise<ValidatedL2StagedToken | null> {
    if (!this.enabled) return Promise.resolve(null);
    return this.enqueue(() => this.validateStagedOutputInternal(runToken, output));
  }

  finalizeAfterCommit(
    stagedToken: ValidatedL2StagedToken,
    receipt: StrongL2CommitReadbackReceipt | null,
  ): Promise<boolean> {
    if (!this.enabled) return Promise.resolve(false);
    return this.enqueue(() => this.finalizeAfterCommitInternal(stagedToken, receipt));
  }

  /** Wait for all already-dispatched shadow work; never waits for production. */
  async drain(): Promise<void> {
    await this.queue;
  }

  private enqueue<T>(work: () => Promise<T>): Promise<T> {
    const queued = this.queue.then(work, work);
    this.queue = queued.then(() => undefined, () => undefined);
    return queued;
  }

  private async beginRunInternal(input: L2AggregationBeginInput): Promise<L2AggregationRunToken | null> {
    if (!validCaptureContext(this.context)) {
      // An untrusted/self-generated context cannot author even an unresolved
      // audit row, because doing so would launder it into a depth-0 envelope.
      this.logger?.warn("[memory-tdai][shadow-l2-stage] Refused invalid or recursive capture context");
      return null;
    }
    let runId = nonEmptyOrNull(input?.aggregationRunId);
    try {
      if (!input || typeof input !== "object") {
        throw new L2StageError("INVALID_BEGIN_INPUT", "begin input must be an object");
      }
      requireNonEmpty(input.aggregationRunId, "aggregationRunId", "INVALID_BEGIN_INPUT");
      runId = input.aggregationRunId;
      requireIso(input.frozenAt, "frozenAt", "INVALID_BEGIN_INPUT");
      requireHash(input.systemPromptHash, "systemPromptHash", "INVALID_BEGIN_INPUT");
      requireHash(input.userPromptHash, "userPromptHash", "INVALID_BEGIN_INPUT");
      requireHash(input.toolSchemaHash, "toolSchemaHash", "INVALID_BEGIN_INPUT");
      requireHash(input.configHash, "configHash", "INVALID_BEGIN_INPUT");
      if (!this.scopeAuthority || !this.scopeAuthority.teamId.trim() || !this.scopeAuthority.agentId.trim()) {
        throw new L2StageError("INVALID_BEGIN_INPUT", "enabled capture requires an exact team/agent scope authority");
      }
      if (!this.readbackAuthority
        || !nonEmptyOrNull(this.readbackAuthority.authorityId)
        || !nonEmptyOrNull(this.readbackAuthority.authorityVersion)
        || !/^[a-f0-9]{64}$/i.test(this.readbackAuthority.authorityBindingHash)
        || typeof this.readbackAuthority.verifyCommittedSnapshot !== "function") {
        throw new L2StageError(
          "MISSING_READBACK_AUTHORITY",
          "enabled capture requires an independently configured commit-readback authority",
        );
      }
      if (this.runs.has(input.aggregationRunId)) {
        throw new L2StageError("DUPLICATE_RUN_ID", `duplicate aggregation run ${input.aggregationRunId}`);
      }

      let frozenInputs: FrozenAggregationInputSet;
      try {
        frozenInputs = freezeAggregationInputs({
          aggregationRunId: input.aggregationRunId,
          frozenAt: input.frozenAt,
          aggregator: input.aggregator,
          records: input.records,
        });
      } catch (error) {
        throw new L2StageError("INVALID_L1_INPUT", errorMessage(error));
      }
      for (const record of input.records) {
        if (record.origin !== this.context.origin) {
          throw new L2StageError("MIXED_CAPTURE_ORIGIN", "L1 input origin differs from coordinator origin");
        }
        if (Date.parse(record.capturedAt) > Date.parse(input.frozenAt)
          || Date.parse(record.payload.observedAt) > Date.parse(input.frozenAt)) {
          throw new L2StageError("INPUT_OBSERVED_AFTER_FREEZE", "L1 input was captured or observed after frozenAt");
        }
        assertAuthorityScope(record, this.scopeAuthority);
      }

      const baseline = input.baseline ?? null;
      if (baseline !== null) {
        try {
          assertShadowCaptureEvent(baseline);
          if (baseline.eventType !== "versioned_memory_record" || baseline.payload.record.layer !== "L2") {
            throw new Error("baseline must be an exact L2 record");
          }
          if (baseline.origin !== this.context.origin) {
            throw new L2StageError("MIXED_CAPTURE_ORIGIN", "L2 baseline origin differs from coordinator origin");
          }
          if (Date.parse(baseline.capturedAt) > Date.parse(input.frozenAt)
            || Date.parse(baseline.payload.observedAt) > Date.parse(input.frozenAt)) {
            throw new L2StageError("INPUT_OBSERVED_AFTER_FREEZE", "L2 baseline was captured or observed after frozenAt");
          }
          assertAuthorityScope(baseline, this.scopeAuthority);
        } catch (error) {
          if (error instanceof L2StageError) throw error;
          throw new L2StageError("INVALID_L2_BASELINE", errorMessage(error));
        }
      }

      const generationInputHashes = {
        systemPromptHash: input.systemPromptHash,
        userPromptHash: input.userPromptHash,
        toolSchemaHash: input.toolSchemaHash,
        configHash: input.configHash,
      };
      const generationContractHash = canonicalHash(generationInputHashes);
      const tokenBody = {
        schemaVersion: "tdai-l2-aggregation-run-token.v1" as const,
        aggregationRunId: input.aggregationRunId,
        preparedAt: input.frozenAt,
        inputSetHash: frozenInputs.inputSetHash,
        generationContractHash,
        generationInputHashes,
        scopeAuthorityHash: canonicalHash(this.scopeAuthority),
        readbackAuthorityHash: canonicalHash({
          authorityId: this.readbackAuthority.authorityId,
          authorityVersion: this.readbackAuthority.authorityVersion,
          authorityBindingHash: this.readbackAuthority.authorityBindingHash,
        }),
        baseline: baseline === null ? null : {
          record: {
            layer: "L2" as const,
            id: baseline.payload.record.id,
            version: baseline.payload.record.version,
          },
          logicalId: baseline.payload.logicalId,
          recordDigest: baseline.payload.recordDigest,
          scopeHash: baseline.payload.scopeHash,
        },
        ...tokenSafety(),
      };
      const runToken = cloneFreeze({ ...tokenBody, tokenHash: canonicalHash(tokenBody) });
      const preparedAudit = this.makeAudit({
        aggregationRunId: input.aggregationRunId,
        phase: "begin",
        status: "prepared",
        runTokenHash: runToken.tokenHash,
        stagedTokenHash: null,
        inputSetHash: frozenInputs.inputSetHash,
        generationContractHash,
        receiptHash: null,
        output: null,
        eventIds: [],
        blockers: [],
        exactL2DerivationCaptureReady: false,
      });
      if (!await this.appendAudit(preparedAudit)) {
        await this.appendUnresolved({
          aggregationRunId: input.aggregationRunId,
          phase: "begin",
          reason: "PREPARED_AUDIT_APPEND_FAILED",
        });
        return null;
      }
      this.runs.set(input.aggregationRunId, {
        phase: "prepared",
        runToken,
        frozenInputs,
        baseline: baseline ? cloneFreeze(baseline) : null,
        scopeAuthority: structuredClone(this.scopeAuthority),
        stage: null,
        stagedToken: null,
      });
      return runToken;
    } catch (error) {
      const reason = stageReason(error, "INVALID_BEGIN_INPUT");
      await this.appendUnresolved({
        aggregationRunId: runId,
        phase: "begin",
        state: runId ? this.runs.get(runId) : undefined,
        reason,
      });
      return null;
    }
  }

  private async validateStagedOutputInternal(
    runToken: L2AggregationRunToken,
    output: StagedL2OutputInput,
  ): Promise<ValidatedL2StagedToken | null> {
    const runId = nonEmptyOrNull(runToken?.aggregationRunId);
    let state: RunState | undefined;
    try {
      state = runId ? this.runs.get(runId) : undefined;
      if (!state || !validRunToken(runToken, state.runToken)) {
        throw new L2StageError("UNKNOWN_OR_TAMPERED_RUN_TOKEN", "run token is unknown or was modified");
      }
      if (state.phase !== "prepared") {
        throw new L2StageError("RUN_NOT_PREPARED", `run is ${state.phase}, not prepared`);
      }
      const stage = normalizeStage(output, state);
      const stagedPayloadHash = canonicalHash(stage);
      const tokenBody = {
        schemaVersion: "tdai-l2-validated-stage-token.v1" as const,
        aggregationRunId: runToken.aggregationRunId,
        runTokenHash: runToken.tokenHash,
        action: stage.action,
        outputId: stage.recordId,
        logicalId: stage.logicalId,
        contentHash: canonicalHash(stage.content),
        metadataHash: canonicalHash(stage.metadata),
        scopeHash: canonicalHash(stage.scope),
        entityBindingHash: canonicalHash(stage.entityBindings),
        stagedPayloadHash,
        baselineVersion: state.baseline?.payload.record.version ?? null,
        ...tokenSafety(),
      };
      const stagedToken = cloneFreeze({ ...tokenBody, tokenHash: canonicalHash(tokenBody) });
      const audit = this.makeAudit({
        aggregationRunId: runToken.aggregationRunId,
        phase: "validate",
        status: "validated",
        runTokenHash: runToken.tokenHash,
        stagedTokenHash: stagedToken.tokenHash,
        inputSetHash: state.frozenInputs.inputSetHash,
        generationContractHash: runToken.generationContractHash,
        receiptHash: null,
        output: null,
        eventIds: [],
        blockers: [],
        exactL2DerivationCaptureReady: false,
      });
      if (!await this.appendAudit(audit)) {
        state.phase = "unresolved";
        await this.appendUnresolved({
          aggregationRunId: runToken.aggregationRunId,
          phase: "validate",
          state,
          reason: "VALIDATION_AUDIT_APPEND_FAILED",
        });
        return null;
      }
      state.stage = cloneFreeze(stage);
      state.stagedToken = stagedToken;
      state.phase = "validated";
      return stagedToken;
    } catch (error) {
      if (state) state.phase = "unresolved";
      await this.appendUnresolved({
        aggregationRunId: runId,
        phase: "validate",
        state,
        reason: stageReason(error, "INVALID_STAGED_PAYLOAD"),
      });
      return null;
    }
  }

  private async finalizeAfterCommitInternal(
    stagedToken: ValidatedL2StagedToken,
    receipt: StrongL2CommitReadbackReceipt | null,
  ): Promise<boolean> {
    const runId = nonEmptyOrNull(stagedToken?.aggregationRunId);
    let state: RunState | undefined;
    try {
      state = runId ? this.runs.get(runId) : undefined;
      if (!state || !state.stagedToken || !validStagedToken(stagedToken, state.stagedToken)) {
        throw new L2StageError("UNKNOWN_OR_TAMPERED_STAGED_TOKEN", "staged token is unknown or was modified");
      }
      if (state.phase !== "validated" || !state.stage) {
        throw new L2StageError("RUN_NOT_VALIDATED", `run is ${state.phase}, not validated`);
      }
      if (receipt === null) {
        throw new L2StageError("MISSING_READBACK_RECEIPT", "commit readback receipt is required");
      }
      validateReadbackAgainstStage(receipt, state);
      await this.verifyReadbackAuthority(receipt);

      const outputRef = {
        layer: "L2" as const,
        id: receipt.stableOutputId,
        version: receipt.committedVersion,
      };
      let output: VersionedMemoryRecord;
      try {
        output = createVersionedMemoryRecord({
          context: this.context,
          layer: "L2",
          recordId: state.stage.recordId,
          logicalId: state.stage.logicalId,
          version: receipt.committedVersion,
          content: state.stage.content,
          metadata: state.stage.metadata,
          scope: state.stage.scope,
          entityBindings: state.stage.entityBindings,
          predecessors: state.baseline ? [{
            relation: "supersedes",
            record: {
              layer: "L2" as const,
              id: state.baseline.payload.record.id,
              version: state.baseline.payload.record.version,
            },
          }] : [],
          createdAt: state.stage.createdAt,
          observedAt: receipt.committedAt,
          capturePoint: this.context.origin === "benchmark_fixture"
            ? "benchmark_fixture"
            : "l2_profile_commit_receipt",
          persistenceReceiptHash: receipt.receiptHash,
        });
        const manifest = createAggregationManifest({
          context: this.context,
          manifestId: `manifest:l2:v1:${canonicalHash({
            aggregationRunId: state.runToken.aggregationRunId,
            output: outputRef,
          })}`,
          manifestVersion: 1,
          frozenInputs: state.frozenInputs,
          output,
          aggregationCompletedAt: receipt.committedAt,
          claims: state.stage.claims.map((claim) => ({
            claimId: claim.claimId,
            span: structuredClone(claim.span),
            sources: claim.sources.map((source) => ({
              edgeId: immutableEdgeId(state!.runToken.aggregationRunId, outputRef, claim.claimId, source),
              edgeVersion: 1,
              source: structuredClone(source),
            })),
          })),
        });
        if (!manifest.claimCoverage.complete) {
          throw new Error("manifest did not preserve complete staged claim coverage");
        }
        try {
          await this.eventStore.appendBatch([output, manifest]);
        } catch (error) {
          throw new L2StageError("SIDECAR_APPEND_FAILED", errorMessage(error));
        }
        state.phase = "captured";
        const capturedAuditWritten = await this.appendAudit(this.makeAudit({
          aggregationRunId: state.runToken.aggregationRunId,
          phase: "commit",
          status: "captured",
          runTokenHash: state.runToken.tokenHash,
          stagedTokenHash: stagedToken.tokenHash,
          inputSetHash: state.frozenInputs.inputSetHash,
          generationContractHash: state.runToken.generationContractHash,
          receiptHash: receipt.receiptHash,
          output: outputRef,
          eventIds: [output.eventId, manifest.eventId],
          blockers: [],
          exactL2DerivationCaptureReady: true,
        }));
        if (!capturedAuditWritten) {
          state.phase = "unresolved";
          await this.appendUnresolved({
            aggregationRunId: state.runToken.aggregationRunId,
            phase: "commit",
            state,
            reason: "CAPTURED_AUDIT_APPEND_FAILED",
            receiptHash: receipt.receiptHash,
          });
          return false;
        }
        return true;
      } catch (error) {
        if (error instanceof L2StageError) throw error;
        throw new L2StageError("CAPTURE_CONTRACT_REJECTED", errorMessage(error));
      }
    } catch (error) {
      if (state) state.phase = "unresolved";
      await this.appendUnresolved({
        aggregationRunId: runId,
        phase: "commit",
        state,
        reason: stageReason(error, "INVALID_READBACK_RECEIPT"),
        receiptHash: receipt?.receiptHash ?? null,
      });
      return false;
    }
  }

  private makeAudit(input: {
    aggregationRunId: string | null;
    phase: L2StagedAuditPhase;
    status: L2StagedAuditStatus;
    runTokenHash: string | null;
    stagedTokenHash: string | null;
    inputSetHash: string | null;
    generationContractHash: string | null;
    receiptHash: string | null;
    output: { layer: "L2"; id: string; version: number } | null;
    eventIds: string[];
    blockers: L2StagedFailureReason[];
    exactL2DerivationCaptureReady: boolean;
  }): L2StagedAggregationAudit {
    const body = {
      schemaVersion: "tdai-l2-staged-aggregation-audit.v1" as const,
      captureId: this.context.captureId,
      capturedAt: this.context.capturedAt,
      aggregationRunId: input.aggregationRunId,
      phase: input.phase,
      status: input.status,
      runTokenHash: input.runTokenHash,
      stagedTokenHash: input.stagedTokenHash,
      inputSetHash: input.inputSetHash,
      generationContractHash: input.generationContractHash,
      receiptHash: input.receiptHash,
      output: input.output ? structuredClone(input.output) : null,
      eventIds: [...input.eventIds].sort(),
      blockers: [...new Set(input.blockers)].sort(),
      exactLocalizationCaptureReady: false as const,
      exactL2DerivationCaptureReady: input.exactL2DerivationCaptureReady,
      feedbackDepth: 0 as const,
      memoryIngestionAllowed: false as const,
      mayWriteProductionMemory: false as const,
      mayEnqueueFeedback: false as const,
      feedbackReingestionEnabled: false as const,
      optimizationReady: false as const,
    };
    const auditHash = canonicalHash(body);
    return cloneFreeze({ ...body, auditId: `l2-stage-audit:${auditHash.slice(0, 32)}`, auditHash });
  }

  private async appendUnresolved(input: {
    aggregationRunId: string | null;
    phase: L2StagedAuditPhase;
    state?: RunState;
    reason: L2StagedFailureReason;
    receiptHash?: string | null;
  }): Promise<void> {
    await this.appendAudit(this.makeAudit({
      aggregationRunId: input.aggregationRunId,
      phase: input.phase,
      status: "unresolved",
      runTokenHash: input.state?.runToken.tokenHash ?? null,
      stagedTokenHash: input.state?.stagedToken?.tokenHash ?? null,
      inputSetHash: input.state?.frozenInputs.inputSetHash ?? null,
      generationContractHash: input.state?.runToken.generationContractHash ?? null,
      receiptHash: input.receiptHash ?? null,
      output: null,
      eventIds: [],
      blockers: [input.reason],
      exactL2DerivationCaptureReady: false,
    }));
  }

  private async appendAudit(audit: L2StagedAggregationAudit): Promise<boolean> {
    try {
      await this.auditStore.append(audit);
      return true;
    } catch (error) {
      // There is intentionally no fallback to production Memory or feedback.
      this.logger?.warn(`[memory-tdai][shadow-l2-stage] Audit append failed (non-fatal): ${errorMessage(error)}`);
      return false;
    }
  }

  private async verifyReadbackAuthority(receipt: StrongL2CommitReadbackReceipt): Promise<void> {
    const authority = this.readbackAuthority;
    if (!authority) {
      throw new L2StageError("MISSING_READBACK_AUTHORITY", "commit-readback authority is unavailable");
    }
    if (receipt.readerAuthorityId !== authority.authorityId
      || receipt.readerAuthorityVersion !== authority.authorityVersion
      || receipt.backendBindingHash !== authority.authorityBindingHash) {
      throw new L2StageError(
        "READBACK_AUTHORITY_MISMATCH",
        "receipt reader authority differs from the configured authority",
      );
    }
    try {
      if (await authority.verifyCommittedSnapshot(cloneFreeze(receipt)) !== true) {
        throw new Error("configured authority did not confirm the committed snapshot");
      }
    } catch (error) {
      throw new L2StageError("READBACK_AUTHORITY_REJECTED", errorMessage(error));
    }
  }
}

function normalizeStage(output: StagedL2OutputInput, state: RunState): NormalizedStage {
  if (!output || typeof output !== "object") {
    throw new L2StageError("INVALID_STAGED_PAYLOAD", "staged output must be an object");
  }
  assertExactKeys(output, [
    "action", "claims", "content", "createdAt", "entityBindings", "logicalId", "metadata", "recordId", "scope",
  ], "staged output", "INVALID_STAGED_PAYLOAD");
  if (output.action !== "create" && output.action !== "update") {
    throw new L2StageError("UNSUPPORTED_STAGED_ACTION", `unsupported staged action ${String(output.action)}`);
  }
  if ((output.action === "create") === (state.baseline !== null)) {
    throw new L2StageError("BASELINE_ACTION_MISMATCH", "create requires no baseline and update requires one exact baseline");
  }
  requireNonEmpty(output.recordId, "staged.recordId", "INVALID_STAGED_PAYLOAD");
  requireNonEmpty(output.logicalId, "staged.logicalId", "INVALID_STAGED_PAYLOAD");
  if (typeof output.content !== "string" || !output.content.trim()) {
    throw new L2StageError("MISSING_STAGED_CONTENT", "staged content is required");
  }
  assertJsonOnly(output.metadata, "staged.metadata");
  assertScope(output.scope);
  assertBindings(output.entityBindings);
  if (output.scope.teamId !== state.scopeAuthority.teamId
    || output.scope.agentId !== state.scopeAuthority.agentId) {
    throw new L2StageError("SCOPE_AUTHORITY_MISMATCH", "staged output differs from runtime team/agent scope authority");
  }
  requireIso(output.createdAt, "staged.createdAt", "INVALID_STAGED_PAYLOAD");

  if (state.baseline) {
    if (output.recordId !== state.baseline.payload.record.id) {
      throw new L2StageError("STAGED_OUTPUT_ID_MISMATCH", "update output ID differs from its exact baseline");
    }
    if (output.logicalId !== state.baseline.payload.logicalId) {
      throw new L2StageError("STAGED_LOGICAL_ID_MISMATCH", "update logical ID differs from its exact baseline");
    }
    if (canonicalHash(output.scope) !== state.baseline.payload.scopeHash) {
      throw new L2StageError("STAGED_SCOPE_MISMATCH", "update scope differs from its stable-ID baseline");
    }
    if (canonicalHash(output.entityBindings) !== state.baseline.payload.entityBindingHash) {
      throw new L2StageError(
        "STAGED_ENTITY_BINDING_MISMATCH",
        "update entity bindings differ from its stable-ID baseline",
      );
    }
    if (output.createdAt !== state.baseline.payload.createdAt) {
      throw new L2StageError("INVALID_STAGED_PAYLOAD", "update must preserve baseline createdAt");
    }
  }

  const claims = normalizeClaims(output.content, output.claims, state.frozenInputs);
  return cloneFreeze({
    action: output.action,
    recordId: output.recordId,
    logicalId: output.logicalId,
    content: output.content,
    metadata: structuredClone(output.metadata),
    scope: structuredClone(output.scope),
    entityBindings: Object.fromEntries(Object.entries(output.entityBindings).sort(([left], [right]) => left.localeCompare(right))),
    createdAt: output.createdAt,
    claims,
  });
}

function normalizeClaims(
  content: string,
  rawClaims: StagedL2ClaimInput[],
  frozenInputs: FrozenAggregationInputSet,
): NormalizedClaim[] {
  if (!Array.isArray(rawClaims) || rawClaims.length === 0) {
    throw new L2StageError("MISSING_CLAIMS", "at least one claim is required");
  }
  const frozenRefs = new Set(frozenInputs.inputs.map((entry) => nodeKey(entry.record)));
  const claimIds = new Set<string>();
  const claims = rawClaims.map((claim): NormalizedClaim => {
    if (!claim || typeof claim !== "object") {
      throw new L2StageError("INVALID_STAGED_PAYLOAD", "claim must be an object");
    }
    assertExactKeys(claim, ["claimId", "sources", "span"], "claim", "INVALID_STAGED_PAYLOAD");
    requireNonEmpty(claim?.claimId, "claim.claimId", "INVALID_STAGED_PAYLOAD");
    if (claimIds.has(claim.claimId)) throw new L2StageError("DUPLICATE_CLAIM_ID", `duplicate claim ${claim.claimId}`);
    claimIds.add(claim.claimId);
    if (!claim.span || typeof claim.span !== "object") {
      throw new L2StageError("INVALID_CLAIM_SPAN", `missing span for claim ${claim.claimId}`);
    }
    assertExactKeys(claim.span, ["end", "start"], `claim span:${claim.claimId}`, "INVALID_CLAIM_SPAN");
    if (!Number.isSafeInteger(claim.span.start) || !Number.isSafeInteger(claim.span.end)
      || claim.span.start < 0 || claim.span.end <= claim.span.start || claim.span.end > content.length
      || !content.slice(claim.span.start, claim.span.end).trim()) {
      throw new L2StageError("INVALID_CLAIM_SPAN", `invalid span for claim ${claim.claimId}`);
    }
    if (!Array.isArray(claim.sources) || claim.sources.length === 0) {
      throw new L2StageError("MISSING_CLAIM_SOURCE", `claim ${claim.claimId} has no exact L1 source`);
    }
    const sourceKeys = new Set<string>();
    const sources = claim.sources.map((source) => {
      if (source && typeof source === "object") {
        assertExactKeys(source, ["id", "layer", "version"], `claim source:${claim.claimId}`, "SOURCE_OUTSIDE_FROZEN_SET");
      }
      if (!source || source.layer !== "L1" || !nonEmptyOrNull(source.id)
        || !Number.isSafeInteger(source.version) || source.version < 1) {
        throw new L2StageError("SOURCE_OUTSIDE_FROZEN_SET", `claim ${claim.claimId} has an invalid L1 source tuple`);
      }
      const key = nodeKey(source);
      if (!frozenRefs.has(key)) {
        throw new L2StageError("SOURCE_OUTSIDE_FROZEN_SET", `claim ${claim.claimId} cites ${key} outside its frozen set`);
      }
      if (sourceKeys.has(key)) {
        throw new L2StageError("DUPLICATE_CLAIM_SOURCE", `claim ${claim.claimId} repeats ${key}`);
      }
      sourceKeys.add(key);
      return { layer: "L1" as const, id: source.id, version: source.version };
    }).sort((left, right) => nodeKey(left).localeCompare(nodeKey(right)));
    return {
      claimId: claim.claimId,
      span: { start: claim.span.start, end: claim.span.end },
      sources,
    };
  }).sort((left, right) => left.span.start - right.span.start || left.span.end - right.span.end || left.claimId.localeCompare(right.claimId));

  for (let index = 1; index < claims.length; index++) {
    if (claims[index]!.span.start < claims[index - 1]!.span.end) {
      throw new L2StageError("OVERLAPPING_CLAIM_SPANS", "claim spans must not overlap");
    }
  }
  for (let index = 0; index < content.length; index++) {
    if (/\s/u.test(content[index]!)) continue;
    if (!claims.some((claim) => index >= claim.span.start && index < claim.span.end)) {
      throw new L2StageError("INCOMPLETE_CLAIM_COVERAGE", "claim spans do not cover every non-whitespace output character");
    }
  }
  return cloneFreeze(claims);
}

function validateReadbackAgainstStage(receipt: StrongL2CommitReadbackReceipt, state: RunState): void {
  try {
    assertExactKeys(receipt, [
      "acknowledgementBasis",
      "aggregationRunId",
      "backendBindingHash",
      "baselineRecordDigest",
      "commitOperationId",
      "committedAt",
      "committedVersion",
      "contentHash",
      "entityBindingHash",
      "metadataHash",
      "logicalId",
      "priorVersion",
      "readOperationId",
      "readbackAt",
      "readerAuthorityId",
      "readerAuthorityVersion",
      "readerSnapshotDigest",
      "receiptHash",
      "runTokenHash",
      "schemaVersion",
      "scopeHash",
      "stagedTokenHash",
      "stableOutputId",
      "storageRevision",
      "verifiedFieldSetHash",
      "createdAt",
    ], "readback receipt");
    const { receiptHash, ...body } = receipt;
    assertReadbackReceiptBody(body);
    requireHash(receiptHash, "receiptHash", "INVALID_READBACK_RECEIPT");
    if (canonicalHash(body) !== receiptHash) throw new Error("receipt hash mismatch");
    if (receipt.readerSnapshotDigest !== canonicalHash(readbackSnapshotBody(receipt))) {
      throw new Error("reader snapshot digest mismatch");
    }
  } catch (error) {
    if (error instanceof L2StageError) throw error;
    throw new L2StageError("INVALID_READBACK_RECEIPT", errorMessage(error));
  }
  const stage = state.stage!;
  if (receipt.aggregationRunId !== state.runToken.aggregationRunId
    || receipt.runTokenHash !== state.runToken.tokenHash
    || receipt.stagedTokenHash !== state.stagedToken?.tokenHash
    || receipt.baselineRecordDigest !== (state.baseline?.payload.recordDigest ?? null)) {
    throw new L2StageError(
      "READBACK_CAUSAL_BINDING_MISMATCH",
      "readback does not bind this aggregation run, staged payload, and exact baseline",
    );
  }
  if (receipt.verifiedFieldSetHash !== l2CommitReadbackVerifiedFieldSetHash()) {
    throw new L2StageError(
      "INVALID_READBACK_RECEIPT",
      "readback did not verify the complete required committed-row field set",
    );
  }
  if (receipt.stableOutputId !== stage.recordId) {
    throw new L2StageError("READBACK_OUTPUT_ID_MISMATCH", "readback stable output ID differs from staged output");
  }
  if (receipt.logicalId !== stage.logicalId || receipt.createdAt !== stage.createdAt) {
    throw new L2StageError(
      "READBACK_CAUSAL_BINDING_MISMATCH",
      "readback logical identity or creation time differs from the staged output",
    );
  }
  if (receipt.contentHash !== canonicalHash(stage.content)) {
    throw new L2StageError("READBACK_CONTENT_MISMATCH", "readback content hash differs from staged bytes");
  }
  if (receipt.metadataHash !== canonicalHash(stage.metadata)) {
    throw new L2StageError("READBACK_METADATA_MISMATCH", "readback metadata hash differs from staged metadata");
  }
  if (receipt.scopeHash !== canonicalHash(stage.scope)) {
    throw new L2StageError("READBACK_SCOPE_MISMATCH", "readback scope hash differs from staged scope");
  }
  if (receipt.entityBindingHash !== canonicalHash(stage.entityBindings)) {
    throw new L2StageError("READBACK_ENTITY_BINDING_MISMATCH", "readback entity-binding hash differs from staged bindings");
  }
  if (!Number.isSafeInteger(receipt.committedVersion) || receipt.committedVersion < 1) {
    throw new L2StageError("NON_POSITIVE_COMMITTED_VERSION", "readback version must be positive");
  }
  if (Date.parse(receipt.committedAt) < Date.parse(state.frozenInputs.frozenAt)) {
    throw new L2StageError("COMMIT_PRECEDES_FREEZE", "commit timestamp precedes input freeze");
  }
  if (Date.parse(receipt.committedAt) < Date.parse(stage.createdAt)) {
    throw new L2StageError("INVALID_READBACK_RECEIPT", "commit timestamp precedes staged createdAt");
  }
  const baselineVersion = state.baseline?.payload.record.version ?? null;
  if (receipt.priorVersion !== baselineVersion) {
    throw new L2StageError("READBACK_BASELINE_MISMATCH", "readback priorVersion differs from prepared baseline");
  }
  if (baselineVersion !== null && receipt.committedVersion !== baselineVersion + 1) {
    throw new L2StageError("NON_MONOTONIC_COMMITTED_VERSION", "update must commit exactly baseline version + 1");
  }
  if (baselineVersion === null && receipt.committedVersion !== 1) {
    throw new L2StageError("NON_MONOTONIC_COMMITTED_VERSION", "create must commit version 1");
  }
}

function assertReadbackReceiptBody(
  input: StrongL2CommitReadbackReceiptInput & { readerSnapshotDigest: string },
): void {
  if (input.schemaVersion !== "tdai-l2-commit-readback-receipt.v1"
    || input.acknowledgementBasis !== "committed_row_readback") {
    throw new L2StageError("INVALID_READBACK_RECEIPT", "readback receipt has an unsupported schema or basis");
  }
  requireNonEmpty(input.stableOutputId, "stableOutputId", "INVALID_READBACK_RECEIPT");
  requireNonEmpty(input.aggregationRunId, "aggregationRunId", "INVALID_READBACK_RECEIPT");
  requireHash(input.runTokenHash, "runTokenHash", "INVALID_READBACK_RECEIPT");
  requireHash(input.stagedTokenHash, "stagedTokenHash", "INVALID_READBACK_RECEIPT");
  requireNonEmpty(input.logicalId, "logicalId", "INVALID_READBACK_RECEIPT");
  requireHash(input.contentHash, "contentHash", "INVALID_READBACK_RECEIPT");
  requireHash(input.metadataHash, "metadataHash", "INVALID_READBACK_RECEIPT");
  requireHash(input.scopeHash, "scopeHash", "INVALID_READBACK_RECEIPT");
  requireHash(input.entityBindingHash, "entityBindingHash", "INVALID_READBACK_RECEIPT");
  requireNonEmpty(input.readerAuthorityId, "readerAuthorityId", "INVALID_READBACK_RECEIPT");
  requireNonEmpty(input.readerAuthorityVersion, "readerAuthorityVersion", "INVALID_READBACK_RECEIPT");
  requireHash(input.readerSnapshotDigest, "readerSnapshotDigest", "INVALID_READBACK_RECEIPT");
  requireIso(input.committedAt, "committedAt", "INVALID_READBACK_RECEIPT");
  requireIso(input.createdAt, "createdAt", "INVALID_READBACK_RECEIPT");
  requireIso(input.readbackAt, "readbackAt", "INVALID_READBACK_RECEIPT");
  requireNonEmpty(input.commitOperationId, "commitOperationId", "INVALID_READBACK_RECEIPT");
  requireNonEmpty(input.storageRevision, "storageRevision", "INVALID_READBACK_RECEIPT");
  requireHash(input.backendBindingHash, "backendBindingHash", "INVALID_READBACK_RECEIPT");
  requireNonEmpty(input.readOperationId, "readOperationId", "INVALID_READBACK_RECEIPT");
  requireHash(input.verifiedFieldSetHash, "verifiedFieldSetHash", "INVALID_READBACK_RECEIPT");
  if (input.baselineRecordDigest !== null) {
    requireHash(input.baselineRecordDigest, "baselineRecordDigest", "INVALID_READBACK_RECEIPT");
  }
  if (Date.parse(input.readbackAt) < Date.parse(input.committedAt)) {
    throw new L2StageError("INVALID_READBACK_RECEIPT", "readbackAt precedes committedAt");
  }
  if (!Number.isSafeInteger(input.committedVersion) || input.committedVersion < 1) {
    throw new L2StageError("NON_POSITIVE_COMMITTED_VERSION", "committedVersion must be a positive integer");
  }
  if (input.priorVersion !== null && (!Number.isSafeInteger(input.priorVersion) || input.priorVersion < 1)) {
    throw new L2StageError("INVALID_READBACK_RECEIPT", "priorVersion must be a positive integer or null");
  }
}

function readbackSnapshotBody(input: {
  aggregationRunId: string;
  runTokenHash: string;
  stagedTokenHash: string;
  stableOutputId: string;
  logicalId: string;
  committedVersion: number;
  contentHash: string;
  metadataHash: string;
  scopeHash: string;
  entityBindingHash: string;
  priorVersion: number | null;
  baselineRecordDigest: string | null;
  createdAt: string;
  committedAt: string;
  readbackAt: string;
  commitOperationId: string;
  storageRevision: string;
  backendBindingHash: string;
  readOperationId: string;
  verifiedFieldSetHash: string;
}) {
  return {
    aggregationRunId: input.aggregationRunId,
    runTokenHash: input.runTokenHash,
    stagedTokenHash: input.stagedTokenHash,
    stableOutputId: input.stableOutputId,
    logicalId: input.logicalId,
    committedVersion: input.committedVersion,
    contentHash: input.contentHash,
    metadataHash: input.metadataHash,
    scopeHash: input.scopeHash,
    entityBindingHash: input.entityBindingHash,
    priorVersion: input.priorVersion,
    baselineRecordDigest: input.baselineRecordDigest,
    createdAt: input.createdAt,
    committedAt: input.committedAt,
    readbackAt: input.readbackAt,
    commitOperationId: input.commitOperationId,
    storageRevision: input.storageRevision,
    backendBindingHash: input.backendBindingHash,
    readOperationId: input.readOperationId,
    verifiedFieldSetHash: input.verifiedFieldSetHash,
  };
}

function validRunToken(candidate: L2AggregationRunToken, expected: L2AggregationRunToken): boolean {
  try {
    const { tokenHash, ...body } = candidate;
    return canonicalHash(body) === tokenHash && canonicalHash(candidate) === canonicalHash(expected);
  } catch {
    return false;
  }
}

function validStagedToken(candidate: ValidatedL2StagedToken, expected: ValidatedL2StagedToken): boolean {
  try {
    const { tokenHash, ...body } = candidate;
    return canonicalHash(body) === tokenHash && canonicalHash(candidate) === canonicalHash(expected);
  } catch {
    return false;
  }
}

function immutableEdgeId(
  aggregationRunId: string,
  output: { layer: "L2"; id: string; version: number },
  claimId: string,
  source: ExactL1Ref,
): string {
  return `edge:l1-l2:v1:${canonicalHash({ aggregationRunId, output, claimId, source })}`;
}

function tokenSafety() {
  return {
    feedbackDepth: 0 as const,
    memoryIngestionAllowed: false as const,
    mayWriteProductionMemory: false as const,
    mayEnqueueFeedback: false as const,
    feedbackReingestionEnabled: false as const,
    optimizationReady: false as const,
  };
}

function assertJsonOnly(value: unknown, field: string, seen = new Set<object>()): asserts value is CaptureJsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new L2StageError("INVALID_STAGED_PAYLOAD", `${field} contains a non-finite number`);
    return;
  }
  if (!value || typeof value !== "object") {
    throw new L2StageError("INVALID_STAGED_PAYLOAD", `${field} must be JSON-only`);
  }
  if (seen.has(value)) throw new L2StageError("INVALID_STAGED_PAYLOAD", `${field} contains a cycle`);
  seen.add(value);
  if (Array.isArray(value)) {
    value.forEach((entry, index) => assertJsonOnly(entry, `${field}[${index}]`, seen));
  } else {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new L2StageError("INVALID_STAGED_PAYLOAD", `${field} must contain plain objects`);
    }
    Object.entries(value).forEach(([key, entry]) => {
      requireNonEmpty(key, `${field} key`, "INVALID_STAGED_PAYLOAD");
      assertJsonOnly(entry, `${field}.${key}`, seen);
    });
  }
  seen.delete(value);
}

function assertScope(scope: MemoryCaptureScope): void {
  if (!scope || typeof scope !== "object") {
    throw new L2StageError("INVALID_STAGED_PAYLOAD", "staged.scope must be an object");
  }
  const keys: Array<keyof MemoryCaptureScope> = [
    "agentId", "projectId", "sceneName", "sessionId", "sessionKey", "taskId", "teamId", "userId",
  ];
  assertExactKeys(scope, keys, "staged.scope", "INVALID_STAGED_PAYLOAD");
  for (const key of keys) {
    if (scope[key] !== null) requireNonEmpty(scope[key], `staged.scope.${key}`, "INVALID_STAGED_PAYLOAD");
  }
}

function assertBindings(bindings: Record<string, string>): void {
  if (!bindings || typeof bindings !== "object" || Array.isArray(bindings)) {
    throw new L2StageError("INVALID_STAGED_PAYLOAD", "entityBindings must be an object");
  }
  for (const [key, value] of Object.entries(bindings)) {
    requireNonEmpty(key, "entity binding key", "INVALID_STAGED_PAYLOAD");
    requireNonEmpty(value, `entityBindings.${key}`, "INVALID_STAGED_PAYLOAD");
  }
}

function assertExactKeys(
  value: object,
  keys: readonly PropertyKey[],
  field: string,
  reason: L2StagedFailureReason = "INVALID_READBACK_RECEIPT",
): void {
  const actual = Reflect.ownKeys(value).map(String).sort();
  const expected = keys.map(String).sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw new L2StageError(reason, `${field} has unexpected or missing fields`);
  }
}

function assertAuthorityScope(
  record: VersionedMemoryRecord,
  authority: { teamId: string; agentId: string },
): void {
  if (record.payload.scope.teamId !== authority.teamId || record.payload.scope.agentId !== authority.agentId) {
    throw new L2StageError("SCOPE_AUTHORITY_MISMATCH", "input team/agent scope differs from runtime authority");
  }
}

function requireNonEmpty(value: unknown, field: string, reason: L2StagedFailureReason): asserts value is string {
  if (typeof value !== "string" || !value.trim()) throw new L2StageError(reason, `${field} is required`);
}

function requireHash(value: unknown, field: string, reason: L2StagedFailureReason): asserts value is string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/i.test(value)) {
    throw new L2StageError(reason, `${field} must be a SHA-256 digest`);
  }
}

function requireIso(value: unknown, field: string, reason: L2StagedFailureReason): asserts value is string {
  if (typeof value !== "string" || !value.trim() || !Number.isFinite(Date.parse(value))) {
    throw new L2StageError(reason, `${field} must be an ISO-compatible timestamp`);
  }
}

function nodeKey(ref: { layer: string; id: string; version: number }): string {
  return `${ref.layer}\u001f${ref.id}\u001f${ref.version}`;
}

function nonEmptyOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function validCaptureContext(context: ShadowCaptureContext): boolean {
  return Boolean(
    context
    && typeof context.captureId === "string"
    && context.captureId.trim()
    && typeof context.capturedAt === "string"
    && Number.isFinite(Date.parse(context.capturedAt))
    && (context.origin === "production_capture" || context.origin === "benchmark_fixture")
    && context.feedbackDepth === 0
    && (context.taskRunId === null || (typeof context.taskRunId === "string" && Boolean(context.taskRunId.trim()))),
  );
}

function stageReason(error: unknown, fallback: L2StagedFailureReason): L2StagedFailureReason {
  return error instanceof L2StageError ? error.reason : fallback;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function deepFreeze<T>(value: T, seen = new Set<object>()): T {
  if (!value || typeof value !== "object" || seen.has(value as object)) return value;
  seen.add(value as object);
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function cloneFreeze<T>(value: T): T {
  return deepFreeze(structuredClone(value));
}
