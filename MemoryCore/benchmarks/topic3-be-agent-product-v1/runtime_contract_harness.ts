/** Emit machine-readable off/success/failure/cap behavior for the public adapter. */
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { runAnswerFeedbackAdapter } from "../../memory-feedback.js";

const output = resolve(process.argv[2] ?? "runtime-contract-results.json");
const baseline = ["host-baseline"];
const observation = {
  answerId: "answer-1",
  candidates: [
    { id: "failed-1", checkerPass: false },
    { id: "failed-2", checkerPass: false },
    { id: "passed", checkerPass: true },
  ],
};
const common = {
  observation,
  baselineFeedback: baseline,
  signalType: "explicit_correction" as const,
  policyVersion: "temporary-feedback:v1",
};

let offCalls = 0;
const off = await runAnswerFeedbackAdapter({
  ...common, enabled: false,
  selector: async () => { offCalls++; return ["failed-1"]; },
});
assert.equal(off.feedback, baseline);
assert.equal(offCalls, 0);

const enabled = await runAnswerFeedbackAdapter({
  ...common, enabled: true, maxSelectedK: 1,
  selector: async () => ["failed-1"],
});
assert.deepEqual(enabled.feedback, ["failed-1"]);

const forcedFailure = await runAnswerFeedbackAdapter({
  ...common, enabled: true,
  selector: async () => { throw Error("forced auxiliary failure"); },
});
assert.equal(forcedFailure.feedback, baseline);

const overK = await runAnswerFeedbackAdapter({
  ...common, enabled: true, maxSelectedK: 1,
  selector: async () => ["failed-1", "failed-2"],
});
assert.equal(overK.feedback, baseline);

const cases = [
  { id: "feature_off", expected: { mode: "baseline", status: "off", auxiliaryPathUsed: false,
    fallback: false, useBaseline: true }, result: off },
  { id: "enabled_selection", expected: { mode: "enabled", status: "selected", auxiliaryPathUsed: true,
    fallback: false, useBaseline: false }, result: enabled },
  { id: "forced_failure_fallback", expected: { mode: "enabled", status: "fallback",
    auxiliaryPathUsed: true, fallback: true, fallbackReason: "selector_failed", useBaseline: true },
    result: forcedFailure },
  { id: "over_k_fallback", expected: { mode: "enabled", status: "fallback",
    auxiliaryPathUsed: true, fallback: true, fallbackReason: "invalid_selection", useBaseline: true },
    result: overK },
].map(item => {
  const log = item.result.decisionLog;
  const passed = Object.entries(item.expected).every(([key, value]) => log[key as keyof typeof log] === value);
  assert(passed, `${item.id} did not match its expected decision log`);
  return { id: item.id, status: passed ? "pass" : "fail", expected: item.expected, decisionLog: log };
});

const summary = {
  schema: 1,
  suite: "topic3-be-runtime-contract-v2",
  status: cases.every(item => item.status === "pass") ? "pass" : "fail",
  cases,
  bounds: {
    maxCandidates: 256,
    defaultSelectedK: 8,
    allowedSelectedK: [1, 32],
    defaultTimeoutMs: 30000,
    maxTimeoutMs: 30000,
    persistentWrites: false,
  },
  scope: "Host-neutral answer-feedback sidecar; no Gateway hook, model call, memory mutation, or production traffic.",
};
await writeFile(output, `${JSON.stringify(summary, null, 2)}\n`);
console.log(JSON.stringify({ suite: summary.suite, status: summary.status, output }));
if (summary.status !== "pass") process.exitCode = 1;
