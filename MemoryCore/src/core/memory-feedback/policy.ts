/** Feedback predicts verification utility, not the truth of a remembered claim. */
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
export class FeedbackPolicy {
  private state: PolicyState;
  constructor(readonly signature: string, snapshot?: unknown) {
    if (!signature) throw Error('signature required');
    this.state = { schema: 1, signature, bins: Array.from({ length: 4 }, () => ({ changed: 0, same: 0 })), seen: [] };
    if (snapshot !== undefined) {
      const s = snapshot as PolicyState;
      if (s?.schema !== 1 || s.signature !== signature || !Array.isArray(s.bins) || s.bins.length !== 4
        || s.bins.some(b => !b || [b.changed, b.same].some(n => !Number.isInteger(n) || n < 0 || n > 1024))
        || !Array.isArray(s.seen) || s.seen.length > 4096 || s.seen.some(x => typeof x !== 'string')
        || new Set(s.seen).size !== s.seen.length) throw Error('invalid feedback policy');
      this.state = structuredClone(s);
    }
  }
  private bin(score: number) {
    if (!Number.isFinite(score) || score < 0 || score > 1) throw Error('invalid proposal score');
    return Math.min(3, Math.floor(score * 4));
  }
  decide(score: number) {
    const bin = this.bin(score), b = this.state.bins[bin], observations = b.changed + b.same;
    return { verify: observations < 3 || 4 * b.changed >= observations, bin, observations,
      eChangedRate: observations ? b.changed / observations : null };
  }
  observe(candidateId: string, evidenceId: string, score: number, result: Verification) {
    const bin = this.bin(score);
    if (result.candidateId !== candidateId || result.evidenceId !== evidenceId
      || !['changed', 'same', 'unknown'].includes(result.relation)) throw Error('feedback identity mismatch');
    if (result.relation === 'unknown' || this.state.seen.includes(candidateId)) return;
    const b = this.state.bins[bin];
    if (this.state.seen.length >= 4096 || b[result.relation] >= 1024) return;
    b[result.relation]++; this.state.seen.push(candidateId);
  }
  snapshot(): PolicyState { return structuredClone(this.state); }
}
