import { createHash } from 'node:crypto';
import type { IMemoryStore } from '../store/types.js';
import type { MemoryRecord } from '../record/l1-writer.js';

export type ProjectAction = 'read' | 'edit' | 'test' | 'build' | 'install';
export interface ProjectObservation {
  id: string;
  /** Host-assigned monotonically increasing sequence, not a model prediction. */
  order: number;
  role: 'user' | 'tool';
  text: string;
}
export interface ConstraintScope { paths: string[]; actions: ProjectAction[] }
export interface ConstraintProposal {
  key: string;
  quote: string;
  scope: ConstraintScope;
  supersedes?: string;
}
export interface ProjectConstraint extends ConstraintProposal {
  id: string; sourceId: string; order: number;
}
export interface ProjectMemorySnapshot {
  schema: 1; owner: string; project: string; revision: number;
  observations: ProjectObservation[];
  constraints: ProjectConstraint[];
  retractions: { constraintId: string; sourceId: string; order: number }[];
}
const actions = new Set(['read', 'edit', 'test', 'build', 'install']);
const digest = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');
function validPath(path: string) {
  return typeof path === 'string' && path.length <= 512
    && (path === '.' || (!!path && !path.startsWith('/') && !path.includes('\\')
      && path.split('/').every(part => part !== '..' && part !== '.' && part !== '')));
}
function canonicalScope(scope: ConstraintScope): ConstraintScope {
  if (!scope || !Array.isArray(scope.paths) || !scope.paths.length || scope.paths.length > 16
    || !scope.paths.every(validPath) || !Array.isArray(scope.actions) || !scope.actions.length
    || scope.actions.length > 5 || !scope.actions.every(action => actions.has(action))) {
    throw Error('invalid constraint scope');
  }
  return { paths: [...new Set(scope.paths)].sort(), actions: [...new Set(scope.actions)].sort() };
}
function sameScope(a: ConstraintScope, b: ConstraintScope) {
  return JSON.stringify(canonicalScope(a)) === JSON.stringify(canonicalScope(b));
}
function normalizeProposal(proposal: ConstraintProposal): ConstraintProposal {
  return { key: proposal.key, quote: proposal.quote, scope: canonicalScope(proposal.scope),
    ...(proposal.supersedes ? { supersedes: proposal.supersedes } : {}) };
}
function validateObservation(observation: ProjectObservation) {
  if (!observation || typeof observation.id !== 'string' || !observation.id || observation.id.length > 256
    || !Number.isSafeInteger(observation.order) || observation.order < 1
    || !['user', 'tool'].includes(observation.role) || typeof observation.text !== 'string'
    || !observation.text.trim() || observation.text.length > 32000) throw Error('invalid observation');
}
function activeAt(state: ProjectMemorySnapshot, order: number) {
  const eligible = state.constraints.filter(rule => rule.order <= order);
  const retired = new Set(eligible.flatMap(rule => rule.supersedes ? [rule.supersedes] : []));
  for (const item of state.retractions) if (item.order <= order) retired.add(item.constraintId);
  return eligible.filter(rule => !retired.has(rule.id));
}

/**
 * Bounded, single-writer project memory on the existing MemoryCore store.
 * Quotes/lineage are checked mechanically; semantic key and scope remain extractor judgments.
 * Only explicit user observations may propose normative constraints. Tool output stays evidence.
 */
export class ProjectMemory {
  private queue: Promise<unknown> = Promise.resolve();
  readonly recordId: string;
  constructor(readonly store: IMemoryStore, readonly owner: string, readonly project: string,
    readonly capacity = 128) {
    if (!owner || !project || !Number.isInteger(capacity) || capacity < 1 || capacity > 1024) {
      throw Error('invalid project memory configuration');
    }
    this.recordId = `project_memory_${digest([owner, project])}`;
  }
  async snapshot(): Promise<ProjectMemorySnapshot> {
    if (this.store.isDegraded()) throw Error('project memory store unavailable');
    if (!this.store.queryL1RecordsStrict) throw Error('project memory requires failure-distinguishing reads');
    const rows = await this.store.queryL1RecordsStrict({ recordIds: [this.recordId], userId: this.owner });
    if (!rows.length) return {
      schema: 1, owner: this.owner, project: this.project, revision: 0,
      observations: [], constraints: [], retractions: [],
    };
    if (rows.length !== 1) throw Error('duplicate project state');
    const state = JSON.parse(rows[0].content) as ProjectMemorySnapshot;
    if (state.schema !== 1 || state.owner !== this.owner || state.project !== this.project
      || !Number.isSafeInteger(state.revision) || state.revision < 1
      || state.revision !== rows[0].version || !Array.isArray(state.observations)
      || !Array.isArray(state.constraints) || !Array.isArray(state.retractions)
      || state.observations.length > this.capacity || state.constraints.length > this.capacity * 4) {
      throw Error('invalid project state');
    }
    return state;
  }
  private async save(state: ProjectMemorySnapshot) {
    const now = new Date().toISOString();
    const record: MemoryRecord = {
      id: this.recordId, content: JSON.stringify(state), type: 'work_method', priority: 50,
      scene_name: 'scoped-project-memory', source_message_ids: state.observations.map(o => o.id),
      metadata: {}, timestamps: [], createdAt: now, updatedAt: now, version: state.revision,
      sessionKey: this.project, sessionId: this.project, userId: this.owner,
      agentId: 'project-memory', taskId: this.project,
    };
    if (!await this.store.upsertL1(record, undefined)) throw Error('project memory persistence failed');
  }
  private serialize<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.queue.then(operation);
    this.queue = result.catch(() => {});
    return result;
  }
  async ingest(observation: ProjectObservation, proposals: readonly ConstraintProposal[]) {
    // Clone before scheduling: callers cannot alter a queued observation or proposal.
    const source = structuredClone(observation), inputs = structuredClone(proposals);
    return this.serialize(async () => {
      validateObservation(source);
      if (!Array.isArray(inputs) || inputs.length > 4 || (source.role !== 'user' && inputs.length)) {
        throw Error('only user observations may introduce bounded constraints');
      }
      const state = await this.snapshot();
      const previous = state.observations.find(item => item.id === source.id);
      if (previous) {
        if (previous.order !== source.order || previous.role !== source.role || previous.text !== source.text) {
          throw Error('source identity conflict');
        }
        const existing = state.constraints.filter(rule => rule.sourceId === source.id);
        const expected = inputs.map(normalizeProposal);
        const actual = existing.map(normalizeProposal);
        if (JSON.stringify(actual) !== JSON.stringify(expected)) throw Error('source proposals conflict');
        return { revision: state.revision, accepted: existing, duplicate: true };
      }
      if (state.observations.length >= this.capacity) throw Error('project observation capacity');
      if (source.order <= (state.observations.at(-1)?.order ?? 0)) throw Error('non-monotonic observation');
      const accepted: ProjectConstraint[] = [];
      const current = activeAt(state, source.order);
      for (const proposal of inputs) {
        const scope = canonicalScope(proposal.scope);
        if (typeof proposal.key !== 'string' || !proposal.key.trim() || proposal.key.length > 128
          || typeof proposal.quote !== 'string' || !proposal.quote.trim() || proposal.quote.length > 4000
          || source.text.indexOf(proposal.quote) < 0
          || source.text.indexOf(proposal.quote) !== source.text.lastIndexOf(proposal.quote)) {
          throw Error('constraint requires a unique exact source quote');
        }
        const peer = current.find(rule => rule.key === proposal.key && sameScope(rule.scope, scope));
        if (proposal.supersedes) {
          if (!peer || peer.id !== proposal.supersedes) throw Error('supersession must name the current same-scope predecessor');
        } else if (peer) throw Error('same-scope update needs an explicit predecessor');
        if (accepted.some(rule => rule.key === proposal.key && sameScope(rule.scope, scope))) {
          throw Error('duplicate key and scope in observation');
        }
        const normalized = normalizeProposal(proposal);
        accepted.push({ ...normalized, id: digest([this.owner, this.project, source.id, normalized]),
          sourceId: source.id, order: source.order });
      }
      const next = { ...state, revision: state.revision + 1,
        observations: [...state.observations, source], constraints: [...state.constraints, ...accepted] };
      await this.save(next);
      return { revision: next.revision, accepted, duplicate: false };
    });
  }
  async retract(constraintId: string, observation: ProjectObservation) {
    const source = structuredClone(observation);
    return this.serialize(async () => {
      validateObservation(source);
      const state = await this.snapshot();
      if (source.role !== 'user' || source.order <= (state.observations.at(-1)?.order ?? 0)
        || state.observations.some(o => o.id === source.id) || state.observations.length >= this.capacity
        || !activeAt(state, source.order).some(rule => rule.id === constraintId)) {
        throw Error('retraction requires a new user observation and an active constraint');
      }
      const next = { ...state, revision: state.revision + 1,
        observations: [...state.observations, source], retractions: [...state.retractions,
          { constraintId, sourceId: source.id, order: source.order }] };
      await this.save(next);
      return next.revision;
    });
  }
  async context(options: {
    paths: string[]; action: ProjectAction; beforeOrder: number;
    maxBytes?: number; enabled?: boolean;
  }) {
    const result = { text: '', selectedIds: [] as string[], omittedForBudget: 0,
      revision: 0, status: 'off' as 'off' | 'selected' | 'fallback', reason: null as string | null };
    if (options.enabled === false) return result;
    try {
      if (!options.paths.length || !options.paths.every(validPath) || !actions.has(options.action)
        || !Number.isSafeInteger(options.beforeOrder) || options.beforeOrder < 1) throw Error('invalid context query');
      const budget = options.maxBytes ?? 12000;
      if (!Number.isInteger(budget) || budget < 1 || budget > 64000) throw Error('invalid context budget');
      const state = await this.snapshot();
      const rules = activeAt(state, options.beforeOrder - 1).filter(rule =>
        rule.scope.actions.includes(options.action) && options.paths.some(path => rule.scope.paths.some(
          prefix => prefix === '.' || path === '.' || path === prefix
            || path.startsWith(`${prefix}/`) || prefix.startsWith(`${path}/`))));
      // Keep applicable broader and narrower quotes, with scope visible. Do not
      // silently use one directory's exception for another requested directory.
      rules.sort((a, b) => b.order - a.order || a.id.localeCompare(b.id));
      const lines: string[] = [];
      for (const rule of rules) {
        // "The other rules are unchanged" needs its predecessor to be readable.
        // Preserve that source as historical evidence, never reactivate it.
        const predecessors: { status: 'historical'; sourceId: string; order: number; userQuote: string }[] = [];
        const seen = new Set([rule.id]);
        let child = rule;
        while (child.supersedes) {
          const parent = state.constraints.find(item => item.id === child.supersedes);
          if (!parent || seen.has(parent.id) || parent.order >= child.order
            || parent.key !== child.key || !sameScope(parent.scope, child.scope)) {
            throw Error('invalid project constraint lineage');
          }
          seen.add(parent.id);
          predecessors.push({ status: 'historical', sourceId: parent.sourceId,
            order: parent.order, userQuote: parent.quote });
          child = parent;
        }
        const line = JSON.stringify({ id: rule.id, key: rule.key, scope: rule.scope,
          sourceId: rule.sourceId, order: rule.order, userQuote: rule.quote,
          ...(predecessors.length ? { predecessorEvidence: predecessors.reverse() } : {}) });
        if (Buffer.byteLength([...lines, line].join('\n')) > budget) {
          result.omittedForBudget++;
          continue;
        }
        lines.push(line); result.selectedIds.push(rule.id);
      }
      return { ...result, text: lines.join('\n'), revision: state.revision, status: 'selected' as const };
    } catch (error) {
      return { ...result, text: '', selectedIds: [], omittedForBudget: 0,
        status: 'fallback' as const, reason: String(error) };
    }
  }
}
