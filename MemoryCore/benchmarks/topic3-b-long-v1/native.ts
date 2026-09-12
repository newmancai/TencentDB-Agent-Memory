import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { executeConversationSearch } from '../../src/core/tools/conversation-search.js';

const [input, output] = process.argv.slice(2);
const tasks = JSON.parse(await readFile(input, 'utf8'));
await mkdir(output);
const results = [];
for (const task of tasks) {
  const directory = join(output, task.id); await mkdir(directory);
  const store = new VectorStore(join(directory, 'base.sqlite'), 0); store.init();
  try {
    if (store.isDegraded() || !store.isFtsAvailable()) throw Error('native FTS unavailable');
    for (const m of task.messages) {
      if (m.order >= task.incoming.order) throw Error('future input');
      const ok = await store.upsertL0({ id: m.id, sessionKey: task.id, sessionId: task.id,
        userId: task.id, agentId: 'topic3-b-long-v1', role: 'user', messageText: m.content,
        recordedAt: new Date(1700000000000 + m.order).toISOString(), timestamp: 1700000000000 + m.order });
      if (!ok) throw Error('native write failed');
    }
    const start = performance.now();
    const recalled = await executeConversationSearch({ query: task.incoming.content, limit: 8,
      vectorStore: store, filter: { userId: task.id } });
    const originals = new Map(task.messages.map((m: any) => [m.id, m.content]));
    for (const r of recalled.results) if (originals.get(r.id) !== r.content) throw Error('readback mismatch');
    results.push({ id: task.id, writes: task.messages.length,
      fts: { ...recalled, elapsedMs: performance.now() - start },
      recent: { results: task.messages.slice(-8).map((m: any) => ({id: m.id, content: m.content})),
        provenance: 'last eight of successfully written corpus; not separately timed database query' } });
  } finally { store.close(); }
  console.log(JSON.stringify({ done: results.length, total: tasks.length }));
}
await writeFile(join(output,'results.json'),JSON.stringify(results));
