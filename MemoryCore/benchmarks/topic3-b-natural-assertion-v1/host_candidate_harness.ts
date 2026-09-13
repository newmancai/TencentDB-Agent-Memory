/** Replay pre-audited public follow-up outputs through the real candidate gate/store. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import {
  compileFeedbackAssertionCandidate,
  JsonlFeedbackTraceStore,
  observeFeedback,
  recordOutcome,
  selectMemoryAction,
  type FeedbackAssertionProposal,
} from '../../src/core/memory-feedback/index.js';

const [runDirectory, outputDirectory] = process.argv.slice(2);
assert(runDirectory && outputDirectory,
  'usage: tsx host_candidate_harness.ts PREAUDITED_RUN OUTPUT_DIRECTORY');
await mkdir(outputDirectory);

const readJsonl = async (path: string) => (await readFile(path, 'utf8'))
  .split('\n').filter(Boolean).map(line => JSON.parse(line));
const tasks = new Map((await readJsonl(join(runDirectory, 'tasks.private.jsonl')))
  .map(row => [row.case_id, row]));
const references = new Map((await readJsonl(join(runDirectory, 'reference.private.jsonl')))
  .map(row => [row.case_id, row]));
const receipts = await readJsonl(join(runDirectory, 'receipts.jsonl'));
const ledger = new JsonlFeedbackTraceStore(outputDirectory);
let tick = 0;
const timestamp = () => new Date(1789257600000 + tick++ * 1000).toISOString();
let candidates = 0;
let exact = 0;

for (const receipt of receipts) {
  const task = tasks.get(receipt.case_id);
  const reference = references.get(receipt.case_id);
  assert(task && reference);
  const answerId = `${receipt.case_id}:answer`;
  const sourceDecision = selectMemoryAction({
    id: `${receipt.case_id}:source-answer:decision`, contextId: `${receipt.case_id}:source`,
    taskId: `${receipt.case_id}:source-answer`, contextEventIds: [`${receipt.case_id}:prior-user`],
    candidateMemoryIds: [], action: 'omit', selectedMemoryIds: [],
    policyVersion: 'public-offpolicy-answer:v1', propensity: 1, decidedAt: timestamp(),
    promptMemorySpans: [], outputIds: [answerId], toolCallIds: [],
  });
  ledger.append(sourceDecision);
  const claim = observeFeedback({
    id: `${receipt.case_id}:feedback-claim`, decisionId: sourceDecision.id,
    observationType: reference.source_label === 'NEG_2' ? 'explicit_correction' : 'unknown',
    targetType: 'answer_span', targetIds: [answerId],
    claimText: task.visible.follow_up_user_message, scope: 'current interaction',
    authority: 'explicit_user', confidence: 1,
    sourceEventIds: [`${receipt.case_id}:follow-up`], observedAt: timestamp(),
  });
  ledger.append(claim);
  const extractionDecision = selectMemoryAction({
    id: `${receipt.case_id}:extractor:decision`, contextId: `${receipt.case_id}:feedback`,
    taskId: `${receipt.case_id}:candidate-extraction`,
    contextEventIds: [`${receipt.case_id}:answer`, `${receipt.case_id}:follow-up`],
    candidateMemoryIds: [], action: 'ask', selectedMemoryIds: [],
    policyVersion: 'codex-natural-assertion:v1', propensity: 1, decidedAt: timestamp(),
    promptMemorySpans: [], outputIds: [`${receipt.case_id}:extractor:output`], toolCallIds: [],
  });
  ledger.append(extractionDecision);
  const proposal = receipt.parsed as FeedbackAssertionProposal;
  const candidate = compileFeedbackAssertionCandidate(claim, proposal, {
    id: `${receipt.case_id}:candidate-assertion`, recordedAt: timestamp(),
  });
  if (candidate) {
    ledger.append(candidate);
    candidates += 1;
  }
  const actionCorrect = proposal.action === reference.expected_action;
  exact += Number(actionCorrect);
  ledger.append(recordOutcome({
    id: `${receipt.case_id}:extractor:outcome`, decisionId: extractionDecision.id,
    result: actionCorrect ? 'success' : 'failure', reward: actionCorrect ? 1 : 0,
    metrics: { actionCorrect, candidateCreated: candidate !== null },
    source: 'preaudited-action-and-runtime-candidate-gate', observedAt: timestamp(), delayed: false,
  }));
}

const restarted = new JsonlFeedbackTraceStore(outputDirectory);
const replay = restarted.replay();
assert(replay.ok);
assert.equal(receipts.length, 14);
assert.equal(exact, 14);
assert.equal(candidates, 2);
assert.equal(replay.learningSamples.length, 14);
const summary = {
  protocol: 'topic3-b-natural-assertion-host-candidate-v1',
  sourceCalls: receipts.length, exactActions: exact, candidateAssertions: candidates,
  restartReplay: replay,
  scope: 'Local development replay of public off-policy conversations and fixed Codex outputs through the real fail-closed candidate gate and JSONL store. No durable promotion, production write, or memory-cause claim.',
};
await writeFile(join(outputDirectory, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary));
