import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  recordConversation,
  type L0MessageRecord,
  type L0PersistenceObservation,
} from "../conversation/l0-recorder.js";
import {
  writeMemory,
  type L1PersistenceObservation,
  type MemoryRecord,
} from "../record/l1-writer.js";
import type {
  IMemoryStore,
  L1RecordRow,
  MemoryPersistenceReceipt,
} from "../store/types.js";
import { createMemoryPersistenceReceipt } from "../store/persistence-receipt.js";
import { InMemoryShadowCaptureSidecarStore } from "./capture-sidecar.js";
import {
  InMemoryL0L1CaptureAuditStore,
  PassiveL0L1ShadowCaptureAdapter,
} from "./l0-l1-shadow-adapter.js";
import type { ShadowCaptureContext } from "./capture-contracts.js";

const context: ShadowCaptureContext = {
  captureId: "capture-l0-l1-1",
  capturedAt: "2026-09-04T07:00:00.000Z",
  origin: "production_capture",
  feedbackDepth: 0,
  taskRunId: "task-1",
};

function sourceRecord(role: "user" | "assistant" = "user"): L0MessageRecord {
  return {
    sessionKey: "session-key",
    sessionId: "session-1",
    userId: "user-1",
    agentId: "agent-1",
    recordedAt: "2026-09-04T06:59:00.000Z",
    id: role === "user" ? "msg-user-1" : "msg-assistant-1",
    role,
    content: role === "user" ? "Atlas 部署区域是上海。" : "我推测 Atlas 部署区域是上海。",
    timestamp: 1788505140000,
  };
}

function receipt(input: {
  layer: "L0" | "L1";
  target: string;
  records: Array<{ id: string; version: number }>;
  payload: string;
}): MemoryPersistenceReceipt {
  return createMemoryPersistenceReceipt({
    layer: input.layer,
    sink: "storage_jsonl",
    acknowledgementBasis: "append_resolved",
    target: input.target,
    records: input.records,
    payload: input.payload,
    acknowledgedAt: "2026-09-04T07:00:00.000Z",
  });
}

function l0Observation(record = sourceRecord()): L0PersistenceObservation {
  const recordKey = "conversations/2026-09-04.jsonl";
  const payload = `${JSON.stringify(record)}\n`;
  return {
    layer: "L0",
    recordKey,
    records: [record],
    receipt: receipt({ layer: "L0", target: recordKey, records: [{ id: record.id, version: 1 }], payload }),
    failure: null,
  };
}

function l1Record(overrides: Partial<MemoryRecord> = {}): MemoryRecord {
  const source = sourceRecord();
  return {
    id: "l1-atlas-region",
    content: "Atlas 部署区域是上海。",
    type: "work_fact",
    priority: 90,
    scene_name: "atlas-deployment",
    source_message_ids: [source.id],
    metadata: {
      _tdai_provenance: {
        logicalId: "atlas-region",
        sourceIds: [source.id],
        entityBindings: { project: "atlas", region: "shanghai" },
        projectId: "atlas",
        sourceSpans: [{
          sourceId: source.id,
          assertionId: "assert-atlas-region",
          claimId: "atlas-region",
          start: 0,
          end: source.content.length,
        }],
      },
    } as MemoryRecord["metadata"],
    timestamps: ["2026-09-04T06:59:00.000Z"],
    createdAt: "2026-09-04T06:59:30.000Z",
    updatedAt: "2026-09-04T06:59:30.000Z",
    version: 2,
    sessionKey: "session-key",
    sessionId: "session-1",
    taskId: "task-1",
    teamId: "team-1",
    userId: "user-1",
    agentId: "agent-1",
    ...overrides,
  };
}

function l1Observation(record = l1Record()): L1PersistenceObservation {
  const recordKey = "records/2026-09-04.jsonl";
  const payload = `${JSON.stringify(record)}\n`;
  return {
    layer: "L1",
    recordKey,
    record,
    decision: { record_id: record.id, action: "store", target_ids: [] },
    receipts: [receipt({
      layer: "L1",
      target: recordKey,
      records: [{ id: record.id, version: record.version ?? 0 }],
      payload,
    })],
    failures: { jsonl: null, memoryStore: null },
  };
}

function l1Row(recordId: string, version: number): L1RecordRow {
  return {
    record_id: recordId,
    content: `${recordId} content`,
    type: "work_fact",
    priority: 50,
    scene_name: "atlas-deployment",
    session_key: "session-key",
    session_id: "session-1",
    team_id: "team-1",
    task_id: "task-1",
    user_id: "user-1",
    agent_id: "agent-1",
    version,
    timestamp_str: "2026-09-04T06:59:00.000Z",
    timestamp_start: "2026-09-04T06:59:00.000Z",
    timestamp_end: "2026-09-04T06:59:00.000Z",
    created_time: "2026-09-04T06:59:00.000Z",
    updated_time: "2026-09-04T06:59:00.000Z",
    metadata_json: "{}",
  };
}

function l1WriterStore(rows: L1RecordRow[]): IMemoryStore {
  return {
    queryL1Records: async () => rows,
    deleteL1Batch: async () => true,
    upsertL1: async () => true,
  } as unknown as IMemoryStore;
}

describe("passive L0/L1 shadow capture adapter", () => {
  it("is disabled by default and performs no sidecar or audit writes", async () => {
    const eventStore = new InMemoryShadowCaptureSidecarStore();
    const auditStore = new InMemoryL0L1CaptureAuditStore();
    const adapter = new PassiveL0L1ShadowCaptureAdapter({ context, eventStore, auditStore });

    await adapter.observeL0Persistence(l0Observation());
    await adapter.observeL1Persistence(l1Observation());

    expect(eventStore.events).toEqual([]);
    expect(auditStore.audits).toEqual([]);
  });

  it("captures the recorder's resolved JSONL acknowledgement without a hook", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-l0-passive-"));
    try {
      const eventStore = new InMemoryShadowCaptureSidecarStore();
      const auditStore = new InMemoryL0L1CaptureAuditStore();
      const adapter = new PassiveL0L1ShadowCaptureAdapter({ enabled: true, context, eventStore, auditStore });

      const messages = await recordConversation({
        sessionKey: "session-key",
        sessionId: "session-1",
        rawMessages: [{
          id: "msg-live-path",
          role: "user",
          content: "Atlas 部署区域是上海。",
          timestamp: 1788505140000,
        }],
        baseDir: root,
        shadowObserver: adapter,
      });
      await adapter.drain();

      expect(messages).toHaveLength(1);
      expect(eventStore.events).toHaveLength(1);
      expect(eventStore.events[0]?.eventType === "materialized_l0_authority"
        && eventStore.events[0].source).toMatchObject({
        record: { layer: "L0", id: "msg-live-path", version: 1 },
        role: "user",
        authorityClass: "user_assertion",
      });
      expect(auditStore.audits[0]).toMatchObject({ status: "captured", localizationEvidenceReady: true });
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("binds an acknowledged positive L1 version to role-correct persisted L0", async () => {
    const eventStore = new InMemoryShadowCaptureSidecarStore();
    const auditStore = new InMemoryL0L1CaptureAuditStore();
    const adapter = new PassiveL0L1ShadowCaptureAdapter({ enabled: true, context, eventStore, auditStore });

    await adapter.observeL0Persistence(l0Observation());
    await adapter.observeL1Persistence(l1Observation());

    const l1 = eventStore.events.find((event) => event.eventType === "versioned_memory_record");
    const linkedAuthority = eventStore.events.find((event) =>
      event.eventType === "materialized_l0_authority" && event.assertions.length > 0);
    expect(l1?.eventType === "versioned_memory_record" && l1.payload).toMatchObject({
      record: { layer: "L1", id: "l1-atlas-region", version: 2 },
      logicalId: "atlas-region",
      sourceL0: [{ layer: "L0", id: "msg-user-1", version: 1 }],
      capturePoint: "l1_write_receipt",
    });
    expect(linkedAuthority?.eventType === "materialized_l0_authority" && linkedAuthority.source).toMatchObject({
      role: "user",
      authorityClass: "user_assertion",
      eligibleForUserFactSupport: true,
    });
    expect(auditStore.audits.at(-1)).toMatchObject({
      layer: "L1",
      status: "captured",
      localizationEvidenceReady: true,
      blockers: [],
      warnings: [],
      optimizationReady: false,
    });
  });

  it("preserves assistant provenance without promoting it to a user assertion", async () => {
    const eventStore = new InMemoryShadowCaptureSidecarStore();
    const auditStore = new InMemoryL0L1CaptureAuditStore();
    const adapter = new PassiveL0L1ShadowCaptureAdapter({ enabled: true, context, eventStore, auditStore });
    const assistant = sourceRecord("assistant");
    const record = l1Record({
      source_message_ids: [assistant.id],
      metadata: {
        _tdai_provenance: {
          logicalId: "atlas-region",
          sourceIds: [assistant.id],
          sourceSpans: [{
            sourceId: assistant.id,
            assertionId: "assert-assistant-atlas",
            claimId: "atlas-region",
            start: 0,
            end: assistant.content.length,
          }],
        },
      } as MemoryRecord["metadata"],
    });

    await adapter.observeL0Persistence(l0Observation(assistant));
    await adapter.observeL1Persistence(l1Observation(record));

    const authority = eventStore.events.find((event) =>
      event.eventType === "materialized_l0_authority" && event.assertions.length > 0);
    expect(authority?.eventType === "materialized_l0_authority" && authority.source).toMatchObject({
      role: "assistant",
      authorityClass: "assistant_generated_output",
      eligibleForUserFactSupport: false,
    });
    expect(auditStore.audits.at(-1)).toMatchObject({
      status: "captured_unresolved",
      localizationEvidenceReady: false,
      warnings: ["ASSISTANT_ONLY_SOURCE"],
    });
  });

  it("keeps exact source refs but marks missing source spans unresolved", async () => {
    const eventStore = new InMemoryShadowCaptureSidecarStore();
    const auditStore = new InMemoryL0L1CaptureAuditStore();
    const adapter = new PassiveL0L1ShadowCaptureAdapter({ enabled: true, context, eventStore, auditStore });
    const record = l1Record({
      metadata: {
        _tdai_provenance: {
          logicalId: "atlas-region",
          sourceIds: ["msg-user-1"],
        },
      } as MemoryRecord["metadata"],
    });

    await adapter.observeL0Persistence(l0Observation());
    await adapter.observeL1Persistence(l1Observation(record));

    const l1 = eventStore.events.find((event) => event.eventType === "versioned_memory_record");
    expect(l1?.eventType === "versioned_memory_record" && l1.payload.sourceL0).toEqual([
      { layer: "L0", id: "msg-user-1", version: 1 },
    ]);
    expect(auditStore.audits.at(-1)).toMatchObject({
      status: "captured_unresolved",
      warnings: ["MISSING_SOURCE_SPANS"],
      localizationEvidenceReady: false,
    });
  });

  it("fails closed on a missing receipt instead of hashing an attempted write", async () => {
    const eventStore = new InMemoryShadowCaptureSidecarStore();
    const auditStore = new InMemoryL0L1CaptureAuditStore();
    const adapter = new PassiveL0L1ShadowCaptureAdapter({ enabled: true, context, eventStore, auditStore });
    const observation = l0Observation();
    observation.receipt = null;
    observation.failure = "append failed";

    await adapter.observeL0Persistence(observation);

    expect(eventStore.events).toEqual([]);
    expect(auditStore.audits).toHaveLength(1);
    expect(auditStore.audits[0]).toMatchObject({
      status: "unresolved",
      blockers: ["WRITE_NOT_ACKNOWLEDGED"],
      localizationEvidenceReady: false,
      optimizationReady: false,
    });
  });

  it("starts a stored record at v1 while keeping a missing logical ID unresolved", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-l1-passive-"));
    try {
      const eventStore = new InMemoryShadowCaptureSidecarStore();
      const auditStore = new InMemoryL0L1CaptureAuditStore();
      const adapter = new PassiveL0L1ShadowCaptureAdapter({ enabled: true, context, eventStore, auditStore });
      await adapter.observeL0Persistence(l0Observation());

      const record = await writeMemory({
        memory: {
          content: "Atlas 部署区域是上海。",
          type: "work_fact",
          priority: 90,
          scene_name: "atlas-deployment",
          source_message_ids: ["msg-user-1"],
          metadata: {},
        },
        decision: { record_id: "legacy-l1", action: "store", target_ids: [] },
        baseDir: root,
        sessionKey: "session-key",
        sessionId: "session-1",
        shadowObserver: adapter,
      });
      await adapter.drain();
      expect(auditStore.audits).toHaveLength(2);

      expect(record).toMatchObject({ id: "legacy-l1", version: 1 });
      expect(existsSync(join(root, "records"))).toBe(true);
      expect(eventStore.events.filter((event) => event.eventType === "versioned_memory_record")).toEqual([]);
      expect(auditStore.audits.at(-1)).toMatchObject({
        layer: "L1",
        status: "unresolved",
        blockers: ["MISSING_LOGICAL_ID"],
        localizationEvidenceReady: false,
      });
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("increments update/merge from the maximum version only when all targets resolve", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-l1-versioned-update-"));
    try {
      const record = await writeMemory({
        memory: {
          content: "new input",
          type: "work_fact",
          priority: 20,
          scene_name: "atlas-deployment",
          source_message_ids: ["msg-user-1"],
          metadata: {},
        },
        decision: {
          record_id: "merged-l1",
          action: "merge",
          target_ids: ["old-a", "old-b"],
          merged_content: "merged result",
          merged_type: "work_method",
          merged_priority: 88,
          merged_timestamps: ["2026-09-04T06:59:00.000Z"],
        },
        baseDir: root,
        sessionKey: "session-key",
        vectorStore: l1WriterStore([l1Row("old-a", 2), l1Row("old-b", 4)]),
      });

      expect(record).toMatchObject({
        id: "merged-l1",
        version: 5,
        content: "merged result",
        type: "work_method",
        priority: 88,
        source_message_ids: ["msg-user-1"],
      });
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("keeps update/merge at v0 when a requested target is missing", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-l1-unresolved-update-"));
    try {
      const eventStore = new InMemoryShadowCaptureSidecarStore();
      const auditStore = new InMemoryL0L1CaptureAuditStore();
      const adapter = new PassiveL0L1ShadowCaptureAdapter({ enabled: true, context, eventStore, auditStore });
      await adapter.observeL0Persistence(l0Observation());

      const record = await writeMemory({
        memory: {
          content: "new input",
          type: "work_fact",
          priority: 20,
          scene_name: "atlas-deployment",
          source_message_ids: ["msg-user-1"],
          metadata: l1Record().metadata,
        },
        decision: {
          record_id: "unresolved-l1",
          action: "update",
          target_ids: ["old-a", "missing-b"],
          merged_content: "updated result",
        },
        baseDir: root,
        sessionKey: "session-key",
        vectorStore: l1WriterStore([l1Row("old-a", 4)]),
        shadowObserver: adapter,
      });
      await adapter.drain();

      expect(record).toMatchObject({
        id: "unresolved-l1",
        version: 0,
        content: "updated result",
        type: "work_fact",
        priority: 20,
      });
      expect(eventStore.events.filter((event) => event.eventType === "versioned_memory_record")).toEqual([]);
      expect(auditStore.audits.at(-1)).toMatchObject({
        layer: "L1",
        status: "unresolved",
        blockers: ["NON_POSITIVE_VERSION"],
        localizationEvidenceReady: false,
      });
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("does not promote an unresolved v0 predecessor into an exact successor", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-l1-v0-predecessor-"));
    try {
      const record = await writeMemory({
        memory: {
          content: "new input",
          type: "work_fact",
          priority: 20,
          scene_name: "atlas-deployment",
          source_message_ids: ["msg-user-1"],
          metadata: {},
        },
        decision: {
          record_id: "replacement-for-v0",
          action: "update",
          target_ids: ["legacy-v0"],
          merged_content: "updated result",
        },
        baseDir: root,
        sessionKey: "session-key",
        vectorStore: l1WriterStore([l1Row("legacy-v0", 0)]),
      });

      expect(record).toMatchObject({ id: "replacement-for-v0", version: 0 });
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("keeps L0 and L1 task writes successful when an opt-in observer throws", async () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-passive-fail-open-"));
    const throwing = {
      observeL0Persistence(): never { throw new Error("shadow unavailable"); },
      observeL1Persistence(): never { throw new Error("shadow unavailable"); },
    };
    try {
      const messages = await recordConversation({
        sessionKey: "session-key",
        sessionId: "session-1",
        rawMessages: [{
          id: "msg-fail-open",
          role: "user",
          content: "请把 Atlas 的部署区域记录为上海。",
          timestamp: 1788505140000,
        }],
        baseDir: root,
        shadowObserver: throwing,
      });
      const memory = await writeMemory({
        memory: {
          content: "Atlas 部署区域是上海。",
          type: "work_fact",
          priority: 90,
          scene_name: "atlas-deployment",
          source_message_ids: ["msg-fail-open"],
          metadata: {},
        },
        decision: { record_id: "l1-fail-open", action: "store", target_ids: [] },
        baseDir: root,
        sessionKey: "session-key",
        shadowObserver: throwing,
      });

      expect(messages).toHaveLength(1);
      expect(memory?.id).toBe("l1-fail-open");
      expect(existsSync(join(root, "conversations"))).toBe(true);
      expect(existsSync(join(root, "records"))).toBe(true);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});
