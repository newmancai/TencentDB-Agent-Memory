/** Reuse prior native raw receipts to audit answer-object versus memory-cause binding. */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';

import { bindFeedbackTarget } from '../support/memory-feedback/index.js';

const [input, output] = process.argv.slice(2);
assert(input && output, 'usage: tsx native_reply_audit.ts NATIVE_RAW_SUMMARY OUTPUT_JSON');
const source = JSON.parse(await readFile(input, 'utf8')) as {
  events: number;
  receipts: { id: string; feedbackRecordId: string; responseRecordId: string }[];
};
const rows = source.receipts.map(receipt => {
  const binding = bindFeedbackTarget({
    candidateMemoryIds: [],
    outputIds: [receipt.responseRecordId],
    toolCallIds: [],
  }, { replyToOutputId: receipt.responseRecordId });
  return {
    id: receipt.id,
    feedbackRecordId: receipt.feedbackRecordId,
    responseRecordId: receipt.responseRecordId,
    answerBinding: binding,
    memoryCauseBinding: bindFeedbackTarget({
      candidateMemoryIds: [], outputIds: [receipt.responseRecordId], toolCallIds: [],
    }, {}),
  };
});
assert.equal(rows.length, source.events);
const summary = {
  protocol: 'topic3-b-native-reply-target-audit-v1',
  events: rows.length,
  answerObjectBound: rows.filter(row => row.answerBinding.status === 'bound').length,
  memoryCauseBound: rows.filter(row => row.memoryCauseBinding.status === 'bound').length,
  rows,
  scope: 'Host-carried reply adjacency binds the answer object only. Historical candidate memory sets are unavailable, so no memory cause is inferred and these are not replay learning samples.',
};
await writeFile(output, JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify({ events: summary.events, answerObjectBound: summary.answerObjectBound,
  memoryCauseBound: summary.memoryCauseBound, scope: summary.scope }));
