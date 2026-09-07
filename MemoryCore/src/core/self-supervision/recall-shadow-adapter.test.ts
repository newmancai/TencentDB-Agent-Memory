import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import type { L1SearchResult } from "../store/types.js";
import {
  createVersionedMemoryRecord,
  type CaptureJsonValue,
  type VersionedMemoryRecord,
} from "./capture-contracts.js";
import {
  applyStructuredRecallBudget,
  createRecallShadowDraft,
  dispatchRecallShadowObservation,
  finalizeRecallShadowObservation,
  JsonlRecallShadowObserver,
  type RecallSearchFacts,
  type StructuredRecallCandidate,
} from "./recall-shadow-adapter.js";

function row(id: string, version = 3, logicalId: string | null = `logical-${id}`): L1SearchResult {
  return {
    record_id: id,
    content: `memory content ${id}`,
    type: "work_fact",
    priority: 80,
    scene_name: "atlas",
    score: 0.9,
    timestamp_str: "2026-09-04T00:00:00.000Z",
    timestamp_start: "2026-09-04T00:00:00.000Z",
    timestamp_end: "",
    version,
    session_key: "session-key-1",
    session_id: "session-1",
    team_id: "team-1",
    task_id: "task-1",
    user_id: "user-1",
    agent_id: "agent-1",
    metadata_json: logicalId === null
      ? "{}"
      : JSON.stringify({ _tdai_provenance: { logicalId, persistenceReceiptHash: "a".repeat(64) } }),
  };
}

function candidate(id: string, rank: number, renderedText: string): StructuredRecallCandidate {
  return {
    row: row(id),
    retrievalRank: rank,
    score: 0.9 - (rank - 1) * 0.1,
    stage: "l1_hybrid",
    renderedText,
  };
}

function identityAuthority(
  authorityRow: L1SearchResult,
  overrides: { content?: string; logicalId?: string; receiptHash?: string } = {},
): VersionedMemoryRecord {
  const metadata = JSON.parse(authorityRow.metadata_json) as CaptureJsonValue;
  return createVersionedMemoryRecord({
    context: {
      captureId: `capture-${authorityRow.record_id}-${overrides.content ?? "base"}`,
      capturedAt: "2026-09-04T00:00:00.000Z",
      origin: "production_capture",
      feedbackDepth: 0,
      taskRunId: authorityRow.task_id || null,
    },
    layer: "L1",
    recordId: authorityRow.record_id,
    logicalId: overrides.logicalId ?? `logical-${authorityRow.record_id}`,
    version: authorityRow.version,
    content: overrides.content ?? authorityRow.content,
    metadata,
    scope: {
      teamId: authorityRow.team_id || null,
      userId: authorityRow.user_id || null,
      agentId: authorityRow.agent_id || null,
      sessionKey: authorityRow.session_key || null,
      sessionId: authorityRow.session_id || null,
      taskId: authorityRow.task_id || null,
      projectId: null,
      sceneName: authorityRow.scene_name || null,
    },
    entityBindings: {},
    createdAt: authorityRow.timestamp_str,
    observedAt: authorityRow.timestamp_str,
    capturePoint: "l1_write_receipt",
    persistenceReceiptHash: overrides.receiptHash ?? "a".repeat(64),
  });
}

const search: RecallSearchFacts = {
  strategy: "hybrid",
  status: "completed",
  failureCode: null,
  queryEligible: true,
  configuredMaxResults: 5,
  configuredScoreThreshold: 0.3,
  rawCandidateCount: 8,
  scoreFilteredCount: 3,
  rankPrunedCount: 3,
  selectedCandidateCount: 2,
  smallCorpusThresholdBypass: false,
};

describe("structured recall budget", () => {
  it("keeps exact identity, retrieval rank and score for exposed and pruned candidates", () => {
    const candidates = [
      candidate("l1-a", 1, "- [work_fact] Atlas uses Shanghai."),
      candidate("l1-b", 2, "- [work_fact] Atlas uses Beijing."),
    ];
    const budgeted = applyStructuredRecallBudget(candidates, {
      maxTotalRecallChars: candidates[0].renderedText.length,
    });

    expect(budgeted).toHaveLength(2);
    expect(budgeted[0]).toMatchObject({
      row: { record_id: "l1-a", version: 3 },
      retrievalRank: 1,
      promptRank: 1,
      score: 0.9,
      notExposedReason: null,
    });
    expect(budgeted[1]).toMatchObject({
      row: { record_id: "l1-b", version: 3 },
      retrievalRank: 2,
      promptRank: null,
      budgetedText: null,
      score: 0.8,
      notExposedReason: "budget_pruned",
    });
  });

  it("truncates Unicode by code point while retaining its candidate tuple", () => {
    const [result] = applyStructuredRecallBudget(
      [candidate("l1-emoji", 1, "- [work_fact] 部署在上海🚀，需要双活。")],
      { maxCharsPerMemory: 12 },
    );
    expect(Array.from(result.budgetedText ?? "")).toHaveLength(12);
    expect(result.budgetedText).not.toContain("�");
    expect(result).toMatchObject({ retrievalRank: 1, promptRank: 1, truncated: true });
  });
});

describe("two-phase recall/exposure observation", () => {
  function fixture() {
    const budgeted = applyStructuredRecallBudget([
      candidate("l1-a", 1, "- [work_fact] Atlas uses Shanghai."),
      candidate("l1-b", 2, "- [work_fact] Atlas uses Beijing."),
    ], { maxTotalRecallChars: 50 });
    const lines = budgeted.flatMap((entry) => entry.budgetedText === null ? [] : [entry.budgetedText]);
    const prependContext = `<relevant-memories>\n${lines.join("\n")}\n</relevant-memories>`;
    return {
      prependContext,
      draft: createRecallShadowDraft({
        traceId: "trace-1",
        capturedAt: "2026-09-04T00:00:00.000Z",
        sessionKey: "session-key-1",
        sessionId: "session-1",
        taskRunId: "task-1",
        actorId: "user-1",
        query: "Atlas 部署在哪里？",
        expectedPrependContext: prependContext,
        search,
        limits: { maxTotalRecallChars: 50 },
        candidates: budgeted,
      }),
    };
  }

  it("marks only budget-selected candidates exposed after exact prompt acknowledgement", () => {
    const { draft, prependContext } = fixture();
    const event = finalizeRecallShadowObservation(
      draft,
      "2026-09-04T00:00:01.000Z",
      prependContext,
    );

    expect(event.promptAssemblyEvidence).toBe("exact_context_acknowledged");
    expect(event.candidates[0]).toMatchObject({
      recordId: "l1-a",
      logicalId: "logical-l1-a",
      version: 3,
      retrievalRank: 1,
      promptRank: 1,
      highestObservedState: "exposed",
      exposed: true,
      used: false,
      notExposedReason: null,
    });
    expect(event.candidates[1]).toMatchObject({
      recordId: "l1-b",
      highestObservedState: "retrieved",
      exposed: false,
      used: false,
      notExposedReason: "budget_pruned",
    });
    expect(event.noMatch).toEqual({
      systemDecision: "inject_candidates",
      expectedMatch: "unknown",
      decision: "abstain",
      reasonCodes: ["independent_relevance_authority_missing"],
    });
    expect(event).toMatchObject({
      feedbackDepth: 0,
      memoryIngestionAllowed: false,
      mayWriteProductionMemory: false,
      mayEnqueueFeedback: false,
      feedbackReingestionEnabled: false,
      optimizationReady: false,
    });
  });

  it("does not promote a digest-shaped metadata claim without capture authority", () => {
    const { draft, prependContext } = fixture();
    const event = finalizeRecallShadowObservation(
      draft,
      "2026-09-04T00:00:01.000Z",
      prependContext,
    );

    expect(event.candidates[0]).toMatchObject({
      exactIdentityReady: false,
      persistenceReceiptHash: null,
      recordDigest: null,
      identityAuthorityEventId: null,
      identityAuthorityEventHash: null,
      identityReasonCodes: [
        "missing_identity_authority",
        "unverified_metadata_persistence_receipt",
      ],
    });
  });

  it("joins a validated capture event to the exact L1 tuple", () => {
    const { draft, prependContext } = fixture();
    const authority = identityAuthority(draft.candidates[0]!.row);
    const event = finalizeRecallShadowObservation(
      draft,
      "2026-09-04T00:00:01.000Z",
      prependContext,
      { records: [authority] },
    );

    expect(event.candidates[0]).toMatchObject({
      recordId: authority.payload.record.id,
      logicalId: authority.payload.logicalId,
      version: authority.payload.record.version,
      persistenceReceiptHash: authority.payload.persistenceReceiptHash,
      recordDigest: authority.payload.recordDigest,
      identityAuthorityEventId: authority.eventId,
      identityAuthorityEventHash: authority.eventHash,
      exactIdentityReady: true,
      identityReasonCodes: [],
    });
    expect(event.candidates[1]).toMatchObject({
      exactIdentityReady: false,
      identityReasonCodes: [
        "missing_identity_authority",
        "unverified_metadata_persistence_receipt",
      ],
    });
  });

  it("fails closed when validated authorities for one record-version conflict", () => {
    const { draft, prependContext } = fixture();
    const first = identityAuthority(draft.candidates[0]!.row);
    const conflicting = identityAuthority(draft.candidates[0]!.row, { content: "different persisted content" });
    const event = finalizeRecallShadowObservation(
      draft,
      "2026-09-04T00:00:01.000Z",
      prependContext,
      { records: [first, conflicting] },
    );

    expect(event.candidates[0]).toMatchObject({
      exactIdentityReady: false,
      persistenceReceiptHash: null,
      recordDigest: null,
      identityReasonCodes: ["conflicting_identity_authority"],
    });
  });

  it("rejects a metadata receipt claim that does not match the validated authority", () => {
    const { draft, prependContext } = fixture();
    const authority = identityAuthority(draft.candidates[0]!.row, { receiptHash: "b".repeat(64) });
    const event = finalizeRecallShadowObservation(
      draft,
      "2026-09-04T00:00:01.000Z",
      prependContext,
      { records: [authority] },
    );

    expect(event.candidates[0]).toMatchObject({
      exactIdentityReady: false,
      persistenceReceiptHash: null,
      recordDigest: null,
      identityReasonCodes: ["identity_authority_receipt_mismatch"],
    });
  });

  it("rejects a recalled row whose metadata or scope differs from capture authority", () => {
    const authorityRow = row("l1-tampered-payload");
    const authority = identityAuthority(authorityRow);
    const recalledRow: L1SearchResult = {
      ...authorityRow,
      team_id: "team-other",
      metadata_json: JSON.stringify({
        ...JSON.parse(authorityRow.metadata_json),
        mutableField: "changed-after-capture",
      }),
    };
    const [budgeted] = applyStructuredRecallBudget([{
      ...candidate("l1-tampered-payload", 1, "- [work_fact] Atlas uses Shanghai."),
      row: recalledRow,
    }], {});
    const prependContext = budgeted.budgetedText!;
    const draft = createRecallShadowDraft({
      traceId: "trace-tampered-payload",
      capturedAt: "2026-09-04T00:00:00.000Z",
      sessionKey: "session-key-1",
      sessionId: "session-1",
      taskRunId: "task-1",
      actorId: "user-1",
      query: "Atlas region",
      expectedPrependContext: prependContext,
      search: { ...search, selectedCandidateCount: 1 },
      limits: {},
      candidates: [budgeted],
    });

    const event = finalizeRecallShadowObservation(
      draft,
      "2026-09-04T00:00:01.000Z",
      prependContext,
      { records: [authority] },
    );

    expect(event.candidates[0]).toMatchObject({
      exactIdentityReady: false,
      persistenceReceiptHash: null,
      recordDigest: null,
      identityReasonCodes: [
        "identity_authority_metadata_hash_mismatch",
        "identity_authority_scope_hash_mismatch",
      ],
    });
  });

  it("rejects entity bindings that are present in the row but absent from capture authority", () => {
    const authorityRow = row("l1-tampered-entity");
    authorityRow.metadata_json = JSON.stringify({
      _tdai_provenance: {
        logicalId: "logical-l1-tampered-entity",
        persistenceReceiptHash: "a".repeat(64),
        entityBindings: { project: "atlas" },
      },
    });
    const authority = identityAuthority(authorityRow);
    const [budgeted] = applyStructuredRecallBudget([{
      ...candidate("l1-tampered-entity", 1, "- [work_fact] Atlas uses Shanghai."),
      row: authorityRow,
    }], {});
    const prependContext = budgeted.budgetedText!;
    const draft = createRecallShadowDraft({
      traceId: "trace-tampered-entity",
      capturedAt: "2026-09-04T00:00:00.000Z",
      sessionKey: "session-key-1",
      sessionId: "session-1",
      taskRunId: "task-1",
      actorId: "user-1",
      query: "Atlas region",
      expectedPrependContext: prependContext,
      search: { ...search, selectedCandidateCount: 1 },
      limits: {},
      candidates: [budgeted],
    });

    const event = finalizeRecallShadowObservation(
      draft,
      "2026-09-04T00:00:01.000Z",
      prependContext,
      { records: [authority] },
    );

    expect(event.candidates[0]).toMatchObject({
      exactIdentityReady: false,
      identityReasonCodes: ["identity_authority_entity_binding_hash_mismatch"],
    });
  });

  it("does not call prepared prompt content exposed without an acknowledgement", () => {
    const { draft } = fixture();
    const event = finalizeRecallShadowObservation(draft, "2026-09-04T00:00:01.000Z");
    expect(event.promptAssemblyEvidence).toBe("not_acknowledged");
    expect(event.candidates.every((entry) => !entry.exposed && !entry.used)).toBe(true);
    expect(event.candidates[0].notExposedReason).toBe("prompt_not_acknowledged");
  });

  it("reports inject_none when the prompt budget prunes every selected candidate", () => {
    const budgeted = applyStructuredRecallBudget(
      [candidate("l1-budget-pruned", 1, "- [work_fact] Atlas uses Shanghai.")],
      { maxTotalRecallChars: 1 },
    );
    const draft = createRecallShadowDraft({
      traceId: "trace-budget-pruned",
      capturedAt: "2026-09-04T00:00:00.000Z",
      sessionKey: "session-key-1",
      actorId: "user-1",
      query: "Atlas region",
      search: { ...search, selectedCandidateCount: 1 },
      limits: { maxTotalRecallChars: 1 },
      candidates: budgeted,
    });

    const event = finalizeRecallShadowObservation(draft, "2026-09-04T00:00:01.000Z");

    expect(event.candidates[0]).toMatchObject({
      promptRank: null,
      highestObservedState: "retrieved",
      notExposedReason: "budget_pruned",
    });
    expect(event.noMatch.systemDecision).toBe("inject_none");
    expect(event.search.selectedCandidateCount).toBe(1);
  });

  it("keeps legacy version zero and missing logical ID unresolved instead of inventing identity", () => {
    const unresolved = candidate("legacy", 1, "- [work_fact] legacy");
    unresolved.row = row("legacy", 0, null);
    const budgeted = applyStructuredRecallBudget([unresolved], {});
    const prependContext = "- [work_fact] legacy";
    const draft = createRecallShadowDraft({
      traceId: "trace-legacy",
      capturedAt: "2026-09-04T00:00:00.000Z",
      sessionKey: "session-key-1",
      actorId: "user-1",
      query: "legacy",
      expectedPrependContext: prependContext,
      search: { ...search, selectedCandidateCount: 1 },
      limits: {},
      candidates: budgeted,
    });
    const event = finalizeRecallShadowObservation(draft, "2026-09-04T00:00:01.000Z", prependContext);
    expect(event.candidates[0]).toMatchObject({
      logicalId: null,
      version: 0,
      exactIdentityReady: false,
      persistenceReceiptHash: null,
      identityReasonCodes: ["unresolved_version", "missing_identity_authority", "missing_logical_id"],
      exposed: true,
      used: false,
    });
    expect(event.warnings).toEqual(expect.arrayContaining(["missing_session_id", "missing_task_run_id"]));
  });

  it("contains synchronous and asynchronous sidecar failures", async () => {
    const { draft, prependContext } = fixture();
    const event = finalizeRecallShadowObservation(draft, "2026-09-04T00:00:01.000Z", prependContext);
    const warn = vi.fn();

    expect(() => dispatchRecallShadowObservation({ append: () => { throw new Error("sync"); } }, event, { warn })).not.toThrow();
    expect(() => dispatchRecallShadowObservation({ append: async () => { throw new Error("async"); } }, event, { warn })).not.toThrow();
    await new Promise<void>((resolve) => setImmediate(resolve));
    await new Promise<void>((resolve) => setImmediate(resolve));

    expect(warn).toHaveBeenCalledTimes(2);
    expect(warn.mock.calls.map(([message]) => String(message))).toEqual([
      expect.stringContaining("sync"),
      expect.stringContaining("async"),
    ]);
  });

  it("persists an immutable append-only hash-only observation when explicitly wired", () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-recall-shadow-observer-"));
    try {
      const { draft, prependContext } = fixture();
      const event = finalizeRecallShadowObservation(draft, "2026-09-04T00:00:01.000Z", prependContext);
      const observer = new JsonlRecallShadowObserver(root);
      observer.append(event);

      const [reloaded] = new JsonlRecallShadowObserver(root).readAll();
      expect(reloaded).toEqual(event);
      expect(JSON.stringify(reloaded)).not.toContain("Atlas 部署在哪里");
      expect(JSON.stringify(reloaded)).not.toContain("Atlas uses Shanghai");
      expect(() => observer.append(event)).toThrow(/Duplicate recall shadow observation/);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});
