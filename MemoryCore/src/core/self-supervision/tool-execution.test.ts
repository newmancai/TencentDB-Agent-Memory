import { describe, it, expect } from "vitest";
import { executionCaptureMessages, observeToolExecutions } from "./tool-execution.js";
import { formatExtractionPrompt } from "../prompts/l1-extraction.js";

const contracts = { update: { id: "test_api", recordPath: ["record"], identityField: "id",
  changedFields: ["status"], success: { field: "status", value: "updated" }, errorField: "error" } };
const call = { role: "assistant", tool_calls: [{ id: "c1", function: {
  name: "update", arguments: JSON.stringify({ id: "A", status: "active" }) } }] };
const reply = (content: unknown) => ({ role: "tool", tool_call_id: "c1", content: JSON.stringify(content) });
const observe = (messages: unknown[]) => observeToolExecutions(messages, "session", contracts)[0];

describe("observations from actual tool results", () => {
  it("corroborates a matching returned field but does not claim overall success", () => {
    const o = observe([call, reply({ status: "updated", record: { id: "A", status: "active" } })]);
    expect(o.validator.status).toBe("pass");
    expect(o.fieldChecks[0].validity).toBe("supported");
    expect(o.taskStatus).toBe("unknown");
  });
  it("does not let assistant success claims override an actual tool error", () => {
    const o = observe([call, reply({ error: "not found" }), { role: "assistant", content: "Successfully activated A" }]);
    expect(o.validator.status).toBe("fail");
    expect(o.fieldChecks[0].validity).toBe("unverifiable");
  });
  it("detects returned values that contradict the requested change", () => {
    expect(observe([call, reply({ status: "updated", record: { id: "A", status: "suspended" } })])
      .fieldChecks[0].validity).toBe("refuted");
  });
  it("does not corroborate a different entity", () => {
    expect(observe([call, reply({ status: "updated", record: { id: "B", status: "active" } })])
      .fieldChecks[0].validity).toBe("unverifiable");
  });
  it("keeps missing, ambiguous and out-of-order results unknown", () => {
    const r = reply({ status: "updated", record: { id: "A", status: "active" } });
    for (const messages of [[call], [r, call], [call, r, r], [call, call, r]]) {
      expect(observe(messages).validator.status).toBe("unverifiable");
    }
  });
  it("never interprets a response without its declared API contract", () => {
    const o = observeToolExecutions([call, reply({ status: "updated" })], "s")[0];
    expect(o.validator.status).toBe("unverifiable");
  });
  it("preserves tool identity and partial judgment in extraction input", () => {
    const o = observe([call, reply({ error: "not found" })]);
    const msgs = executionCaptureMessages([o], 1000);
    const prompt = formatExtractionPrompt({ newMessages: msgs });
    expect(msgs[0].role).toBe("tool");
    expect(prompt).toContain("[tool]");
    expect(prompt).toContain('"callId":"c1"');
    expect(prompt).toContain('"status":"fail"');
    expect(prompt).toContain("助手声称完成不证明执行成功");
  });
});
