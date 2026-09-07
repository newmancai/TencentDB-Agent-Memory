import type {
  L0MessageRecord,
  L0PersistenceObservation,
  L0PersistenceObserver,
} from "../conversation/l0-recorder.js";
import type {
  L1PersistenceObservation,
  L1PersistenceObserver,
  MemoryRecord,
} from "../record/l1-writer.js";
import type { Logger } from "../types.js";
import type { MemoryPersistenceReceipt } from "../store/types.js";
import { matchesMemoryPersistenceReceipt } from "../store/persistence-receipt.js";
import {
  createVersionedMemoryRecord,
  materializeL0Authority,
  type CaptureJsonValue,
  type ExactL1Ref,
  type MemoryCaptureScope,
  type ShadowCaptureContext,
  type VersionPredecessor,
} from "./capture-contracts.js";
import type { ShadowCaptureSidecarStore } from "./capture-sidecar.js";
import { canonicalHash } from "./observation-plane.js";

export type L0L1CaptureStatus = "captured" | "captured_unresolved" | "unresolved";

export type L0L1CaptureReason =
  | "WRITE_NOT_ACKNOWLEDGED"
  | "INVALID_PERSISTENCE_RECEIPT"
  | "NON_POSITIVE_VERSION"
  | "MISSING_LOGICAL_ID"
  | "MISSING_SOURCE_REFS"
  | "SOURCE_REF_MISMATCH"
  | "UNKNOWN_SOURCE_REF"
  | "MISSING_SOURCE_SPANS"
  | "MISSING_PREDECESSOR_VERSIONS"
  | "ASSISTANT_ONLY_SOURCE"
  | "CAPTURE_EVENT_APPEND_FAILED";

export interface L0L1CaptureAudit {
  schemaVersion: "tdai-l0-l1-capture-audit.v1";
  auditId: string;
  captureId: string;
  capturedAt: string;
  layer: "L0" | "L1";
  status: L0L1CaptureStatus;
  recordId: string | null;
  recordVersion: number | null;
  logicalId: string | null;
  receiptIds: string[];
  eventIds: string[];
  blockers: L0L1CaptureReason[];
  warnings: L0L1CaptureReason[];
  /** Ready only for this L0/L1 evidence slice, never a feedback decision. */
  localizationEvidenceReady: boolean;
  feedbackDepth: 0;
  memoryIngestionAllowed: false;
  mayWriteProductionMemory: false;
  mayEnqueueFeedback: false;
  optimizationReady: false;
  auditHash: string;
}

export interface L0L1CaptureAuditStore {
  append(audit: L0L1CaptureAudit): void | Promise<void>;
}

export class InMemoryL0L1CaptureAuditStore implements L0L1CaptureAuditStore {
  readonly audits: L0L1CaptureAudit[] = [];

  append(audit: L0L1CaptureAudit): void {
    this.audits.push(deepFreeze(structuredClone(audit)));
  }
}

interface SourceSpanDeclaration {
  sourceId: string;
  assertionId: string;
  claimId: string;
  start: number;
  end: number;
}

interface ParsedL1Provenance {
  logicalId: string | null;
  sourceIds: string[] | null;
  sourceSpans: SourceSpanDeclaration[];
  entityBindings: Record<string, string>;
  projectId: string | null;
  predecessors: VersionPredecessor[];
}

export interface PassiveL0L1ShadowCaptureOptions {
  /** Defaults to false. Merely constructing the adapter has no side effects. */
  enabled?: boolean;
  context: ShadowCaptureContext;
  eventStore: ShadowCaptureSidecarStore;
  auditStore: L0L1CaptureAuditStore;
  logger?: Logger;
}

/**
 * Opt-in bridge from acknowledged L0/L1 writes into the isolated capture
 * sidecar. It has no IMemoryStore or StorageAdapter reference, so it cannot
 * modify production Memory. Producer failures and observer failures are always
 * swallowed; missing evidence creates an unresolved audit and no invented fact.
 */
export class PassiveL0L1ShadowCaptureAdapter
implements L0PersistenceObserver, L1PersistenceObserver {
  private readonly enabled: boolean;
  private readonly context: ShadowCaptureContext;
  private readonly eventStore: ShadowCaptureSidecarStore;
  private readonly auditStore: L0L1CaptureAuditStore;
  private readonly logger?: Logger;
  private readonly l0ById = new Map<string, L0MessageRecord>();
  private queue: Promise<void> = Promise.resolve();

  constructor(options: PassiveL0L1ShadowCaptureOptions) {
    this.enabled = options.enabled ?? false;
    this.context = structuredClone(options.context);
    this.eventStore = options.eventStore;
    this.auditStore = options.auditStore;
    this.logger = options.logger;
  }

  observeL0Persistence(observation: L0PersistenceObservation): Promise<void> {
    if (!this.enabled) return Promise.resolve();
    return this.enqueue(async () => {
      try {
        await this.captureL0(observation);
      } catch (error) {
        await this.appendAuditSafely(this.makeAudit({
          layer: "L0",
          status: "unresolved",
          recordId: observation.records.length === 1 ? observation.records[0]!.id : null,
          recordVersion: 1,
          logicalId: null,
          receipts: observation.receipt ? [observation.receipt] : [],
          eventIds: [],
          blockers: ["CAPTURE_EVENT_APPEND_FAILED"],
          warnings: [],
          localizationEvidenceReady: false,
        }));
        this.logger?.warn?.(`[memory-tdai][shadow-l0-l1] L0 capture failed closed: ${errorMessage(error)}`);
      }
    });
  }

  observeL1Persistence(observation: L1PersistenceObservation): Promise<void> {
    if (!this.enabled) return Promise.resolve();
    return this.enqueue(async () => {
      try {
        await this.captureL1(observation);
      } catch (error) {
        await this.appendAuditSafely(this.makeAudit({
          layer: "L1",
          status: "unresolved",
          recordId: observation.record.id || null,
          recordVersion: observation.record.version ?? null,
          logicalId: parseL1Provenance(observation.record).logicalId,
          receipts: observation.receipts,
          eventIds: [],
          blockers: ["CAPTURE_EVENT_APPEND_FAILED"],
          warnings: [],
          localizationEvidenceReady: false,
        }));
        this.logger?.warn?.(`[memory-tdai][shadow-l0-l1] L1 capture failed closed: ${errorMessage(error)}`);
      }
    });
  }

  /** Await already-dispatched shadow work without exposing a production write. */
  async drain(): Promise<void> {
    await this.queue;
  }

  private enqueue(work: () => Promise<void>): Promise<void> {
    const queued = this.queue.then(work, work);
    this.queue = queued.catch(() => undefined);
    return queued;
  }

  private async captureL0(observation: L0PersistenceObservation): Promise<void> {
    const receipt = observation.receipt;
    const blockers: L0L1CaptureReason[] = [];
    if (!receipt) blockers.push("WRITE_NOT_ACKNOWLEDGED");
    else if (!validL0Receipt(observation, receipt)) blockers.push("INVALID_PERSISTENCE_RECEIPT");

    if (blockers.length > 0) {
      await this.appendAuditSafely(this.makeAudit({
        layer: "L0",
        status: "unresolved",
        recordId: observation.records.length === 1 ? observation.records[0]!.id : null,
        recordVersion: 1,
        logicalId: null,
        receipts: receipt ? [receipt] : [],
        eventIds: [],
        blockers,
        warnings: [],
        localizationEvidenceReady: false,
      }));
      return;
    }

    const events = observation.records.map((record) => materializeL0Authority({
      context: this.context,
      source: {
        recordId: record.id,
        version: 1,
        role: record.role,
        content: record.content,
        recordedAt: record.recordedAt,
        scope: l0Scope(record),
        materializationBasis: "persisted_l0_row",
      },
      // The current producer persists source IDs but no exact assertion spans.
      // Never upgrade the whole message into an asserted support span here.
      assertions: [],
    }));
    await this.eventStore.appendBatch(events);
    for (const record of observation.records) this.l0ById.set(record.id, structuredClone(record));
    await this.appendAuditSafely(this.makeAudit({
      layer: "L0",
      status: "captured",
      recordId: observation.records.length === 1 ? observation.records[0]!.id : null,
      recordVersion: 1,
      logicalId: null,
      receipts: [receipt!],
      eventIds: events.map((event) => event.eventId),
      blockers: [],
      warnings: [],
      localizationEvidenceReady: true,
    }));
  }

  private async captureL1(observation: L1PersistenceObservation): Promise<void> {
    const record = observation.record;
    const provenance = parseL1Provenance(record);
    const jsonlReceipt = observation.receipts.find((receipt) =>
      receipt.sink === "storage_jsonl" || receipt.sink === "local_jsonl");
    const hardBlockers: L0L1CaptureReason[] = [];
    if (!jsonlReceipt) hardBlockers.push("WRITE_NOT_ACKNOWLEDGED");
    else if (!validL1Receipt(observation, jsonlReceipt)) hardBlockers.push("INVALID_PERSISTENCE_RECEIPT");
    if (!Number.isSafeInteger(record.version) || (record.version ?? 0) < 1) hardBlockers.push("NON_POSITIVE_VERSION");
    if (!provenance.logicalId) hardBlockers.push("MISSING_LOGICAL_ID");
    const sourceIds = uniqueNonEmpty(record.source_message_ids);
    if (sourceIds.length === 0) hardBlockers.push("MISSING_SOURCE_REFS");
    if (provenance.sourceIds && !sameStringSet(sourceIds, provenance.sourceIds)) {
      hardBlockers.push("SOURCE_REF_MISMATCH");
    }
    if (provenance.sourceSpans.some((span) => !sourceIds.includes(span.sourceId))) {
      hardBlockers.push("SOURCE_REF_MISMATCH");
    }
    if (sourceIds.some((sourceId) => !this.l0ById.has(sourceId))) hardBlockers.push("UNKNOWN_SOURCE_REF");

    if (hardBlockers.length > 0) {
      await this.appendAuditSafely(this.makeAudit({
        layer: "L1",
        status: "unresolved",
        recordId: record.id || null,
        recordVersion: record.version ?? null,
        logicalId: provenance.logicalId,
        receipts: observation.receipts,
        eventIds: [],
        blockers: uniqueReasons(hardBlockers),
        warnings: [],
        localizationEvidenceReady: false,
      }));
      return;
    }

    const l1Ref: ExactL1Ref = { layer: "L1", id: record.id, version: record.version! };
    const warnings: L0L1CaptureReason[] = [];
    const spansBySource = new Map<string, SourceSpanDeclaration[]>();
    for (const declaration of provenance.sourceSpans) {
      spansBySource.set(declaration.sourceId, [...(spansBySource.get(declaration.sourceId) ?? []), declaration]);
    }
    if (sourceIds.some((sourceId) => (spansBySource.get(sourceId) ?? []).length === 0)) {
      warnings.push("MISSING_SOURCE_SPANS");
    }
    const sources = sourceIds.map((sourceId) => this.l0ById.get(sourceId)!);
    if (sources.every((source) => source.role === "assistant")) warnings.push("ASSISTANT_ONLY_SOURCE");
    if ((observation.decision.action === "update" || observation.decision.action === "merge")
      && !coversTargets(provenance.predecessors, observation.decision.target_ids)) {
      warnings.push("MISSING_PREDECESSOR_VERSIONS");
    }

    const memoryEvent = createVersionedMemoryRecord({
      context: this.context,
      layer: "L1",
      recordId: record.id,
      logicalId: provenance.logicalId!,
      version: record.version!,
      content: record.content,
      metadata: record.metadata as unknown as CaptureJsonValue,
      scope: l1Scope(record, provenance.projectId),
      entityBindings: provenance.entityBindings,
      sourceL0: sourceIds.map((id) => ({ layer: "L0" as const, id, version: 1 as const })),
      predecessors: provenance.predecessors,
      createdAt: record.createdAt,
      observedAt: record.updatedAt,
      capturePoint: "l1_write_receipt",
      persistenceReceiptHash: canonicalHash(jsonlReceipt!),
    });
    const linkedAuthorities = sources.flatMap((source) => {
      const declarations = spansBySource.get(source.id) ?? [];
      if (declarations.length === 0) return [];
      return [materializeL0Authority({
        context: this.context,
        source: {
          recordId: source.id,
          version: 1,
          role: source.role,
          content: source.content,
          recordedAt: source.recordedAt,
          scope: l0Scope(source),
          materializationBasis: "persisted_l0_row",
        },
        assertions: declarations.map((declaration) => ({
          assertionId: declaration.assertionId,
          claimId: declaration.claimId,
          span: { start: declaration.start, end: declaration.end },
          supports: [l1Ref],
        })),
      })];
    });
    const events = [memoryEvent, ...linkedAuthorities];
    await this.eventStore.appendBatch(events);
    const localizationEvidenceReady = warnings.length === 0;
    await this.appendAuditSafely(this.makeAudit({
      layer: "L1",
      status: localizationEvidenceReady ? "captured" : "captured_unresolved",
      recordId: record.id,
      recordVersion: record.version!,
      logicalId: provenance.logicalId,
      receipts: observation.receipts,
      eventIds: events.map((event) => event.eventId),
      blockers: [],
      warnings: uniqueReasons(warnings),
      localizationEvidenceReady,
    }));
  }

  private makeAudit(input: {
    layer: "L0" | "L1";
    status: L0L1CaptureStatus;
    recordId: string | null;
    recordVersion: number | null;
    logicalId: string | null;
    receipts: MemoryPersistenceReceipt[];
    eventIds: string[];
    blockers: L0L1CaptureReason[];
    warnings: L0L1CaptureReason[];
    localizationEvidenceReady: boolean;
  }): L0L1CaptureAudit {
    const body = {
      schemaVersion: "tdai-l0-l1-capture-audit.v1" as const,
      captureId: this.context.captureId,
      capturedAt: this.context.capturedAt,
      layer: input.layer,
      status: input.status,
      recordId: input.recordId,
      recordVersion: input.recordVersion,
      logicalId: input.logicalId,
      receiptIds: input.receipts.map((receipt) => receipt.receiptId).sort(),
      eventIds: [...input.eventIds].sort(),
      blockers: uniqueReasons(input.blockers),
      warnings: uniqueReasons(input.warnings),
      localizationEvidenceReady: input.localizationEvidenceReady,
      feedbackDepth: 0 as const,
      memoryIngestionAllowed: false as const,
      mayWriteProductionMemory: false as const,
      mayEnqueueFeedback: false as const,
      optimizationReady: false as const,
    };
    const auditHash = canonicalHash(body);
    return deepFreeze({ ...body, auditId: `capture-audit:${auditHash.slice(0, 32)}`, auditHash });
  }

  private async appendAuditSafely(audit: L0L1CaptureAudit): Promise<void> {
    try {
      await this.auditStore.append(audit);
    } catch (error) {
      // There is intentionally no fallback to Memory or feedback storage.
      this.logger?.warn?.(`[memory-tdai][shadow-l0-l1] Audit append failed (non-fatal): ${errorMessage(error)}`);
    }
  }
}

function validL0Receipt(observation: L0PersistenceObservation, receipt: MemoryPersistenceReceipt): boolean {
  const payload = observation.records.map((record) => JSON.stringify(record)).join("\n") + "\n";
  return (receipt.sink === "storage_jsonl" || receipt.sink === "local_jsonl")
    && matchesMemoryPersistenceReceipt(receipt, {
      layer: "L0",
      sink: receipt.sink,
      acknowledgementBasis: "append_resolved",
      target: observation.recordKey,
      records: observation.records.map((record) => ({ id: record.id, version: 1 })),
      payload,
    });
}

function validL1Receipt(observation: L1PersistenceObservation, receipt: MemoryPersistenceReceipt): boolean {
  return (receipt.sink === "storage_jsonl" || receipt.sink === "local_jsonl")
    && matchesMemoryPersistenceReceipt(receipt, {
      layer: "L1",
      sink: receipt.sink,
      acknowledgementBasis: "append_resolved",
      target: observation.recordKey,
      records: [{ id: observation.record.id, version: observation.record.version ?? 0 }],
      payload: JSON.stringify(observation.record) + "\n",
    });
}

function l0Scope(record: L0MessageRecord): MemoryCaptureScope {
  const extended = record as L0MessageRecord & { teamId?: string; taskId?: string; projectId?: string };
  return {
    teamId: nonEmptyOrNull(extended.teamId),
    userId: nonEmptyOrNull(record.userId),
    agentId: nonEmptyOrNull(record.agentId),
    sessionKey: nonEmptyOrNull(record.sessionKey),
    sessionId: nonEmptyOrNull(record.sessionId),
    taskId: nonEmptyOrNull(extended.taskId),
    projectId: nonEmptyOrNull(extended.projectId),
    sceneName: null,
  };
}

function l1Scope(record: MemoryRecord, projectId: string | null): MemoryCaptureScope {
  return {
    teamId: nonEmptyOrNull(record.teamId),
    userId: nonEmptyOrNull(record.userId),
    agentId: nonEmptyOrNull(record.agentId),
    sessionKey: nonEmptyOrNull(record.sessionKey),
    sessionId: nonEmptyOrNull(record.sessionId),
    taskId: nonEmptyOrNull(record.taskId),
    projectId,
    sceneName: nonEmptyOrNull(record.scene_name),
  };
}

function parseL1Provenance(record: MemoryRecord): ParsedL1Provenance {
  const metadata = isPlainObject(record.metadata) ? record.metadata as Record<string, unknown> : {};
  const raw = isPlainObject(metadata._tdai_provenance)
    ? metadata._tdai_provenance as Record<string, unknown>
    : {};
  const topLevelLogicalId = (record as MemoryRecord & { logicalId?: unknown }).logicalId;
  const logicalId = nonEmptyOrNull(typeof topLevelLogicalId === "string" ? topLevelLogicalId
    : typeof raw.logicalId === "string" ? raw.logicalId : null);
  const rawSources = raw.sourceIds ?? raw.source_message_ids;
  const sourceIds = Array.isArray(rawSources)
    ? uniqueNonEmpty(rawSources.filter((value): value is string => typeof value === "string"))
    : null;
  const entityBindings = isPlainObject(raw.entityBindings)
    ? Object.fromEntries(Object.entries(raw.entityBindings).filter(
      (entry): entry is [string, string] => Boolean(entry[0].trim()) && typeof entry[1] === "string" && Boolean(entry[1].trim()),
    ))
    : {};
  const sourceSpans = Array.isArray(raw.sourceSpans)
    ? raw.sourceSpans.flatMap((entry): SourceSpanDeclaration[] => {
      if (!isPlainObject(entry)) return [];
      return typeof entry.sourceId === "string"
        && typeof entry.assertionId === "string"
        && typeof entry.claimId === "string"
        && Number.isSafeInteger(entry.start)
        && Number.isSafeInteger(entry.end)
        ? [{
          sourceId: entry.sourceId,
          assertionId: entry.assertionId,
          claimId: entry.claimId,
          start: Number(entry.start),
          end: Number(entry.end),
        }]
        : [];
    })
    : [];
  const predecessors = parsePredecessors(raw);
  return {
    logicalId,
    sourceIds,
    sourceSpans,
    entityBindings,
    projectId: nonEmptyOrNull(typeof raw.projectId === "string" ? raw.projectId : null),
    predecessors,
  };
}

function parsePredecessors(raw: Record<string, unknown>): VersionPredecessor[] {
  const explicit = Array.isArray(raw.predecessors) ? raw.predecessors : [];
  const parsed = explicit.flatMap((entry): VersionPredecessor[] => {
    if (!isPlainObject(entry) || (entry.relation !== "replaces" && entry.relation !== "merged_from")
      || typeof entry.id !== "string" || !Number.isSafeInteger(entry.version) || Number(entry.version) < 1) return [];
    return [{
      relation: entry.relation,
      record: { layer: "L1", id: entry.id, version: Number(entry.version) },
    }];
  });
  if (parsed.length > 0) return parsed;
  const replaces = Array.isArray(raw.replaces) ? raw.replaces : [];
  return replaces.flatMap((entry): VersionPredecessor[] => {
    if (!isPlainObject(entry) || typeof entry.id !== "string"
      || !Number.isSafeInteger(entry.version) || Number(entry.version) < 1) return [];
    return [{ relation: "replaces", record: { layer: "L1", id: entry.id, version: Number(entry.version) } }];
  });
}

function coversTargets(predecessors: VersionPredecessor[], targetIds: string[]): boolean {
  const ids = new Set(predecessors.map((entry) => entry.record.id));
  return targetIds.length > 0 && targetIds.every((targetId) => ids.has(targetId));
}

function sameStringSet(left: string[], right: string[]): boolean {
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return sortedLeft.length === sortedRight.length
    && sortedLeft.every((value, index) => value === sortedRight[index]);
}

function uniqueNonEmpty(values: string[]): string[] {
  return [...new Set(values.filter((value) => typeof value === "string" && Boolean(value.trim())))];
}

function uniqueReasons(reasons: L0L1CaptureReason[]): L0L1CaptureReason[] {
  return [...new Set(reasons)].sort();
}

function nonEmptyOrNull(value: string | undefined | null): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function deepFreeze<T>(value: T): T {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value as Record<string, unknown>)) deepFreeze(child);
  return Object.freeze(value);
}
