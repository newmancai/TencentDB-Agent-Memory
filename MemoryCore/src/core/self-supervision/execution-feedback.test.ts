import { describe, expect, it } from "vitest";
import { assessTaskEvidence, buildObjectiveTaskOutcome, repairMissingOutputPrefix } from "./execution-feedback.js";
import { observeToolExecutions } from "./tool-execution.js";
import type { LayerExposure, TaskOutcomeObservation } from "./types.js";

const contracts = { update: { id: "api", recordPath: ["record"], identityField: "id",
  changedFields: ["status"], success: { field: "status", value: "updated" }, errorField: "error" } };
const call = { role: "assistant", tool_calls: [{ id: "c1", function: {
  name: "update", arguments: JSON.stringify({ id: "A", status: "active" }) } }] };
const reply = (content: unknown) => ({ role: "tool", tool_call_id: "c1", content: JSON.stringify(content) });
const outcome = (status: TaskOutcomeObservation["status"]): TaskOutcomeObservation => ({
  status, outputHash: "o", environmentHash: "e", modelId: "m", validators: [{
    validatorId: "state", validatorVersion: "1", oracleKind: "database",
    status: status === "success" ? "pass" : "fail", score: null, evidenceHash: "h",
  }],
});
const exposure = (state: LayerExposure["state"]): LayerExposure => ({
  exposureId: `e-${state}`, node: { layer: "L1", id: "memory-1", version: 1 }, state,
  channel: "prompt_l1", rank: 1, score: 1, renderedHash: "h", truncated: false, derivationEdges: [],
});

describe("task-bound execution feedback", () => {
  it("repairs only a validated missing literal prefix", () => {
    const validBody = (body: string) => /^INTG-[A-Z]+-\d+(,INTG-[A-Z]+-\d+)*$/.test(body);
    expect(repairMissingOutputPrefix({ output: "INTG-EU-002,INTG-US-004", requiredPrefix: "IDS|",
      bodyIsValid: validBody })).toEqual({ output: "IDS|INTG-EU-002,INTG-US-004", repaired: true,
      reason: "missing_prefix_repaired" });
    expect(repairMissingOutputPrefix({ output: "BATCH|wrong", requiredPrefix: "IDS|",
      bodyIsValid: validBody }).reason).toBe("unsafe_or_invalid_body");
    expect(repairMissingOutputPrefix({ output: "invented", requiredPrefix: "IDS|",
      bodyIsValid: validBody }).reason).toBe("unsafe_or_invalid_body");
  });
  it("builds an all-required objective outcome without model judgment", () => {
    const pass = outcome("success").validators[0];
    expect(buildObjectiveTaskOutcome({ output: "done", environment: { state: "ok" }, modelId: "local",
      validators: [pass] })).toMatchObject({ status: "success", modelId: "local" });
    expect(buildObjectiveTaskOutcome({ output: "done", environment: {}, modelId: "local",
      validators: [{ ...pass, status: "fail" }] }).status).toBe("failure");
    expect(buildObjectiveTaskOutcome({ output: "done", environment: {}, modelId: "local",
      validators: [{ ...pass, status: "unverifiable" }] }).status).toBe("unknown");
  });
  it("does not turn a successful tool receipt into task success", () => {
    const observations = observeToolExecutions([call, reply({ status: "updated",
      record: { id: "A", status: "active" } })], { sessionId: "s", taskRunId: "run-1" }, contracts);
    expect(assessTaskEvidence({ taskRunId: "run-1", observations, outcome: null,
      memoryRelevance: "memory_relevant", exposures: [exposure("used")] })).toMatchObject({
      outcomeStatus: "unknown", executionStatus: "verified", feedbackStage: "insufficient_evidence",
      taskOutcomeAuthority: false, eligibleForMemoryAttributionStudy: false,
    });
  });

  it("ignores a previous task receipt and locates a current retrieval break", () => {
    const observations = observeToolExecutions([call, reply({ error: "old failure" })],
      { sessionId: "s", taskRunId: "run-old" }, contracts);
    expect(assessTaskEvidence({ taskRunId: "run-new", observations, outcome: outcome("failure"),
      memoryRelevance: "memory_relevant", exposures: [] })).toMatchObject({
      executionStatus: "unknown", feedbackStage: "retrieval",
      reasonCodes: ["ignored_unbound_or_stale_tool_evidence", "relevant_memory_not_exposed"],
    });
  });

  it("attributes an observed failure after Memory use to execution, not Memory content", () => {
    const observations = observeToolExecutions([call, reply({ error: "not found" })],
      { sessionId: "s", taskRunId: "run-1" }, contracts);
    expect(assessTaskEvidence({ taskRunId: "run-1", observations, outcome: outcome("failure"),
      memoryRelevance: "memory_relevant", exposures: [exposure("used")] })).toMatchObject({
      executionStatus: "failed", feedbackStage: "tool_execution", eligibleForMemoryAttributionStudy: true,
    });
  });

  it("keeps irrelevant-Memory task failures out of the Memory feedback path", () => {
    expect(assessTaskEvidence({ taskRunId: "run-1", observations: [], outcome: outcome("failure"),
      memoryRelevance: "no_match", exposures: [] })).toMatchObject({
      feedbackStage: "non_memory_failure", eligibleForMemoryAttributionStudy: false,
    });
  });

  it("does not trust a bare task status without objective validator evidence", () => {
    const bare = { ...outcome("success"), validators: [] };
    expect(assessTaskEvidence({ taskRunId: "run-1", observations: [], outcome: bare,
      memoryRelevance: "memory_relevant", exposures: [exposure("used")] })).toMatchObject({
      outcomeStatus: "success", taskOutcomeAuthority: false,
      feedbackStage: "insufficient_evidence", eligibleForMemoryAttributionStudy: false,
    });
  });
});
