import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../store/sqlite.js';
import { ProjectMemory, type ConstraintProposal } from './project-memory.js';

const observation = (order: number, text: string) => ({
  id: `user-${order}`,
  order,
  role: 'user' as const,
  text,
});
const proposal = (quote: string, path = 'src/api'): ConstraintProposal => ({
  key: 'timeout',
  quote,
  scope: { paths: [path], actions: ['edit'] },
});

it('preserves scoped updates, historical views, retractions, and source identity across SQLite restart', async () => {
  const root = await mkdtemp('/tmp/project-memory-test-');
  let store = new VectorStore(join(root, 'memory.sqlite'), 0);
  store.init();
  try {
    let memory = new ProjectMemory(store, 'alice', 'repo');
    const old = await memory.ingest(observation(1, 'Use a 10 second timeout.'), [
      proposal('Use a 10 second timeout.'),
    ]);
    await memory.ingest(observation(2, 'Keep a 20 second timeout in workers.'), [
      proposal('Keep a 20 second timeout in workers.', 'src/workers'),
    ]);
    const update = { ...proposal('Now use a 30 second timeout.'), supersedes: old.accepted[0].id };
    await memory.ingest(observation(3, update.quote), [update]);
    // Property ordering and canonical scope ordering do not change source identity.
    expect(
      (
        await memory.ingest(observation(3, update.quote), [
          {
            supersedes: update.supersedes,
            scope: update.scope,
            quote: update.quote,
            key: update.key,
          },
        ])
      ).duplicate,
    ).toBe(true);
    store.close();
    store = new VectorStore(join(root, 'memory.sqlite'), 0);
    store.init();
    memory = new ProjectMemory(store, 'alice', 'repo');
    const query = { paths: ['src/api/client.ts'], action: 'edit' as const, beforeOrder: 4 };
    const current = await memory.context(query);
    const currentRule = JSON.parse(current.text);
    expect(currentRule.userQuote).toContain('30 second');
    expect(currentRule.userQuote).not.toContain('10 second');
    expect(currentRule.predecessorEvidence[0]).toMatchObject({
      status: 'historical',
      userQuote: 'Use a 10 second timeout.',
    });
    const snapshotRead = vi.spyOn(memory, 'snapshot');
    const loaded = await memory.loadContext({ paths: query.paths, action: query.action });
    expect(snapshotRead).toHaveBeenCalledTimes(1);
    expect(loaded.snapshot.revision).toBe(3);
    expect(loaded.selection).toEqual(current);
    snapshotRead.mockRestore();
    expect((await memory.context({ ...query, beforeOrder: 3 })).text).toContain('10 second');
    expect((await memory.context({ ...query, paths: ['src/workers/run.ts'] })).text).toContain(
      '20 second',
    );
    expect((await memory.context({ ...query, paths: ['src'] })).selectedIds).toHaveLength(2);
    expect((await memory.context({ ...query, paths: ['.'] })).selectedIds).toHaveLength(2);
    expect((await memory.context({ ...query, paths: ['src/apiculture/a.ts'] })).text).toBe('');
    expect((await memory.context({ ...query, action: 'read' })).text).toBe('');
    expect((await new ProjectMemory(store, 'bob', 'repo').context(query)).text).toBe('');
    await memory.retract(current.selectedIds[0], observation(4, 'Withdraw the API timeout rule.'));
    expect((await memory.context({ ...query, beforeOrder: 5 })).text).toBe('');
    expect((await memory.context(query)).text).toContain('30 second');
    expect((await memory.snapshot()).observations).toHaveLength(4);
  } finally {
    store.close();
    await rm(root, { recursive: true, force: true });
  }
});

it('keeps unchanged clauses available through a chain without reactivating superseded rules', async () => {
  const root = await mkdtemp('/tmp/project-memory-lineage-');
  const store = new VectorStore(join(root, 'memory.sqlite'), 0);
  store.init();
  try {
    const memory = new ProjectMemory(store, 'u', 'p');
    const original = 'Use 3 retries and retain cancellation support.';
    const first = await memory.ingest(observation(1, original), [proposal(original)]);
    const second = await memory.ingest(
      observation(2, 'Use 1 retry; everything else stays unchanged.'),
      [
        {
          ...proposal('Use 1 retry; everything else stays unchanged.'),
          supersedes: first.accepted[0].id,
        },
      ],
    );
    await memory.ingest(observation(3, 'Use 0 retries; everything else stays unchanged.'), [
      {
        ...proposal('Use 0 retries; everything else stays unchanged.'),
        supersedes: second.accepted[0].id,
      },
    ]);
    const query = { paths: ['src/api'], action: 'edit' as const, beforeOrder: 4 };
    const view = await memory.context(query);
    const rule = JSON.parse(view.text);
    expect(view.selectedIds).toHaveLength(1);
    expect(rule.userQuote).toContain('0 retries');
    expect(rule.predecessorEvidence.map((item: { order: number }) => item.order)).toEqual([1, 2]);
    expect(rule.predecessorEvidence[0].userQuote).toContain('cancellation support');
    const old = JSON.parse((await memory.context({ ...query, beforeOrder: 3 })).text);
    expect(old.userQuote).toContain('1 retry');
    expect(old.predecessorEvidence).toHaveLength(1);
    // An over-budget family is omitted as a whole; the host falls back to raw history.
    const limited = await memory.context({ ...query, maxBytes: Buffer.byteLength(view.text) - 1 });
    expect(limited.text).toBe('');
    expect(limited.omittedForBudget).toBe(1);
    await memory.ingest(observation(4, 'Keep logging.'), [
      { ...proposal('Keep logging.'), key: 'logs' },
    ]);
    const broken = await memory.snapshot();
    broken.constraints.find((item) => item.order === 3)!.supersedes = 'missing';
    vi.spyOn(memory, 'snapshot').mockResolvedValueOnce(broken);
    const fallback = await memory.context({ ...query, beforeOrder: 5 });
    expect(fallback.status).toBe('fallback');
    expect(fallback.text).toBe('');
    expect(fallback.selectedIds).toEqual([]);
  } finally {
    store.close();
    await rm(root, { recursive: true, force: true });
  }
});

it('rejects unsupported writes atomically and exposes budget/store fallback without mutation', async () => {
  const root = await mkdtemp('/tmp/project-memory-test-');
  const store = new VectorStore(join(root, 'memory.sqlite'), 0);
  store.init();
  try {
    const memory = new ProjectMemory(store, 'u', 'p', 3);
    const first = await memory.ingest(observation(1, 'Use 10 seconds.'), [
      proposal('Use 10 seconds.'),
    ]);
    await expect(
      memory.ingest(observation(2, 'Use 20 seconds.'), [proposal('Use 20 seconds.')]),
    ).rejects.toThrow('predecessor');
    await expect(
      memory.ingest(observation(2, 'Use 20 seconds.'), [
        { ...proposal('Use 20 seconds.', 'src/workers'), supersedes: first.accepted[0].id },
      ]),
    ).rejects.toThrow('same-scope');
    await expect(
      memory.ingest(observation(2, 'A real quote.'), [
        proposal('A real quote.', 'src/workers'),
        proposal('Invented quote.', 'src/other'),
      ]),
    ).rejects.toThrow('source quote');
    await expect(
      memory.ingest({ ...observation(2, 'Use 20 seconds.'), role: 'tool' }, [
        proposal('Use 20 seconds.'),
      ]),
    ).rejects.toThrow('only user');
    await expect(
      memory.ingest(observation(2, 'Use 20 seconds.'), [proposal('Use 20 seconds.', '../escape')]),
    ).rejects.toThrow('scope');
    expect((await memory.snapshot()).revision).toBe(1);
    const [a, b] = await Promise.all([
      memory.ingest(observation(2, 'Unrelated text.'), []),
      memory.ingest(observation(3, 'No new rule.'), []),
    ]);
    expect([a.revision, b.revision]).toEqual([2, 3]);
    await expect(memory.ingest(observation(4, 'Another event.'), [])).rejects.toThrow('capacity');
    const query = { paths: ['src/api/client.ts'], action: 'edit' as const, beforeOrder: 4 };
    expect((await memory.context({ ...query, maxBytes: 1 })).omittedForBudget).toBe(1);
    await expect(memory.context({ ...query, paths: ['../escape'] })).rejects.toThrow(
      'invalid context query',
    );
    await expect(memory.context({ ...query, maxBytes: 0 })).rejects.toThrow(
      'invalid context budget',
    );
    store.close();
    expect((await memory.context({ ...query, enabled: false })).status).toBe('off');
    expect((await memory.context(query)).status).toBe('fallback');
  } finally {
    store.close();
    await rm(root, { recursive: true, force: true });
  }
});
