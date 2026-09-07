import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { parseConfig } from "../../config.js";
import type { IMemoryStore, L1FtsResult } from "../store/types.js";
import {
  finalizeRecallShadowObservation,
  type RecallShadowDraft,
} from "../self-supervision/recall-shadow-adapter.js";
import { performAutoRecall } from "./auto-recall.js";

const roots: string[] = [];

afterEach(() => {
  for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

function resultRow(id: string, content: string, score: number): L1FtsResult {
  return {
    record_id: id,
    content,
    type: "work_fact",
    priority: 80,
    scene_name: "atlas",
    score,
    timestamp_str: "2026-09-04T00:00:00.000Z",
    timestamp_start: "2026-09-04T00:00:00.000Z",
    timestamp_end: "",
    version: id === "l1-a" ? 4 : 2,
    session_key: "session-key-1",
    session_id: "session-1",
    team_id: "team-1",
    task_id: "task-1",
    user_id: "user-1",
    agent_id: "agent-1",
    metadata_json: JSON.stringify({
      _tdai_provenance: { logicalId: `logical-${id}`, persistenceReceiptHash: "b".repeat(64) },
    }),
  };
}

function keywordStore(rows: L1FtsResult[]): IMemoryStore {
  return {
    isFtsAvailable: () => true,
    searchL1Fts: vi.fn(() => rows),
    getCapabilities: () => ({
      vectorSearch: false,
      ftsSearch: true,
      nativeHybridSearch: false,
      sparseVectors: false,
    }),
  } as unknown as IMemoryStore;
}

describe("auto-recall structured shadow handoff", () => {
  it("removes a record before ranking and lets the next Memory occupy the recall slot", async () => {
    const pluginDataDir = mkdtempSync(join(tmpdir(), "tdai-auto-recall-intervention-"));
    roots.push(pluginDataDir);
    const rows = [
      resultRow("l1-a", "Atlas uses Beijing.", 0.91),
      resultRow("l1-b", "Atlas uses Shanghai.", 0.82),
    ];
    const store = keywordStore(rows);
    const cfg = parseConfig({ recall: { strategy: "keyword", scoreThreshold: 0.3, maxResults: 1 } });

    const full = await performAutoRecall({
      userText: "Atlas region",
      actorId: "user-1",
      sessionKey: "session-key-1",
      cfg,
      pluginDataDir,
      vectorStore: store,
    });
    const masked = await performAutoRecall({
      userText: "Atlas region",
      actorId: "user-1",
      sessionKey: "session-key-1",
      cfg,
      pluginDataDir,
      vectorStore: store,
      intervention: { excludedRecordIds: ["l1-a"] },
    });

    expect(full?.prependContext).toContain("Atlas uses Beijing.");
    expect(full?.prependContext).not.toContain("Atlas uses Shanghai.");
    expect(masked?.prependContext).not.toContain("Atlas uses Beijing.");
    expect(masked?.prependContext).toContain("Atlas uses Shanghai.");
    expect(store.searchL1Fts).toHaveBeenNthCalledWith(1, expect.any(String), 2);
    expect(store.searchL1Fts).toHaveBeenNthCalledWith(2, expect.any(String), 3);
  });

  it("preserves record identity through budget and waits for host acknowledgement before exposure", async () => {
    const pluginDataDir = mkdtempSync(join(tmpdir(), "tdai-auto-recall-shadow-"));
    roots.push(pluginDataDir);
    const rows = [
      resultRow("l1-a", "Atlas uses Shanghai.", 0.91),
      resultRow("l1-b", "Atlas uses Beijing.", 0.82),
    ];
    const cfg = parseConfig({ recall: { strategy: "keyword", scoreThreshold: 0.3, maxResults: 2 } });
    // Exactly one full rendered line fits, forcing the second structured tuple
    // to remain retrieved-only rather than disappear from observation.
    cfg.recall.maxTotalRecallChars = "- [work_fact|atlas] Atlas uses Shanghai. (活动时间: 2026-09-04)".length;
    let draft: RecallShadowDraft | undefined;

    const result = await performAutoRecall({
      userText: "Atlas region",
      actorId: "user-1",
      sessionKey: "session-key-1",
      cfg,
      pluginDataDir,
      vectorStore: keywordStore(rows),
      shadowTap: {
        traceId: "trace-1",
        capturedAt: "2026-09-04T00:00:00.000Z",
        sessionId: "session-1",
        taskRunId: "task-1",
        onDraft: (value) => { draft = value; },
      },
    });

    expect(result?.prependContext).toContain("Atlas uses Shanghai.");
    expect(result?.prependContext).not.toContain("Atlas uses Beijing.");
    expect(result?.recalledL1Memories?.[0]?.score).toBe(0);
    expect(draft?.candidates).toHaveLength(2);
    expect(draft?.candidates[0]).toMatchObject({
      row: { record_id: "l1-a", version: 4 },
      retrievalRank: 1,
      promptRank: 1,
      score: 0.91,
    });
    expect(draft?.candidates[1]).toMatchObject({
      row: { record_id: "l1-b", version: 2 },
      retrievalRank: 2,
      promptRank: null,
      score: 0.82,
      notExposedReason: "budget_pruned",
    });

    const observation = finalizeRecallShadowObservation(
      draft!,
      "2026-09-04T00:00:01.000Z",
      result!.prependContext,
    );
    expect(observation.candidates.map((candidate) => candidate.highestObservedState)).toEqual([
      "exposed",
      "retrieved",
    ]);
    expect(observation.candidates.every((candidate) => candidate.used === false)).toBe(true);
  });

  it("contains a shadow draft callback failure without changing recall output", async () => {
    const pluginDataDir = mkdtempSync(join(tmpdir(), "tdai-auto-recall-shadow-fail-"));
    roots.push(pluginDataDir);
    const warn = vi.fn();
    const cfg = parseConfig({ recall: { strategy: "keyword", scoreThreshold: 0.3, maxResults: 1 } });

    const result = await performAutoRecall({
      userText: "Atlas region",
      actorId: "user-1",
      sessionKey: "session-key-1",
      cfg,
      pluginDataDir,
      vectorStore: keywordStore([resultRow("l1-a", "Atlas uses Shanghai.", 0.91)]),
      logger: { debug: vi.fn(), info: vi.fn(), warn, error: vi.fn() },
      shadowTap: {
        traceId: "trace-failure",
        onDraft: () => { throw new Error("sidecar unavailable"); },
      },
    });

    expect(result?.prependContext).toContain("Atlas uses Shanghai.");
    await Promise.resolve();
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("sidecar unavailable"));
  });

  it("does not await an async shadow callback and contains its rejection", async () => {
    const pluginDataDir = mkdtempSync(join(tmpdir(), "tdai-auto-recall-shadow-async-fail-"));
    roots.push(pluginDataDir);
    const warn = vi.fn();
    const cfg = parseConfig({ recall: { strategy: "keyword", scoreThreshold: 0.3, maxResults: 1 } });
    let rejectObserver!: (error: Error) => void;
    let callbackStarted = false;
    const observerPending = new Promise<void>((_resolve, reject) => {
      rejectObserver = reject;
    });

    const result = await performAutoRecall({
      userText: "Atlas region",
      actorId: "user-1",
      sessionKey: "session-key-1",
      cfg,
      pluginDataDir,
      vectorStore: keywordStore([resultRow("l1-a", "Atlas uses Shanghai.", 0.91)]),
      logger: { debug: vi.fn(), info: vi.fn(), warn, error: vi.fn() },
      shadowTap: {
        traceId: "trace-async-failure",
        onDraft: () => {
          callbackStarted = true;
          return observerPending;
        },
      },
    });

    expect(result?.prependContext).toContain("Atlas uses Shanghai.");
    expect(callbackStarted).toBe(true);
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining("sidecar unavailable async"));

    rejectObserver(new Error("sidecar unavailable async"));
    await Promise.resolve();
    await Promise.resolve();

    expect(warn).toHaveBeenCalledWith(expect.stringContaining("sidecar unavailable async"));
  });
});
