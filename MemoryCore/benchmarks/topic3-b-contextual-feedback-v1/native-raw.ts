/** Isolated native L0 provenance roundtrip; no adaptive selection or E actions. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../../src/core/store/sqlite.js';
type Message = { evidence_id: string; role: 'user' | 'assistant'; content: string };
type Event = { id: string; group: string; prefix: Message[]; feedback_id: string; response_id: string };
const [input, output] = process.argv.slice(2);
const events: Event[] = (await readFile(input, 'utf8')).trim().split('\n').map(line => JSON.parse(line));
assert.equal(new Set(events.map(e => e.id)).size, events.length);
await mkdir(output);
const receipts = [];
for (const event of events) {
  const store = new VectorStore(join(output, `${event.id}.sqlite`), 0);
  store.init();
  try {
    assert(!store.isDegraded() && store.isFtsAvailable());
    assert.equal(new Set(event.prefix.map(m => m.evidence_id)).size, event.prefix.length);
    for (const [turn, message] of event.prefix.entries()) {
      assert(await store.upsertL0({ id: `${event.id}:${message.evidence_id}`,
        sessionKey: event.id, sessionId: event.id, userId: event.group,
        agentId: 'cupid-raw-feedback-roundtrip', role: message.role,
        messageText: message.content, timestamp: 1700000000000 + turn,
        recordedAt: new Date(1700000000000 + turn).toISOString() }));
    }
    const before = store.queryL0RecordsCursor('', 1000);
    assert.equal(before.length, event.prefix.length);
    const byId = new Map(before.map(record => [record.record_id, record]));
    const restored = event.prefix.map(message => {
      const recordId = `${event.id}:${message.evidence_id}`;
      const record = byId.get(recordId);
      assert(record);
      assert.equal(record.message_text, message.content);
      assert.equal(record.role, message.role);
      assert.equal(record.session_id, event.id);
      return { recordId, role: record.role, content: record.message_text };
    });
    const feedback = restored.at(-1)!;
    const response = restored.at(-2)!;
    assert.equal(feedback.recordId, `${event.id}:${event.feedback_id}`);
    assert.equal(response.recordId, `${event.id}:${event.response_id}`);
    assert.equal(feedback.role, 'user');
    assert.equal(response.role, 'assistant');
    assert.deepEqual(store.queryL0RecordsCursor('', 1000), before);
    receipts.push({ id: event.id, writes: before.length, textRoleSessionEqual: true,
      feedbackRecordId: feedback.recordId, responseRecordId: response.recordId,
      readsUnchanged: true });
  } finally { store.close(); }
}
const summary = { mode: 'native_raw_provenance_roundtrip', events: receipts.length,
  writes: receipts.reduce((n, r) => n + r.writes, 0), receipts,
  scope: 'Real isolated L0 write/read. Host carries observed reply order; not a persisted reply-to schema, '
    + 'retrieval ranking test, adaptive off/fallback test, semantic truth, or feedback-learning gain.' };
await writeFile(join(output, 'native-raw-summary.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify({ events: summary.events, writes: summary.writes, scope: summary.scope }));
