import { describe, expect, it, vi } from "vitest";

import type { L1SearchResult } from "../store/types.js";
import {
  applyStructuredRecallBudget,
  createRecallShadowDraft,
  type RecallSearchFacts,
  type RecallShadowObservation,
} from "./recall-shadow-adapter.js";
import {
  OpenClawRecallTurnBridge,
  type OpenClawRecallTurnHandle,
} from "./openclaw-recall-turn-bridge.js";

const CONTEXT_A = "<relevant-memories>\n- [work_fact|atlas] Atlas uses Shanghai.\n</relevant-memories>";
const CONTEXT_B = "<relevant-memories>\n- [work_fact|boron] Boron uses Beijing.\n</relevant-memories>";

const search: RecallSearchFacts = {
  strategy: "keyword",
  status: "completed",
  failureCode: null,
  queryEligible: true,
  configuredMaxResults: 1,
  configuredScoreThreshold: 0.3,
  rawCandidateCount: 1,
  scoreFilteredCount: 0,
  rankPrunedCount: 0,
  selectedCandidateCount: 1,
  smallCorpusThresholdBypass: false,
};

function clock(): () => Date {
  let second = 0;
  return () => new Date(`2026-09-04T00:00:${String(second++).padStart(2, "0")}.000Z`);
}

function idFactory(...ids: string[]): (sessionKey: string) => string {
  return () => {
    const id = ids.shift();
    if (!id) throw new Error("test taskRunId exhausted");
    return id;
  };
}

function row(sessionKey: string, recordId: string, content: string): L1SearchResult {
  return {
    record_id: recordId,
    content,
    type: "work_fact",
    priority: 80,
    scene_name: "atlas",
    score: 0.9,
    timestamp_str: "2026-09-04T00:00:00.000Z",
    timestamp_start: "2026-09-04T00:00:00.000Z",
    timestamp_end: "",
    version: 1,
    session_key: sessionKey,
    session_id: `${sessionKey}-id`,
    team_id: "team-1",
    task_id: "task-source-1",
    user_id: "user-1",
    agent_id: "agent-1",
    metadata_json: JSON.stringify({ _tdai_provenance: { logicalId: `logical-${recordId}` } }),
  };
}

function draftFor(
  handle: OpenClawRecallTurnHandle,
  sessionKey: string,
  context: string,
  recordId = `${sessionKey}-record`,
) {
  const content = context.includes("Boron") ? "Boron uses Beijing." : "Atlas uses Shanghai.";
  const candidates = applyStructuredRecallBudget([{
    row: row(sessionKey, recordId, content),
    retrievalRank: 1,
    score: 0.9,
    stage: "l1_keyword",
    renderedText: context.slice("<relevant-memories>\n".length, -"\n</relevant-memories>".length),
  }], {});
  return createRecallShadowDraft({
    traceId: handle.shadowTap.traceId,
    capturedAt: handle.shadowTap.capturedAt!,
    sessionKey,
    sessionId: handle.shadowTap.sessionId,
    taskRunId: handle.taskRunId,
    actorId: "user-1",
    query: `query for ${recordId}`,
    expectedPrependContext: context,
    search,
    limits: {},
    candidates,
  });
}

function flushObserver(): Promise<void> {
  return new Promise((resolve) => setImmediate(resolve));
}

describe("OpenClawRecallTurnBridge", () => {
  it("acknowledges only a byte-exact context in llm_input and returns the last assistant text", async () => {
    const appended: RecallShadowObservation[] = [];
    const bridge = new OpenClawRecallTurnBridge({
      observer: { append: (event) => { appended.push(event); } },
      taskRunIdFactory: idFactory("task-run-a"),
      clock: clock(),
    });
    const handle = bridge.beginTurn({ sessionKey: "session-a", sessionId: "session-a-id" });

    expect(bridge.recordHookReturn({
      sessionKey: "session-a",
      taskRunId: handle.taskRunId,
      prependContext: CONTEXT_A,
    })).toBe(true);
    handle.shadowTap.onDraft(draftFor(handle, "session-a", CONTEXT_A));

    const observation = bridge.onLlmInput({
      sessionKey: "session-a",
      prompt: `Question before\n${CONTEXT_A}\nQuestion after`,
    });
    expect(observation).toMatchObject({
      taskRunId: "task-run-a",
      promptAssemblyEvidence: "exact_context_acknowledged",
    });
    expect(observation?.candidates[0]).toMatchObject({ exposed: true, highestObservedState: "exposed" });
    await flushObserver();
    expect(appended).toEqual([observation]);

    const result = bridge.endTurn({
      sessionKey: "session-a",
      messages: [
        { role: "assistant", content: "earlier" },
        { role: "tool", content: "ignored" },
        { role: "assistant", content: [{ type: "text", text: " final" }, { type: "output_text", text: "answer " }] },
      ],
    });
    expect(result).toMatchObject({
      sessionKey: "session-a",
      sessionId: "session-a-id",
      taskRunId: "task-run-a",
      observation,
      assistantText: "final\nanswer",
    });
  });

  it("finalizes a prompt mismatch as a non-exposed abstaining observation", async () => {
    const append = vi.fn();
    const bridge = new OpenClawRecallTurnBridge({
      observer: { append },
      taskRunIdFactory: idFactory("task-run-mismatch"),
      clock: clock(),
    });
    const handle = bridge.beginTurn({ sessionKey: "session-mismatch" });
    handle.shadowTap.onDraft(draftFor(handle, "session-mismatch", CONTEXT_A));
    bridge.recordHookReturn({
      sessionKey: "session-mismatch",
      taskRunId: handle.taskRunId,
      prependContext: CONTEXT_A,
    });

    const observation = bridge.onLlmInput({
      sessionKey: "session-mismatch",
      prompt: CONTEXT_A.replace("Shanghai", "Shenzhen"),
    });
    expect(observation).toMatchObject({
      promptAssemblyEvidence: "context_mismatch",
      noMatch: { decision: "abstain" },
    });
    expect(observation?.candidates[0]).toMatchObject({
      exposed: false,
      highestObservedState: "retrieved",
      notExposedReason: "prompt_mismatch",
    });
    await flushObserver();
    expect(append).toHaveBeenCalledWith(observation);
  });

  it("keeps concurrent sessions isolated", () => {
    const bridge = new OpenClawRecallTurnBridge({
      taskRunIdFactory: idFactory("task-run-a", "task-run-b"),
      clock: clock(),
    });
    const handleA = bridge.beginTurn({ sessionKey: "session-a", sessionId: "sid-a" });
    const handleB = bridge.beginTurn({ sessionKey: "session-b", sessionId: "sid-b" });
    handleB.shadowTap.onDraft(draftFor(handleB, "session-b", CONTEXT_B));
    handleA.shadowTap.onDraft(draftFor(handleA, "session-a", CONTEXT_A));
    bridge.recordHookReturn({ sessionKey: "session-b", taskRunId: handleB.taskRunId, prependContext: CONTEXT_B });
    bridge.recordHookReturn({ sessionKey: "session-a", taskRunId: handleA.taskRunId, prependContext: CONTEXT_A });

    const observationB = bridge.onLlmInput({ sessionKey: "session-b", prompt: `B:${CONTEXT_B}` });
    const observationA = bridge.onLlmInput({ sessionKey: "session-a", prompt: `A:${CONTEXT_A}` });
    expect(observationA).toMatchObject({ sessionKey: "session-a", sessionId: "sid-a", taskRunId: "task-run-a" });
    expect(observationB).toMatchObject({ sessionKey: "session-b", sessionId: "sid-b", taskRunId: "task-run-b" });

    expect(bridge.endTurn({ sessionKey: "session-a", messages: [{ role: "assistant", content: "A answer" }] }))
      .toMatchObject({ taskRunId: "task-run-a", assistantText: "A answer" });
    expect(bridge.onLlmInput({ sessionKey: "session-b", prompt: "later call" })).toBe(observationB);
    expect(bridge.endTurn({ sessionKey: "session-b", messages: [{ role: "assistant", content: "B answer" }] }))
      .toMatchObject({ taskRunId: "task-run-b", assistantText: "B answer" });
  });

  it("clears all per-turn state at agent_end", () => {
    const bridge = new OpenClawRecallTurnBridge({
      taskRunIdFactory: idFactory("task-run-old", "task-run-new"),
      clock: clock(),
    });
    const oldHandle = bridge.beginTurn({ sessionKey: "session-cleanup" });
    oldHandle.shadowTap.onDraft(draftFor(oldHandle, "session-cleanup", CONTEXT_A));
    bridge.recordHookReturn({
      sessionKey: "session-cleanup",
      taskRunId: oldHandle.taskRunId,
      prependContext: CONTEXT_A,
    });
    bridge.onLlmInput({ sessionKey: "session-cleanup", prompt: CONTEXT_A });

    expect(bridge.endTurn({ sessionKey: "session-cleanup", messages: [] }))
      .toMatchObject({ taskRunId: "task-run-old", assistantText: null });
    expect(bridge.endTurn({ sessionKey: "session-cleanup", messages: [] })).toBeNull();
    expect(bridge.onLlmInput({ sessionKey: "session-cleanup", prompt: CONTEXT_A })).toBeNull();
    expect(bridge.recordHookReturn({
      sessionKey: "session-cleanup",
      taskRunId: oldHandle.taskRunId,
      prependContext: CONTEXT_A,
    })).toBe(false);

    const newHandle = bridge.beginTurn({ sessionKey: "session-cleanup" });
    oldHandle.shadowTap.onDraft(draftFor(oldHandle, "session-cleanup", CONTEXT_A, "stale-record"));
    expect(newHandle.taskRunId).toBe("task-run-new");
    expect(bridge.endTurn({ sessionKey: "session-cleanup", messages: [] }))
      .toMatchObject({ taskRunId: "task-run-new", observation: null });
  });
});
