import { it, expect } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../store/sqlite.js';
import { ProjectMemory, type ConstraintProposal } from './project-memory.js';

const observation = (order: number, text: string) => ({ id: `user-${order}`, order, role: 'user' as const, text });
const proposal = (quote: string, path = 'src/api'): ConstraintProposal => ({
  key: 'timeout', quote, scope: { paths: [path], actions: ['edit'] },
});

it('preserves scoped updates, historical views, retractions, and source identity across SQLite restart', async () => {
  const root = await mkdtemp('/tmp/project-memory-test-');
  let store = new VectorStore(join(root, 'memory.sqlite'), 0); store.init();
  try {
    let memory = new ProjectMemory(store, 'alice', 'repo');
    const old = await memory.ingest(observation(1, 'Use a 10 second timeout.'), [proposal('Use a 10 second timeout.')]);
    await memory.ingest(observation(2, 'Keep a 20 second timeout in workers.'), [proposal('Keep a 20 second timeout in workers.', 'src/workers')]);
    const update = { ...proposal('Now use a 30 second timeout.'), supersedes: old.accepted[0].id };
    await memory.ingest(observation(3, update.quote), [update]);
    // Property ordering and canonical scope ordering do not change source identity.
    expect((await memory.ingest(observation(3, update.quote), [{ supersedes: update.supersedes,
      scope: update.scope, quote: update.quote, key: update.key }])).duplicate).toBe(true);
    store.close(); store = new VectorStore(join(root, 'memory.sqlite'), 0); store.init();
    memory = new ProjectMemory(store, 'alice', 'repo');
    const query = { paths: ['src/api/client.ts'], action: 'edit' as const, beforeOrder: 4 };
    const current = await memory.context(query);
    expect(current.text).toContain('30 second'); expect(current.text).not.toContain('10 second');
    expect((await memory.context({ ...query, beforeOrder: 3 })).text).toContain('10 second');
    expect((await memory.context({ ...query, paths: ['src/workers/run.ts'] })).text).toContain('20 second');
    expect((await memory.context({ ...query, paths: ['src'] })).selectedIds).toHaveLength(2);
    expect((await memory.context({ ...query, paths: ['.'] })).selectedIds).toHaveLength(2);
    expect((await memory.context({ ...query, paths: ['src/apiculture/a.ts'] })).text).toBe('');
    expect((await memory.context({ ...query, action: 'read' })).text).toBe('');
    expect((await new ProjectMemory(store, 'bob', 'repo').context(query)).text).toBe('');
    await memory.retract(current.selectedIds[0], observation(4, 'Withdraw the API timeout rule.'));
    expect((await memory.context({ ...query, beforeOrder: 5 })).text).toBe('');
    expect((await memory.context(query)).text).toContain('30 second');
    expect((await memory.snapshot()).observations).toHaveLength(4);
  } finally { store.close(); await rm(root, { recursive: true, force: true }); }
});

it('rejects unsupported writes atomically and exposes budget/store fallback without mutation', async () => {
  const root = await mkdtemp('/tmp/project-memory-test-');
  const store = new VectorStore(join(root, 'memory.sqlite'), 0); store.init();
  try {
    const memory = new ProjectMemory(store, 'u', 'p', 3);
    const first = await memory.ingest(observation(1, 'Use 10 seconds.'), [proposal('Use 10 seconds.')]);
    await expect(memory.ingest(observation(2, 'Use 20 seconds.'), [proposal('Use 20 seconds.')])).rejects.toThrow('predecessor');
    await expect(memory.ingest(observation(2, 'Use 20 seconds.'), [
      { ...proposal('Use 20 seconds.', 'src/workers'), supersedes: first.accepted[0].id },
    ])).rejects.toThrow('same-scope');
    await expect(memory.ingest(observation(2, 'A real quote.'), [proposal('A real quote.', 'src/workers'),
      proposal('Invented quote.', 'src/other')])).rejects.toThrow('source quote');
    await expect(memory.ingest({ ...observation(2, 'Use 20 seconds.'), role: 'tool' }, [proposal('Use 20 seconds.')])).rejects.toThrow('only user');
    await expect(memory.ingest(observation(2, 'Use 20 seconds.'), [proposal('Use 20 seconds.', '../escape')])).rejects.toThrow('scope');
    expect((await memory.snapshot()).revision).toBe(1);
    const [a,b] = await Promise.all([memory.ingest(observation(2, 'Unrelated text.'), []),
      memory.ingest(observation(3, 'No new rule.'), [])]);
    expect([a.revision,b.revision]).toEqual([2,3]);
    await expect(memory.ingest(observation(4, 'Another event.'), [])).rejects.toThrow('capacity');
    const query = { paths: ['src/api/client.ts'], action: 'edit' as const, beforeOrder: 4 };
    expect((await memory.context({ ...query, maxBytes: 1 })).omittedForBudget).toBe(1);
    expect((await memory.context({ ...query, paths: ['../escape'] })).status).toBe('fallback');
    store.close();
    expect((await memory.context({ ...query, enabled: false })).status).toBe('off');
    expect((await memory.context(query)).status).toBe('fallback');
  } finally { store.close(); await rm(root, { recursive: true, force: true }); }
});
