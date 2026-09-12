import { FeedbackMemory, verifyBounded, type Candidate } from './lifecycle.js';
import { FeedbackPolicy, type Verification } from './policy.js';

/** Host entry point: useBaseline is mandatory for the subsequent read on failure/off. */
export async function processFeedback(p: {
  enabled: boolean; candidate: Candidate; memory: FeedbackMemory;
  verifier: (candidate: Candidate, signal: AbortSignal) => Promise<Verification>;
  score: () => Promise<number>; policy?: FeedbackPolicy; learn?: boolean; timeoutMs?: number;
  loadPolicy?: () => Promise<unknown>; policySignature?: string;
}) {
  const start = performance.now();
  const done = (status: string, useBaseline: boolean, detail?: unknown) =>
    ({ status, useBaseline, detail, elapsedMs: performance.now() - start });
  if (!p.enabled) return done('off', true);
  try {
    let policy = p.policy;
    if (p.loadPolicy) {
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        const snapshot = await Promise.race([p.loadPolicy(), new Promise<never>((_, reject) => {
          timer = setTimeout(() => reject(Error('policy read timeout')), p.timeoutMs ?? 30000);
        })]);
        policy = new FeedbackPolicy(p.policySignature ?? '', snapshot);
      } finally { if (timer) clearTimeout(timer); }
    }
    // Score providers must obey the same bounded asynchronous contract as E.
    let timer: ReturnType<typeof setTimeout> | undefined;
    let score: number;
    try {
      score = await Promise.race([p.score(), new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(Error('score timeout')), p.timeoutMs ?? 30000);
      })]);
    } finally { if (timer) clearTimeout(timer); }
    if (!Number.isFinite(score) || score < 0 || score > 1) throw Error('invalid score');
    const decision = policy?.decide(score) ?? { verify: true };
    if (!p.learn && !decision.verify) return done('skipped', false, decision);
    const verified = await verifyBounded(p.candidate, p.verifier, p.timeoutMs);
    if (!verified.result) return done('fallback', true, verified.error);
    const status = await p.memory.publish(p.candidate, verified.result);
    if (p.learn && policy) policy.observe(p.candidate.id, p.candidate.source.sourceId, score, verified.result);
    return done(status, false, { decision, verification: verified.result, policy: policy?.snapshot() });
  } catch (e) { return done('fallback', true, String(e)); }
}
