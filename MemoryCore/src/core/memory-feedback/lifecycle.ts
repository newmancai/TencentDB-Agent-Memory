import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import type { IMemoryStore } from '../store/types.js';
import { writeMemory } from '../record/l1-writer.js';
import { executeMemorySearch, type MemorySearchResult } from '../tools/memory-search.js';

export type Relation = 'changed' | 'same' | 'unknown';

export interface Verification {
  candidateId: string;
  relation: Relation;
  evidenceId: string;
}

export interface PolicyState {
  schema: 1;
  signature: string;
  bins: { changed: number; same: number }[];
  seen: string[];
}

async function withTimeout<T>(
  work: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  message: string,
): Promise<T> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      Promise.resolve().then(() => work(controller.signal)),
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          controller.abort();
          reject(Error(message));
        }, timeoutMs);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

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
  try {
    validateCandidate(c, c.target.owner);
    const result = await withTimeout(
      signal => verifier(structuredClone(c), signal), timeoutMs, 'verification timeout',
    );
    if (result?.candidateId !== c.id || result.evidenceId !== c.source.sourceId
      || !['changed', 'same', 'unknown'].includes(result.relation)) throw Error('invalid verification');
    return { result, error: null };
  } catch (e) { return { result: null, error: String(e) }; }
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
    try {
      const head = await withTimeout(async () => {
        const h = await (options.load ? options.load() : this.load()) as Head;
        await this.check(h); return h;
      }, options.timeoutMs ?? 1000, 'lifecycle read timeout');
      const applied: string[] = [];
      const results = baseline.results.map(r => {
        const e = head.entries.find(e => e.candidate.target.recordId === r.id);
        if (!e) return r;
        applied.push(e.candidate.id);
        return { ...r, id: e.replacementId, version: 1, content: e.content };
      });
      return done({ ...baseline, results }, false, 'auxiliary', applied);
    } catch (e) { return done(baseline, true, String(e)); }
  }
}

/** Feedback predicts verification utility, not the truth of a remembered claim. */
export class FeedbackPolicy {
  private state: PolicyState;

  constructor(readonly signature: string, snapshot?: unknown) {
    if (!signature) throw Error('signature required');
    this.state = {
      schema: 1,
      signature,
      bins: Array.from({ length: 4 }, () => ({ changed: 0, same: 0 })),
      seen: [],
    };
    if (snapshot === undefined) return;
    const state = snapshot as PolicyState;
    const invalidBins = !Array.isArray(state?.bins) || state.bins.length !== 4
      || state.bins.some(bin => !bin
        || [bin.changed, bin.same].some(count => !Number.isInteger(count) || count < 0 || count > 1024));
    const invalidSeen = !Array.isArray(state?.seen) || state.seen.length > 4096
      || state.seen.some(id => typeof id !== 'string') || new Set(state.seen).size !== state.seen.length;
    if (state?.schema !== 1 || state.signature !== signature || invalidBins || invalidSeen) {
      throw Error('invalid feedback policy');
    }
    this.state = structuredClone(state);
  }

  private bin(score: number) {
    if (!Number.isFinite(score) || score < 0 || score > 1) throw Error('invalid proposal score');
    return Math.min(3, Math.floor(score * 4));
  }

  decide(score: number) {
    const bin = this.bin(score);
    const counts = this.state.bins[bin];
    const observations = counts.changed + counts.same;
    return {
      verify: observations < 3 || 4 * counts.changed >= observations,
      bin,
      observations,
      eChangedRate: observations ? counts.changed / observations : null,
    };
  }

  observe(candidateId: string, evidenceId: string, score: number, result: Verification) {
    const bin = this.bin(score);
    if (result.candidateId !== candidateId || result.evidenceId !== evidenceId
      || !['changed', 'same', 'unknown'].includes(result.relation)) throw Error('feedback identity mismatch');
    if (result.relation === 'unknown' || this.state.seen.includes(candidateId)) return;
    const counts = this.state.bins[bin];
    if (this.state.seen.length >= 4096 || counts[result.relation] >= 1024) return;
    counts[result.relation]++;
    this.state.seen.push(candidateId);
  }

  snapshot(): PolicyState {
    return structuredClone(this.state);
  }
}

/** Host entry point: useBaseline is mandatory for the subsequent read on failure/off. */
export async function processFeedback(p: {
  enabled: boolean;
  candidate: Candidate;
  memory: FeedbackMemory;
  verifier: (candidate: Candidate, signal: AbortSignal) => Promise<Verification>;
  score: () => Promise<number>;
  policy?: FeedbackPolicy;
  learn?: boolean;
  timeoutMs?: number;
  loadPolicy?: () => Promise<unknown>;
  policySignature?: string;
}) {
  const started = performance.now();
  const done = (status: string, useBaseline: boolean, detail?: unknown) => ({
    status, useBaseline, detail, elapsedMs: performance.now() - started,
  });
  if (!p.enabled) return done('off', true);
  const timeoutMs = p.timeoutMs ?? 30000;
  try {
    let policy = p.policy;
    if (p.loadPolicy) {
      const snapshot = await withTimeout(() => p.loadPolicy!(), timeoutMs, 'policy read timeout');
      policy = new FeedbackPolicy(p.policySignature ?? '', snapshot);
    }
    const score = await withTimeout(() => p.score(), timeoutMs, 'score timeout');
    if (!Number.isFinite(score) || score < 0 || score > 1) throw Error('invalid score');
    const decision = policy?.decide(score) ?? { verify: true };
    if (!p.learn && !decision.verify) return done('skipped', false, decision);
    const verified = await verifyBounded(p.candidate, p.verifier, timeoutMs);
    if (!verified.result) return done('fallback', true, verified.error);
    const status = await p.memory.publish(p.candidate, verified.result);
    if (p.learn && policy) {
      policy.observe(p.candidate.id, p.candidate.source.sourceId, score, verified.result);
    }
    return done(status, false, {
      decision,
      verification: verified.result,
      policy: policy?.snapshot(),
    });
  } catch (error) {
    return done('fallback', true, String(error));
  }
}
