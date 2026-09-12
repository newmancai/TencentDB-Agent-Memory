import { it, expect } from 'vitest';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../store/sqlite.js';
import { writeMemory } from '../record/l1-writer.js';
import { FeedbackMemory, verifyBounded, replacementContent, type Candidate } from './lifecycle.js';
import { FeedbackPolicy } from './policy.js';
import { processFeedback } from './process.js';

it('persists only the selected span and falls back to exact native base through failure/restart', async () => {
  const root = await mkdtemp('/tmp/topic3-test-');
  const base = new VectorStore(join(root, 'base.sqlite'), 0), aux = new VectorStore(join(root, 'aux.sqlite'), 0);
  base.init(); aux.init();
  try {
    const put = async (id: string, content: string) => {
      await writeMemory({ baseDir: root, sessionKey: 'u', sessionId: 's', userId: 'u', agentId: 'test', vectorStore: base,
        memory: { content, type: 'episodic', priority: 60, scene_name: 'test', source_message_ids: [id], metadata: {} },
        decision: { record_id: id, action: 'store', target_ids: [] } });
      return { recordId: id, sourceId: id, content, version: 1, owner: 'u', order: id === 'old' ? 1 : 2 };
    };
    const target = await put('old', 'Project port is 8080. Keep the deployment region west.'),
      source = await put('new', 'Project port is now 9090, replacing 8080.');
    const c: Candidate = { id: 'c1', target, source, oldQuote: 'Project port is 8080.', newQuote: source.content };
    const v = { candidateId: c.id, evidenceId: source.sourceId, relation: 'changed' as const };
    const memory = new FeedbackMemory('u', join(root, 'sidecar'), base, aux, 1);
    const ordinary = await memory.search('Project port', { enabled: false, load: async () => { throw Error('must bypass'); } });
    expect(await memory.publish(c, { ...v, relation: 'unknown' })).toBe('unchanged');
    expect(await memory.publish(c, v)).toBe('published');
    expect(await memory.publish(c, v)).toBe('duplicate');
    const forbid = async () => { throw Error('must not be called'); };
    expect((await processFeedback({ enabled: false, candidate: c, memory, score: forbid, verifier: forbid })).status).toBe('off');
    expect((await processFeedback({ enabled: true, candidate: c, memory, score: async () => .5, verifier: forbid })).useBaseline).toBe(true);
    expect((await processFeedback({ enabled: true, candidate: c, memory, score: async () => NaN, verifier: forbid })).useBaseline).toBe(true);
    for (const loadPolicy of [async () => ({ schema: 99 }), async () => { throw Error('policy read failed'); }, () => new Promise(() => {})]) {
      expect((await processFeedback({ enabled: true, candidate: c, memory, score: forbid, verifier: forbid,
        loadPolicy, policySignature: 'v1', timeoutMs: 5 })).useBaseline).toBe(true);
    }
    const reopened = new FeedbackMemory('u', join(root, 'sidecar'), base, aux, 1);
    const updated = await reopened.search('Project port', { enabled: true });
    expect(updated.fallback).toBe(false); expect(updated.applied).toEqual(['c1']);
    expect(updated.result.results.find(r => r.id !== 'new')?.content).toBe(replacementContent(c));
    expect(replacementContent(c)).toContain('Keep the deployment region west.');
    const literal = { ...c, oldQuote: '$&', newQuote: "$'", target: { ...target, content: 'Keep $& and suffix.' } };
    expect(replacementContent(literal)).toBe("Keep [Historical statement: $&] [Later evidence (new): $'] and suffix.");
    expect(base.queryL1Records({ recordIds: ['old'] })[0].content).toBe(target.content);
    const head = JSON.parse(await readFile(join(root, 'sidecar/head.json'), 'utf8'));
    for (const load of [async () => { throw Error('read failure'); }, async () => ({ schema: 2 }),
      async () => ({ ...head, owner: 'other' }), async () => ({ ...head, entries: [{ ...head.entries[0], content: 'tampered' }] }),
      async () => { const h = structuredClone(head); h.entries[0].candidate.target.version = 2; return h; },
      () => new Promise(() => {})]) {
      const r = await reopened.search('Project port', { enabled: true, load, timeoutMs: 5 });
      expect(r.fallback).toBe(true); expect(r.result).toEqual(ordinary.result);
    }
    const late = await verifyBounded(c, async () => { await new Promise(r => setTimeout(r, 20)); return v; }, 1);
    expect(late.result).toBeNull();
    expect(await readFile(join(root, 'sidecar/head.json'), 'utf8')).toBe(JSON.stringify(head));
    await expect(memory.publish({ ...c, id: 'other', target: { ...target, owner: 'foreign' } }, v)).rejects.toThrow();
    const newer = await put('newest', 'Project port is now 7070.'); newer.order = 3;
    const c2 = { ...c, id: 'c2', source: newer, newQuote: newer.content };
    await expect(memory.publish(c2, { ...v, candidateId: 'c2', evidenceId: 'newest' })).rejects.toThrow('capacity');
    const larger = new FeedbackMemory('u', join(root, 'sidecar'), base, aux, 2);
    expect(await larger.publish(c2, { ...v, candidateId: 'c2', evidenceId: 'newest' })).toBe('published');
    expect(await larger.publish(c, v)).toBe('obsolete');
    expect((await larger.search('Project port', { enabled: true })).applied).toEqual(['c2']);
    expect(aux.queryL1Records()).toHaveLength(2);
  } finally { base.close(); aux.close(); await rm(root, { recursive: true, force: true }); }
});

it('learns only attributable non-unknown verification, deduplicates, and restores bounded versioned policy', () => {
  const p = new FeedbackPolicy('source:v1/verifier:v1');
  expect(p.decide(.1).verify).toBe(true);
  p.observe('unknown', 's', .1, { candidateId: 'unknown', evidenceId: 's', relation: 'unknown' });
  expect(p.decide(.1).observations).toBe(0);
  for (let i = 0; i < 3; i++) p.observe(String(i), 's', .1, { candidateId: String(i), evidenceId: 's', relation: 'same' });
  expect(p.decide(.1).verify).toBe(false); expect(p.decide(.9).verify).toBe(true);
  p.observe('0', 's', .1, { candidateId: '0', evidenceId: 's', relation: 'changed' });
  expect(p.decide(.1).observations).toBe(3);
  expect(new FeedbackPolicy(p.signature, p.snapshot()).decide(.1)).toEqual(p.decide(.1));
  expect(() => new FeedbackPolicy('v2', p.snapshot())).toThrow();
  expect(() => p.observe('wrong', 's', .1, { candidateId: 'other', evidenceId: 's', relation: 'same' })).toThrow();
});
