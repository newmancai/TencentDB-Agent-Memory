/** Candidate-pool qualification: query only past native records before writing. */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { writeMemory } from '../../src/core/record/l1-writer.js';
import { executeMemorySearch } from '../../src/core/tools/memory-search.js';

const [input, out] = process.argv.slice(2);
if (!input || !out) throw Error('incoming.ts tasks.json new-isolated-output');
await mkdir(out, { recursive: true });
const tasks = JSON.parse(await readFile(input, 'utf8'));
const results = [];
for (const t of tasks) {
  const dir = join(out, t.id); await mkdir(dir); // fresh native state, no silent rerun
  const db = new VectorStore(join(dir, 'base.sqlite'), 0); db.init();
  if (db.isDegraded()) throw Error('native SQLite unavailable');
  const rows = new Map<string, any>(), events = [];
  const started = performance.now();
  try {
    for (const m of t.messages) {
      const ok = await db.upsertL0({ id: m.id, role: m.role, messageText: m.content,
        userId: t.id, sessionKey: t.id, sessionId: m.session, agentId: 'topic3-v2',
        timestamp: 1700000000000 + m.order, recordedAt: new Date(1700000000000 + m.order).toISOString() }, undefined);
      if (!ok) throw Error('L0 write failed');
      for (const source of t.sources.filter((s: any) => s.parent === m.id)) {
        const start = performance.now();
        const excludedRecordIds = [...rows.entries()].filter(([, p]) => p.parent === source.parent).map(([id]) => id);
        const found = await executeMemorySearch({ query: source.content, limit: 8, vectorStore: db,
          excludedRecordIds, filter: { userId: t.id } });
        const past = found.results.map(r => rows.get(r.id));
        if (past.some(p => !p || p.order >= source.order)) throw Error('non-past native result');
        events.push({ source: source.sourceId, parent: source.parent, order: source.order,
          candidates: past.map(p => ({ source: p.sourceId, parent: p.parent, order: p.order, session: p.session })),
          elapsedMs: performance.now() - start });
        const record = await writeMemory({ baseDir: dir, sessionKey: t.id, sessionId: source.session,
          userId: t.id, agentId: 'topic3-v2', vectorStore: db,
          memory: { content: source.content, type: 'episodic', priority: 60, scene_name: 'source-text', source_message_ids: [source.sourceId], metadata: {} },
          decision: { record_id: 'raw_' + source.sourceId, action: 'store', target_ids: [] } });
        if (!record) throw Error('L1 write failed');
        rows.set(record.id, { ...source, recordId: record.id });
      }
    }
    const native = await executeMemorySearch({ query: t.query, limit: 12, vectorStore: db, filter: { userId: t.id } });
    results.push({ id: t.id, directory: dir, events, native: native.results.map(r => rows.get(r.id)),
      l0: t.messages.length, l1: rows.size, elapsedMs: performance.now() - started });
    console.log(JSON.stringify({ id: t.id, events: events.length, milliseconds: performance.now() - started }));
  } finally { db.close(); }
}
await writeFile(join(out, 'results.json'), JSON.stringify(results));
