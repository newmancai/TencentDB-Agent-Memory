/** Machine-readable off/success/forced-failure/cap verification for the B adapter. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

import { runAnswerFeedbackAdapter } from '../../src/core/memory-feedback/index.js';

const output = resolve(process.argv[2] ?? 'results/runtime-contract.json');
await mkdir(dirname(output), { recursive: true });
const baseline = ['host-baseline'];
const observation = { answerId: 'answer-1', candidates: [
  { id: 'failed-1', checkerPass: false },
  { id: 'failed-2', checkerPass: false },
  { id: 'passed', checkerPass: true },
] };
const common = {
  observation,
  baselineFeedback: baseline,
  signalType: 'explicit_correction' as const,
  policyVersion: 'temporary-feedback:v1',
};

let offCalls = 0;
const off = await runAnswerFeedbackAdapter({ ...common, enabled: false,
  selector: async () => { offCalls += 1; return ['failed-1']; } });
assert.equal(off.feedback, baseline);
assert.equal(offCalls, 0);

const enabled = await runAnswerFeedbackAdapter({ ...common, enabled: true, maxSelectedK: 1,
  selector: async () => ['failed-1'] });
assert.deepEqual(enabled.feedback, ['failed-1']);

const forcedFailure = await runAnswerFeedbackAdapter({ ...common, enabled: true,
  selector: async () => { throw Error('forced auxiliary failure'); } });
assert.equal(forcedFailure.feedback, baseline);

const overK = await runAnswerFeedbackAdapter({ ...common, enabled: true, maxSelectedK: 1,
  selector: async () => ['failed-1', 'failed-2'] });
assert.equal(overK.feedback, baseline);

const cases = [
  { id: 'feature_off', expected: { status: 'off', auxiliaryPathUsed: false, useBaseline: true }, result: off },
  { id: 'enabled_selection', expected: { status: 'selected', auxiliaryPathUsed: true, useBaseline: false }, result: enabled },
  { id: 'forced_failure_fallback', expected: { status: 'fallback', fallbackReason: 'selector_failed', useBaseline: true }, result: forcedFailure },
  { id: 'over_k_fallback', expected: { status: 'fallback', fallbackReason: 'invalid_selection', useBaseline: true }, result: overK },
].map(item => {
  const observed = item.result.decisionLog;
  const passed = Object.entries(item.expected).every(([key, value]) => observed[key as keyof typeof observed] === value);
  assert(passed, `${item.id} did not match its expected decision log`);
  return { id: item.id, status: passed ? 'pass' : 'fail', expected: item.expected, decisionLog: observed };
});

const summary = {
  schema: 1,
  suite: 'topic3-b-runtime-contract-v1',
  status: cases.every(item => item.status === 'pass') ? 'pass' : 'fail',
  cases,
  bounds: {
    maxCandidates: 256,
    defaultSelectedK: 8,
    allowedSelectedK: [1, 32],
    defaultTimeoutMs: 30000,
    maxTimeoutMs: 30000,
    persistentWrites: false,
  },
  scope: 'Host-neutral temporary answer-feedback adapter; no Gateway hook, model call, memory mutation, or production traffic.',
};
await writeFile(output, JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify({ suite: summary.suite, status: summary.status, out: output }));
if (summary.status !== 'pass') process.exitCode = 1;
