import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import assert from 'node:assert/strict';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { executeConversationSearch } from '../../src/core/tools/conversation-search.js';
import { parseAnswerFeedback, selectAnswerFeedback } from '../../src/core/memory-feedback/index.js';

const [input, predictionFile, output] = process.argv.slice(2);
const tasks = JSON.parse(await readFile(join(input, 'tasks.json'), 'utf8'));
const predictions = (await readFile(join(input, predictionFile), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
assert.equal(new Set(tasks.map((t: any) => t.id)).size, tasks.length);
assert.equal(new Set(predictions.map(p => p.id)).size, predictions.length);
assert.deepEqual(predictions.map(p => p.id).sort(), tasks.map((t: any) => t.id).sort());
await mkdir(output);
const receipts = [];
for (const task of tasks) {
  const store = new VectorStore(join(output, task.id.replaceAll(':', '-')+'.sqlite'), 0);
  store.init();
  try {
    assert(!store.isDegraded() && store.isFtsAvailable());
    for (const m of task.history) {
      assert(await store.upsertL0({ id: `${task.id}:turn${m.turn}`, sessionKey: task.id,
        sessionId: task.id, userId: task.id, agentId: 'answer-feedback-replay', role: 'user',
        messageText: m.user, recordedAt: new Date(1700000000000+m.turn).toISOString(),
        timestamp: 1700000000000+m.turn }));
    }
    const before = store.queryL0RecordsCursor('', 1000);
    assert.equal(before.length, task.history.length);
    const originals = new Map(before.map(r => [r.record_id, r.message_text]));
    const history = task.history.map((m: any) => {
      const recordId = `${task.id}:turn${m.turn}`;
      assert.equal(originals.get(recordId), m.user);
      return { turn: m.turn, user: originals.get(recordId), recordId };
    });
    const observation = { answerId: task.id, answer: task.answer, history,
      candidates: task.candidates.map((c: any) => ({ ...c, checkerPass: c.checker_pass })) };
    const search = () => executeConversationSearch({ query: task.history.at(-1).user,
      limit: 8, vectorStore: store, filter: { userId: task.id } });
    const recalledBefore = await search();
    const record = predictions.find((r: any) => r.id === task.id);
    assert(record);
    const arms: Record<string, unknown> = {};
    const baseline: readonly string[] = []; // This demonstration host has no pre-existing feedback.
    for (const [arm, value] of Object.entries(record.arms)) {
      const raw = value as any;
      const selected = await selectAnswerFeedback({ enabled: true, observation, baselineFeedback: baseline,
        selector: async () => parseAnswerFeedback(raw.text, raw.error === 'output_limit') });
      if (raw.prediction === null) assert(selected.useBaseline);
      else { assert(!selected.useBaseline); assert.deepEqual(selected.feedback, raw.prediction); }
      arms[arm] = selected;
    }
    const off = await selectAnswerFeedback({ enabled: false, observation, baselineFeedback: baseline,
      selector: async () => { throw Error('off called selector'); } });
    const failed = await selectAnswerFeedback({ enabled: true, observation, baselineFeedback: baseline,
      selector: async () => { throw Error('forced state read failure'); } });
    assert.strictEqual(off.feedback, baseline); assert.strictEqual(failed.feedback, baseline);
    assert.deepEqual(store.queryL0RecordsCursor('', 1000), before);
    // Search timing is observational; compare returned data, not elapsed clocks.
    assert.deepEqual((await search()).results, recalledBefore.results);
    receipts.push({ id: task.id, writes: before.length, records: history.map((m: any) => m.recordId),
      readbackEqual: true, recordsUnchanged: true, searchUnchanged: true,
      off: off.status, forcedFailure: failed.status, arms });
  } finally { store.close(); }
}
await writeFile(join(output, 'receipts.json'), JSON.stringify(receipts, null, 2));
console.log(JSON.stringify({ tasks: receipts.length, writes: receipts.reduce((s, r) => s+r.writes, 0),
  replayedArms: receipts.reduce((s, r) => s+Object.keys(r.arms).length, 0) }));
