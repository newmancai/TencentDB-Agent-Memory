import { createHash } from 'node:crypto';
import type { MemoryRecord } from '../record/l1-writer.js';
import type { IMemoryStore } from '../store/types.js';

export type ProjectAction = 'read' | 'edit' | 'test' | 'build' | 'install';

export interface ProjectObservation {
  id: string;
  /** Host-assigned monotonically increasing sequence, not a model prediction. */
  order: number;
  role: 'user' | 'tool';
  text: string;
}

export interface ConstraintScope {
  paths: string[];
  actions: ProjectAction[];
}

export interface ConstraintProposal {
  key: string;
  quote: string;
  scope: ConstraintScope;
  supersedes?: string;
}

export interface ProjectConstraint extends ConstraintProposal {
  id: string;
  sourceId: string;
  order: number;
}

export interface ConstraintRetraction {
  constraintId: string;
  sourceId: string;
  order: number;
}

interface HistoricalConstraintEvidence {
  status: 'historical';
  sourceId: string;
  order: number;
  userQuote: string;
}

export interface ProjectMemorySnapshot {
  schema: 1;
  owner: string;
  project: string;
  revision: number;
  observations: ProjectObservation[];
  constraints: ProjectConstraint[];
  retractions: ConstraintRetraction[];
}

export interface ProjectIngestResult {
  revision: number;
  accepted: ProjectConstraint[];
  duplicate: boolean;
}

export interface ProjectContextOptions {
  paths: string[];
  action: ProjectAction;
  beforeOrder: number;
  maxBytes?: number;
  enabled?: boolean;
}

export interface ProjectContextResult {
  text: string;
  selectedIds: string[];
  omittedForBudget: number;
  revision: number;
  status: 'off' | 'selected' | 'fallback';
  reason: string | null;
}

const PROJECT_ACTIONS: ReadonlySet<ProjectAction> = new Set([
  'read',
  'edit',
  'test',
  'build',
  'install',
]);

const digest = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');

function validPath(path: string): boolean {
  if (typeof path !== 'string' || path.length > 512) return false;
  if (path === '.') return true;
  if (!path || path.startsWith('/') || path.includes('\\')) return false;

  return path.split('/').every((part) => part !== '..' && part !== '.' && part !== '');
}

function canonicalScope(scope: ConstraintScope): ConstraintScope {
  const validPaths =
    scope &&
    Array.isArray(scope.paths) &&
    scope.paths.length >= 1 &&
    scope.paths.length <= 16 &&
    scope.paths.every(validPath);
  const validActions =
    scope &&
    Array.isArray(scope.actions) &&
    scope.actions.length >= 1 &&
    scope.actions.length <= 5 &&
    scope.actions.every((action) => PROJECT_ACTIONS.has(action));

  if (!validPaths || !validActions) throw Error('invalid constraint scope');

  return {
    paths: [...new Set(scope.paths)].sort(),
    actions: [...new Set(scope.actions)].sort(),
  };
}

function sameScope(a: ConstraintScope, b: ConstraintScope): boolean {
  return JSON.stringify(canonicalScope(a)) === JSON.stringify(canonicalScope(b));
}

function normalizeProposal(proposal: ConstraintProposal): ConstraintProposal {
  return {
    key: proposal.key,
    quote: proposal.quote,
    scope: canonicalScope(proposal.scope),
    ...(proposal.supersedes ? { supersedes: proposal.supersedes } : {}),
  };
}

function validateObservation(observation: ProjectObservation): void {
  const valid =
    observation &&
    typeof observation.id === 'string' &&
    observation.id.length >= 1 &&
    observation.id.length <= 256 &&
    Number.isSafeInteger(observation.order) &&
    observation.order >= 1 &&
    (observation.role === 'user' || observation.role === 'tool') &&
    typeof observation.text === 'string' &&
    observation.text.trim().length >= 1 &&
    observation.text.length <= 32_000;

  if (!valid) throw Error('invalid observation');
}

function validateAndNormalizeProposal(
  proposal: ConstraintProposal,
  sourceText: string,
): ConstraintProposal {
  const scope = canonicalScope(proposal.scope);
  const validKey =
    typeof proposal.key === 'string' &&
    proposal.key.trim().length >= 1 &&
    proposal.key.length <= 128;
  const validQuote =
    typeof proposal.quote === 'string' &&
    proposal.quote.trim().length >= 1 &&
    proposal.quote.length <= 4_000;
  if (!validKey || !validQuote) {
    throw Error('constraint requires a unique exact source quote');
  }

  const firstQuote = sourceText.indexOf(proposal.quote);
  const uniqueExactQuote = firstQuote >= 0 && firstQuote === sourceText.lastIndexOf(proposal.quote);
  if (!uniqueExactQuote) throw Error('constraint requires a unique exact source quote');

  return {
    key: proposal.key,
    quote: proposal.quote,
    scope,
    ...(proposal.supersedes ? { supersedes: proposal.supersedes } : {}),
  };
}

function activeAt(state: ProjectMemorySnapshot, order: number): ProjectConstraint[] {
  const eligible = state.constraints.filter((rule) => rule.order <= order);
  const retired = new Set(eligible.flatMap((rule) => (rule.supersedes ? [rule.supersedes] : [])));

  for (const item of state.retractions) {
    if (item.order <= order) retired.add(item.constraintId);
  }

  return eligible.filter((rule) => !retired.has(rule.id));
}

function materializeConstraints(
  owner: string,
  project: string,
  state: ProjectMemorySnapshot,
  source: ProjectObservation,
  proposals: readonly ConstraintProposal[],
): ProjectConstraint[] {
  const accepted: ProjectConstraint[] = [];
  const current = activeAt(state, source.order);

  for (const proposal of proposals) {
    const normalized = validateAndNormalizeProposal(proposal, source.text);
    const peer = current.find(
      (rule) => rule.key === normalized.key && sameScope(rule.scope, normalized.scope),
    );

    if (normalized.supersedes) {
      if (!peer || peer.id !== normalized.supersedes) {
        throw Error('supersession must name the current same-scope predecessor');
      }
    } else if (peer) {
      throw Error('same-scope update needs an explicit predecessor');
    }

    const duplicatesAcceptedRule = accepted.some(
      (rule) => rule.key === normalized.key && sameScope(rule.scope, normalized.scope),
    );
    if (duplicatesAcceptedRule) {
      throw Error('duplicate key and scope in observation');
    }

    accepted.push({
      ...normalized,
      id: digest([owner, project, source.id, normalized]),
      sourceId: source.id,
      order: source.order,
    });
  }

  return accepted;
}

function pathsOverlap(left: string, right: string): boolean {
  return (
    left === '.' ||
    right === '.' ||
    left === right ||
    left.startsWith(`${right}/`) ||
    right.startsWith(`${left}/`)
  );
}

function emptySnapshot(owner: string, project: string): ProjectMemorySnapshot {
  return {
    schema: 1,
    owner,
    project,
    revision: 0,
    observations: [],
    constraints: [],
    retractions: [],
  };
}

/**
 * Bounded, single-writer project memory on the existing MemoryCore store.
 * Quotes/lineage are checked mechanically; semantic key and scope remain extractor judgments.
 * Only explicit user observations may propose normative constraints. Tool output stays evidence.
 */
export class ProjectMemory {
  private queue: Promise<unknown> = Promise.resolve();
  readonly recordId: string;

  constructor(
    readonly store: IMemoryStore,
    readonly owner: string,
    readonly project: string,
    readonly capacity = 128,
  ) {
    if (!owner || !project || !Number.isInteger(capacity) || capacity < 1 || capacity > 1024) {
      throw Error('invalid project memory configuration');
    }
    this.recordId = `project_memory_${digest([owner, project])}`;
  }

  async snapshot(): Promise<ProjectMemorySnapshot> {
    if (this.store.isDegraded()) throw Error('project memory store unavailable');
    if (!this.store.queryL1RecordsStrict) {
      throw Error('project memory requires failure-distinguishing reads');
    }

    const rows = await this.store.queryL1RecordsStrict({
      recordIds: [this.recordId],
      userId: this.owner,
    });
    if (!rows.length) return emptySnapshot(this.owner, this.project);
    if (rows.length !== 1) throw Error('duplicate project state');

    const state = JSON.parse(rows[0].content) as ProjectMemorySnapshot;
    const valid =
      state.schema === 1 &&
      state.owner === this.owner &&
      state.project === this.project &&
      Number.isSafeInteger(state.revision) &&
      state.revision >= 1 &&
      state.revision === rows[0].version &&
      Array.isArray(state.observations) &&
      Array.isArray(state.constraints) &&
      Array.isArray(state.retractions) &&
      state.observations.length <= this.capacity &&
      state.constraints.length <= this.capacity * 4;

    if (!valid) throw Error('invalid project state');
    return state;
  }

  private async save(state: ProjectMemorySnapshot): Promise<void> {
    const now = new Date().toISOString();
    const record: MemoryRecord = {
      id: this.recordId,
      content: JSON.stringify(state),
      type: 'work_method',
      priority: 50,
      scene_name: 'scoped-project-memory',
      source_message_ids: state.observations.map((observation) => observation.id),
      metadata: {},
      timestamps: [],
      createdAt: now,
      updatedAt: now,
      version: state.revision,
      sessionKey: this.project,
      sessionId: this.project,
      userId: this.owner,
      agentId: 'project-memory',
      taskId: this.project,
    };

    if (!(await this.store.upsertL1(record, undefined))) {
      throw Error('project memory persistence failed');
    }
  }

  private serialize<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.queue.then(operation);
    this.queue = result.catch(() => {});
    return result;
  }

  async ingest(
    observation: ProjectObservation,
    proposals: readonly ConstraintProposal[],
  ): Promise<ProjectIngestResult> {
    // Clone before scheduling: callers cannot alter a queued observation or proposal.
    const source = structuredClone(observation);
    const inputs = structuredClone(proposals);

    return this.serialize(async () => {
      validateObservation(source);
      if (
        !Array.isArray(inputs) ||
        inputs.length > 4 ||
        (source.role !== 'user' && inputs.length)
      ) {
        throw Error('only user observations may introduce bounded constraints');
      }

      const state = await this.snapshot();
      const previous = state.observations.find((item) => item.id === source.id);
      if (previous) {
        const sourceMatches =
          previous.order === source.order &&
          previous.role === source.role &&
          previous.text === source.text;
        if (!sourceMatches) throw Error('source identity conflict');

        const existing = state.constraints.filter((rule) => rule.sourceId === source.id);
        const expected = inputs.map(normalizeProposal);
        const actual = existing.map(normalizeProposal);
        if (JSON.stringify(actual) !== JSON.stringify(expected)) {
          throw Error('source proposals conflict');
        }
        return { revision: state.revision, accepted: existing, duplicate: true };
      }

      if (state.observations.length >= this.capacity) {
        throw Error('project observation capacity');
      }
      if (source.order <= (state.observations.at(-1)?.order ?? 0)) {
        throw Error('non-monotonic observation');
      }

      const accepted = materializeConstraints(this.owner, this.project, state, source, inputs);

      const next: ProjectMemorySnapshot = {
        ...state,
        revision: state.revision + 1,
        observations: [...state.observations, source],
        constraints: [...state.constraints, ...accepted],
      };
      await this.save(next);
      return { revision: next.revision, accepted, duplicate: false };
    });
  }

  async retract(constraintId: string, observation: ProjectObservation): Promise<number> {
    const source = structuredClone(observation);

    return this.serialize(async () => {
      validateObservation(source);
      const state = await this.snapshot();
      const validRetraction =
        source.role === 'user' &&
        source.order > (state.observations.at(-1)?.order ?? 0) &&
        !state.observations.some((item) => item.id === source.id) &&
        state.observations.length < this.capacity &&
        activeAt(state, source.order).some((rule) => rule.id === constraintId);

      if (!validRetraction) {
        throw Error('retraction requires a new user observation and an active constraint');
      }

      const next: ProjectMemorySnapshot = {
        ...state,
        revision: state.revision + 1,
        observations: [...state.observations, source],
        retractions: [
          ...state.retractions,
          { constraintId, sourceId: source.id, order: source.order },
        ],
      };
      await this.save(next);
      return next.revision;
    });
  }

  async context(options: ProjectContextOptions): Promise<ProjectContextResult> {
    const result: ProjectContextResult = {
      text: '',
      selectedIds: [],
      omittedForBudget: 0,
      revision: 0,
      status: 'off',
      reason: null,
    };
    if (options.enabled === false) return result;

    const validQuery =
      Array.isArray(options.paths) &&
      options.paths.length >= 1 &&
      options.paths.every(validPath) &&
      PROJECT_ACTIONS.has(options.action) &&
      Number.isSafeInteger(options.beforeOrder) &&
      options.beforeOrder >= 1;
    if (!validQuery) throw Error('invalid context query');

    const budget = options.maxBytes ?? 12_000;
    if (!Number.isInteger(budget) || budget < 1 || budget > 64_000) {
      throw Error('invalid context budget');
    }

    try {
      const state = await this.snapshot();
      const rules = activeAt(state, options.beforeOrder - 1).filter(
        (rule) =>
          rule.scope.actions.includes(options.action) &&
          options.paths.some((path) =>
            rule.scope.paths.some((prefix) => pathsOverlap(path, prefix)),
          ),
      );

      // Keep applicable broader and narrower quotes, with scope visible. Do not
      // silently use one directory's exception for another requested directory.
      rules.sort((a, b) => b.order - a.order || a.id.localeCompare(b.id));

      const lines: string[] = [];
      for (const rule of rules) {
        const predecessorEvidence = this.predecessorEvidence(state, rule);
        const line = JSON.stringify({
          id: rule.id,
          key: rule.key,
          scope: rule.scope,
          sourceId: rule.sourceId,
          order: rule.order,
          userQuote: rule.quote,
          ...(predecessorEvidence.length ? { predecessorEvidence } : {}),
        });

        if (Buffer.byteLength([...lines, line].join('\n')) > budget) {
          result.omittedForBudget++;
          continue;
        }
        lines.push(line);
        result.selectedIds.push(rule.id);
      }

      return {
        ...result,
        text: lines.join('\n'),
        revision: state.revision,
        status: 'selected',
      };
    } catch (error) {
      return {
        ...result,
        text: '',
        selectedIds: [],
        omittedForBudget: 0,
        status: 'fallback',
        reason: String(error),
      };
    }
  }

  private predecessorEvidence(
    state: ProjectMemorySnapshot,
    rule: ProjectConstraint,
  ): HistoricalConstraintEvidence[] {
    // “Everything else is unchanged” needs its predecessors to remain readable.
    // They are evidence only; this traversal never reactivates an old constraint.
    const evidence: HistoricalConstraintEvidence[] = [];
    const seen = new Set([rule.id]);
    let child = rule;

    while (child.supersedes) {
      const parent = state.constraints.find((item) => item.id === child.supersedes);
      const validParent =
        parent &&
        !seen.has(parent.id) &&
        parent.order < child.order &&
        parent.key === child.key &&
        sameScope(parent.scope, child.scope);
      if (!parent || !validParent) throw Error('invalid project constraint lineage');

      seen.add(parent.id);
      evidence.push({
        status: 'historical',
        sourceId: parent.sourceId,
        order: parent.order,
        userQuote: parent.quote,
      });
      child = parent;
    }

    return evidence.reverse();
  }
}
