/** Write the full public source prefix; form bounded candidates using native recall. */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { writeMemory } from '../../src/core/record/l1-writer.js';
import { executeMemorySearch } from '../../src/core/tools/memory-search.js';
import type { SourceRecord, Candidate } from '../../src/core/memory-feedback/index.js';

const [input, output] = process.argv.slice(2);
if (!input || !output) throw Error('prepare.ts tasks.json isolated-output');
const root = resolve(output); await mkdir(root, { recursive: true });
const tasks = JSON.parse(await readFile(input, 'utf8'));
const stop = new Set('a an the i me my we our you your it its this that these those is are was were be been being have has had do did does to of in on at for from with and or but as so if then than not now just really very can could would should will about'.split(' '));
const tokens = (s: string) => new Set((s.toLowerCase().match(/[a-z]{3,}/g) ?? []).filter(x => !stop.has(x)));
function sentences(s: string) {
  return (s.match(/[^.!?\n]+[.!?]?/g) ?? []).map(x => x.trim()).filter(x => x.length >= 30 && x.length <= 500
    && s.indexOf(x) === s.lastIndexOf(x));
}
const runs = [];
for (const t of tasks) {
  const directory = join(root, t.id); await mkdir(directory, { recursive: true });
  const store = new VectorStore(join(directory, 'base.sqlite'), 0); store.init();
  if (store.isDegraded()) throw Error('native SQLite unavailable');
  try {
    const sources = new Map<string, SourceRecord>();
    for (const [index, m] of t.messages.entries()) {
      const ok = await store.upsertL0({ id: `m${index}`, role: m.role, messageText: m.content,
        sessionKey: t.owner, sessionId: t.id, userId: t.owner, agentId: 'topic3-public',
        timestamp: 1700000000000 + index, recordedAt: new Date(1700000000000 + index).toISOString() }, undefined);
      if (!ok) throw Error('L0 write failed');
    }
    for (const s of t.sources) {
      const r = await writeMemory({ baseDir: directory, sessionKey: t.owner, sessionId: t.id,
        userId: t.owner, agentId: 'topic3-public', vectorStore: store,
        memory: { content: s.content, type: 'episodic', priority: 60, scene_name: 'source-text', source_message_ids: [s.sourceId], metadata: {} },
        decision: { record_id: `raw_${s.sourceId}`, action: 'store', target_ids: [] } });
      if (!r) throw Error('L1 source write failed');
      sources.set(r.id, { ...s, recordId: r.id, version: r.version });
    }
    const started = performance.now();
    const base = await executeMemorySearch({ query: t.query, limit: 12, vectorStore: store, filter: { userId: t.owner } });
    const evidence = base.results.map(r => sources.get(r.id)!);
    if (evidence.some(x => !x)) throw Error('unmapped recall');
    const pairs: (Candidate & { similarity: number })[] = [];
    for (const target of evidence) for (const source of evidence) {
      if (source.order <= target.order) continue;
      for (const oldQuote of sentences(target.content)) for (const newQuote of sentences(source.content)) {
        const a = tokens(oldQuote), b = tokens(newQuote), overlap = [...a].filter(x => b.has(x)).length;
        if (overlap < 2 || oldQuote === newQuote) continue;
        const similarity = overlap / new Set([...a, ...b]).size;
        const id = createHash('sha256').update(JSON.stringify([t.id, target.recordId, source.recordId, oldQuote, newQuote])).digest('hex').slice(0, 24);
        pairs.push({ id, target, source, oldQuote, newQuote, similarity });
      }
    }
    pairs.sort((a, b) => b.similarity - a.similarity || a.id.localeCompare(b.id));
    const candidates: Candidate[] = [], seen = new Set<string>();
    for (const p of pairs) {
      if (seen.has(p.target.recordId)) continue;
      seen.add(p.target.recordId); const { similarity: _, ...c } = p; candidates.push(c);
      if (candidates.length === 2) break;
    }
    runs.push({ id: t.id, owner: t.owner, split: t.split, query: t.query, options: t.options,
      directory, evidence, candidates, base, prepareMs: performance.now() - started,
      l0Count: t.messages.length, sourceCount: sources.size });
    console.log(JSON.stringify({ id: t.id, split: t.split, sources: sources.size, retrieved: evidence.length, candidates: candidates.length }));
  } finally { store.close(); }
}
await writeFile(join(root, 'prepared.json'), JSON.stringify(runs, null, 2));
await writeFile(join(root, 'candidate-audit.json'), JSON.stringify(runs.flatMap(t => t.candidates.map(c =>
  ({ task: t.id, split: t.split, id: c.id, old: c.oldQuote, later: c.newQuote, target: c.target.content, source: c.source.content }))), null, 2));
