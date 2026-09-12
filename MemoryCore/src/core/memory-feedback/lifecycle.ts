import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import type { IMemoryStore } from '../store/types.js';
import { writeMemory } from '../record/l1-writer.js';
import { executeMemorySearch, type MemorySearchResult } from '../tools/memory-search.js';
import type { Verification } from './policy.js';

export interface SourceRecord {
  recordId: string; version: number; owner: string; sourceId: string; order: number; content: string;
}
export interface Candidate {
  id: string; target: SourceRecord; source: SourceRecord; oldQuote: string; newQuote: string;
}
interface Entry { candidate: Candidate; replacementId: string; content: string }
interface Head { schema: 1; owner: string; entries: Entry[] }
const hash = (s: string) => createHash('sha256').update(s).digest('hex');
const unique = (s: string, q: string) => !!q && s.indexOf(q) >= 0 && s.indexOf(q) === s.lastIndexOf(q);
export function validateCandidate(c: Candidate, owner: string) {
  if (!c || typeof c.id !== 'string' || !c.id || !c.target || !c.source || c.target.owner !== owner
    || c.source.owner !== owner || !Number.isInteger(c.target.version) || c.target.version < 1
    || [c.target.recordId, c.source.recordId, c.target.sourceId, c.source.sourceId].some(id => typeof id !== 'string' || !id)
    || c.target.recordId === c.source.recordId
    || !Number.isInteger(c.source.version) || c.source.version < 1
    || !Number.isFinite(c.target.order) || !Number.isFinite(c.source.order) || c.source.order <= c.target.order
    || typeof c.target.content !== 'string' || typeof c.source.content !== 'string'
    || c.target.content.length > 16000 || c.source.content.length > 16000
    || typeof c.oldQuote !== 'string' || typeof c.newQuote !== 'string'
    || !unique(c.target.content, c.oldQuote) || !unique(c.source.content, c.newQuote)) throw Error('invalid evidence identity/span');
}
export function replacementContent(c: Candidate) {
  return c.target.content.replace(c.oldQuote, () =>
    `[Historical statement: ${c.oldQuote}] [Later evidence (${c.source.sourceId}): ${c.newQuote}]`);
}
/** A timed-out reviewer cannot mutate memory: it receives evidence and an abort signal only. */
export async function verifyBounded(c: Candidate, verifier: (c: Candidate, signal: AbortSignal) => Promise<Verification>, timeoutMs = 30000) {
  const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    validateCandidate(c, c.target.owner);
    const result = await Promise.race([verifier(structuredClone(c), controller.signal), new Promise<never>((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(Error('verification timeout')); }, timeoutMs);
    })]);
    if (result?.candidateId !== c.id || result.evidenceId !== c.source.sourceId
      || !['changed', 'same', 'unknown'].includes(result.relation)) throw Error('invalid verification');
    return { result, error: null };
  } catch (e) { return { result: null, error: String(e) }; }
  finally { if (timer) clearTimeout(timer); }
}

/** Optional single-writer sidecar. Base indexing, ranking and originals remain native. */
export class FeedbackMemory {
  private queue: Promise<unknown> = Promise.resolve();
  constructor(readonly owner: string, readonly root: string, readonly base: IMemoryStore,
    readonly auxiliary: IMemoryStore, readonly capacity = 128) {
    if (!owner || base === auxiliary || !Number.isInteger(capacity) || capacity < 1 || capacity > 2048) throw Error('invalid sidecar configuration');
  }
  private async load(): Promise<Head> {
    try { return JSON.parse(await readFile(join(this.root, 'head.json'), 'utf8')); }
    catch (e: any) { if (e.code === 'ENOENT') return { schema: 1, owner: this.owner, entries: [] }; throw e; }
  }
  private async check(h: Head) {
    if (h?.schema !== 1 || h.owner !== this.owner || !Array.isArray(h.entries) || h.entries.length > this.capacity) throw Error('invalid lifecycle state');
    if (this.base.isDegraded() || this.auxiliary.isDegraded()) throw Error('store unavailable');
    const targets = new Set<string>();
    for (const e of h.entries) {
      validateCandidate(e.candidate, this.owner);
      const c = e.candidate;
      if (targets.has(c.target.recordId) || e.content !== replacementContent(c)
        || e.replacementId !== `be_${hash(JSON.stringify(c))}`) throw Error('corrupt lifecycle entry');
      targets.add(c.target.recordId);
      await this.checkSource(c.target); await this.checkSource(c.source);
      const rows = await this.auxiliary.queryL1Records({ recordIds: [e.replacementId], userId: this.owner });
      if (rows.length !== 1 || rows[0].version !== 1 || rows[0].content !== e.content) throw Error('replacement readback failed');
    }
  }
  private async checkSource(s: SourceRecord) {
    const rows = await this.base.queryL1Records({ recordIds: [s.recordId], userId: this.owner });
    if (rows.length !== 1 || rows[0].version !== s.version || rows[0].content !== s.content) throw Error('stale or missing source');
  }
  async publish(c: Candidate, v: Verification) {
    const run = this.queue.then(async () => {
      validateCandidate(c, this.owner);
      if (v.candidateId !== c.id || v.evidenceId !== c.source.sourceId
        || !['changed', 'same', 'unknown'].includes(v.relation)) throw Error('verification identity mismatch');
      if (v.relation !== 'changed') return 'unchanged';
      const head = await this.load(); await this.check(head);
      const existing = head.entries.find(e => e.candidate.target.recordId === c.target.recordId);
      if (existing) {
        if (JSON.stringify(existing.candidate) === JSON.stringify(c)) return 'duplicate';
        if (existing.candidate.source.order >= c.source.order) return 'obsolete';
      }
      const history = await this.auxiliary.queryL1Records({ userId: this.owner });
      if (history.length >= this.capacity) throw Error('lifecycle history capacity');
      await this.checkSource(c.target); await this.checkSource(c.source);
      const content = replacementContent(c), replacementId = `be_${hash(JSON.stringify(c))}`;
      const record = await writeMemory({ baseDir: this.root, sessionKey: this.owner, sessionId: c.id,
        userId: this.owner, agentId: 'memory-feedback', vectorStore: this.auxiliary,
        memory: { content, type: 'episodic', priority: 60, scene_name: 'feedback-view',
          source_message_ids: [c.target.sourceId, c.source.sourceId], metadata: {} },
        decision: { record_id: replacementId, action: 'store', target_ids: [] } });
      if (!record || record.version !== 1) throw Error('replacement persistence failed');
      const next: Head = { ...head, entries: [...head.entries.filter(e => e.candidate.target.recordId !== c.target.recordId), { candidate: c, replacementId, content }] };
      await this.check(next);
      await mkdir(this.root, { recursive: true });
      const temp = join(this.root, `head-${randomUUID()}.tmp`);
      await writeFile(temp, JSON.stringify(next)); await rename(temp, join(this.root, 'head.json'));
      return 'published';
    });
    this.queue = run.catch(() => {}); return run;
  }
  async search(query: string, options: { enabled: boolean; limit?: number; timeoutMs?: number; load?: () => Promise<unknown> }) {
    const started = performance.now();
    const baseline = await executeMemorySearch({ query, limit: options.limit ?? 12, vectorStore: this.base, filter: { userId: this.owner } });
    const done = (result: MemorySearchResult, fallback: boolean, reason: string, applied: string[] = []) =>
      ({ result, fallback, reason, applied, elapsedMs: performance.now() - started });
    if (!options.enabled) return done(baseline, false, 'off');
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const head = await Promise.race([(async () => {
        const h = await (options.load ? options.load() : this.load()) as Head;
        await this.check(h); return h;
      })(), new Promise<never>((_, reject) => { timer = setTimeout(() => reject(Error('lifecycle read timeout')), options.timeoutMs ?? 1000); })]);
      const applied: string[] = [];
      const results = baseline.results.map(r => {
        const e = head.entries.find(e => e.candidate.target.recordId === r.id);
        if (!e) return r;
        applied.push(e.candidate.id);
        return { ...r, id: e.replacementId, version: 1, content: e.content };
      });
      return done({ ...baseline, results }, false, 'auxiliary', applied);
    } catch (e) { return done(baseline, true, String(e)); }
    finally { if (timer) clearTimeout(timer); }
  }
}
