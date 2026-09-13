import { assertScopePredicate, type FeedbackScope } from './scope.js';

export type MemoryAction = 'omit' | 'include' | 'verify' | 'ask';
export type FeedbackObservationType =
  | 'explicit_correction' | 'edit' | 'retry' | 'acceptance' | 'implicit' | 'unknown';
export type FeedbackTargetType =
  | 'answer_span' | 'tool_call' | 'memory_assertion' | 'style' | 'unknown';
export type FeedbackAuthority =
  | 'explicit_user' | 'tool_readback' | 'qualified_review'
  | 'behavioral' | 'model_inference' | 'unknown';
export type AssertionStatus = 'candidate' | 'verified' | 'disputed' | 'expired' | 'superseded';
export type OutcomeResult = 'success' | 'failure' | 'partial' | 'unknown';
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export interface TraceCost {
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  monetaryUsd: number | null;
}

export interface PromptMemorySpan {
  memoryId: string;
  start: number;
  end: number;
}

/** A policy decision made before its result is known. */
export interface DecisionTrace {
  kind: 'decision_trace';
  schema: 1;
  id: string;
  contextId: string;
  taskId: string;
  contextEventIds: readonly string[];
  candidateMemoryIds: readonly string[];
  action: MemoryAction;
  selectedMemoryIds: readonly string[];
  policyVersion: string;
  /** Probability assigned to the complete logged action, including selectedMemoryIds. */
  propensity: number;
  decidedAt: string;
  promptMemorySpans: readonly PromptMemorySpan[];
  outputIds: readonly string[];
  toolCallIds: readonly string[];
  cost?: TraceCost;
}

/** An observation, not an automatic correctness label or memory mutation. */
export interface FeedbackClaim {
  kind: 'feedback_claim';
  schema: 1;
  id: string;
  /** null means attribution is explicitly unresolved. */
  decisionId: string | null;
  observationType: FeedbackObservationType;
  targetType: FeedbackTargetType;
  targetIds: readonly string[];
  claimText: string;
  scope: FeedbackScope;
  authority: FeedbackAuthority;
  confidence: number;
  sourceEventIds: readonly string[];
  observedAt: string;
}

/** A bitemporal assertion; source claims remain separate from assertion state. */
export interface MemoryAssertion {
  kind: 'memory_assertion';
  schema: 1;
  id: string;
  subject: string;
  predicate: string;
  value: JsonValue;
  scope: FeedbackScope;
  validFrom: string | null;
  validTo: string | null;
  recordedAt: string;
  supersededAt: string | null;
  status: AssertionStatus;
  authority: FeedbackAuthority;
  sourceEventIds: readonly string[];
  supportedByClaimIds: readonly string[];
  contradictsAssertionIds: readonly string[];
}

/** A delayed result linked to the action that may have caused it. */
export interface FeedbackOutcome {
  kind: 'outcome';
  schema: 1;
  id: string;
  decisionId: string;
  result: OutcomeResult;
  /** null records an outcome that is not yet usable by a numeric policy learner. */
  reward: number | null;
  metrics: Readonly<Record<string, JsonValue>>;
  source: string;
  observedAt: string;
  delayed: boolean;
  cost?: TraceCost;
}

export type FeedbackReplayRecord = DecisionTrace | FeedbackClaim | MemoryAssertion | FeedbackOutcome;
export type DecisionTraceInput = Omit<DecisionTrace, 'kind' | 'schema'>;
export type FeedbackClaimInput = Omit<FeedbackClaim, 'kind' | 'schema'>;
export type MemoryAssertionInput = Omit<MemoryAssertion, 'kind' | 'schema'>;
export type FeedbackOutcomeInput = Omit<FeedbackOutcome, 'kind' | 'schema'>;

export interface FeedbackReplayIssue {
  index: number;
  recordId?: string;
  code: string;
  path: string;
  message: string;
}

export interface FeedbackLearningSample {
  decisionId: string;
  feedbackClaimIds: readonly string[];
  outcomeIds: readonly string[];
}

export interface FeedbackReplayResult {
  ok: boolean;
  issues: readonly FeedbackReplayIssue[];
  counts: Readonly<Record<FeedbackReplayRecord['kind'], number>>;
  /** Empty whenever structural or causal validation fails. */
  learningSamples: readonly FeedbackLearningSample[];
  /** Structurally valid decisions that do not yet have a numeric reward. */
  pendingDecisionIds: readonly string[];
}

const actions = new Set<MemoryAction>(['omit', 'include', 'verify', 'ask']);
const observations = new Set<FeedbackObservationType>(
  ['explicit_correction', 'edit', 'retry', 'acceptance', 'implicit', 'unknown'],
);
const targets = new Set<FeedbackTargetType>(
  ['answer_span', 'tool_call', 'memory_assertion', 'style', 'unknown'],
);
const authorities = new Set<FeedbackAuthority>(
  ['explicit_user', 'tool_readback', 'qualified_review', 'behavioral', 'model_inference', 'unknown'],
);
const assertionStatuses = new Set<AssertionStatus>(
  ['candidate', 'verified', 'disputed', 'expired', 'superseded'],
);
const outcomeResults = new Set<OutcomeResult>(['success', 'failure', 'partial', 'unknown']);
const own = (v: object, key: string) => Object.prototype.hasOwnProperty.call(v, key);
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === 'string' && !!v.trim();
const timestamp = (v: unknown): v is string => typeof v === 'string' && Number.isFinite(Date.parse(v));
const stringList = (v: unknown): v is string[] => Array.isArray(v)
  && v.every(text) && new Set(v).size === v.length;

function jsonValue(v: unknown, ancestors = new Set<object>()): v is JsonValue {
  if (v === null || typeof v === 'string' || typeof v === 'boolean') return true;
  if (typeof v === 'number') return Number.isFinite(v);
  if (!v || typeof v !== 'object' || ancestors.has(v)) return false;
  ancestors.add(v);
  const valid = Array.isArray(v)
    ? v.every(item => jsonValue(item, ancestors))
    : Object.entries(v).every(([key, item]) => !!key && jsonValue(item, ancestors));
  ancestors.delete(v);
  return valid;
}

function recordId(record: unknown): string | undefined {
  return object(record) && typeof record.id === 'string' ? record.id : undefined;
}

function validateCost(cost: unknown, path: string, add: (code: string, path: string, message: string) => void) {
  if (!object(cost)) return add('invalid_cost', path, 'cost must be an object');
  for (const key of ['inputTokens', 'outputTokens', 'latencyMs'] as const) {
    if (!Number.isFinite(cost[key]) || (cost[key] as number) < 0) {
      add('invalid_cost', `${path}.${key}`, `${key} must be a finite non-negative number`);
    }
  }
  if (cost.monetaryUsd !== null
      && (!Number.isFinite(cost.monetaryUsd) || (cost.monetaryUsd as number) < 0)) {
    add('invalid_cost', `${path}.monetaryUsd`, 'monetaryUsd must be null or a finite non-negative number');
  }
}

function validateRecord(record: unknown, index: number): FeedbackReplayIssue[] {
  const issues: FeedbackReplayIssue[] = [];
  const id = recordId(record);
  const add = (code: string, path: string, message: string) =>
    issues.push({ index, ...(id ? { recordId: id } : {}), code, path, message });
  if (!object(record)) {
    add('invalid_record', `${index}`, 'record must be an object');
    return issues;
  }
  if (record.schema !== 1) add('invalid_schema', `${index}.schema`, 'schema must equal 1');
  if (!text(record.id)) add('invalid_id', `${index}.id`, 'id must be a non-empty string');

  if (record.kind === 'decision_trace') {
    for (const key of ['contextId', 'taskId', 'policyVersion'] as const) {
      if (!text(record[key])) add('invalid_field', `${index}.${key}`, `${key} must be a non-empty string`);
    }
    for (const key of ['contextEventIds', 'candidateMemoryIds', 'selectedMemoryIds', 'outputIds', 'toolCallIds'] as const) {
      if (!own(record, key) || !stringList(record[key])) {
        add(key === 'candidateMemoryIds' ? 'missing_candidate_set' : 'invalid_id_list',
          `${index}.${key}`, `${key} must be a present, duplicate-free string array`);
      }
    }
    if (!own(record, 'action') || !actions.has(record.action as MemoryAction)) {
      add('missing_action', `${index}.action`, 'action must be omit, include, verify, or ask');
    }
    if (!own(record, 'propensity') || !Number.isFinite(record.propensity)
        || (record.propensity as number) <= 0 || (record.propensity as number) > 1) {
      add('missing_propensity', `${index}.propensity`, 'propensity must be finite and in (0, 1]');
    }
    if (!timestamp(record.decidedAt)) add('invalid_timestamp', `${index}.decidedAt`, 'decidedAt must be a timestamp');
    if (stringList(record.candidateMemoryIds) && stringList(record.selectedMemoryIds)) {
      const candidates = new Set(record.candidateMemoryIds);
      if (record.selectedMemoryIds.some(memoryId => !candidates.has(memoryId))) {
        add('selection_outside_candidates', `${index}.selectedMemoryIds`, 'selected memories must be candidates');
      }
      if (record.action === 'include' && record.selectedMemoryIds.length === 0) {
        add('empty_include', `${index}.selectedMemoryIds`, 'include must select at least one memory');
      }
      if (record.action === 'omit' && record.selectedMemoryIds.length !== 0) {
        add('nonempty_omit', `${index}.selectedMemoryIds`, 'omit cannot select a memory');
      }
    }
    if (!Array.isArray(record.promptMemorySpans)) {
      add('invalid_spans', `${index}.promptMemorySpans`, 'promptMemorySpans must be an array');
    } else {
      const selected = stringList(record.selectedMemoryIds) ? new Set(record.selectedMemoryIds) : new Set<string>();
      for (const [spanIndex, span] of record.promptMemorySpans.entries()) {
        if (!object(span) || !text(span.memoryId) || !selected.has(span.memoryId)
          || !Number.isInteger(span.start) || !Number.isInteger(span.end)
          || (span.start as number) < 0 || (span.end as number) <= (span.start as number)) {
          add('invalid_span', `${index}.promptMemorySpans.${spanIndex}`,
            'a span must reference a selected memory and have integer 0 <= start < end');
        }
      }
    }
    if (record.cost !== undefined) validateCost(record.cost, `${index}.cost`, add);
  } else if (record.kind === 'feedback_claim') {
    if (record.decisionId !== null && !text(record.decisionId)) {
      add('invalid_decision_link', `${index}.decisionId`, 'decisionId must be null or a non-empty string');
    }
    if (!observations.has(record.observationType as FeedbackObservationType)) {
      add('invalid_observation_type', `${index}.observationType`, 'unknown observation type');
    }
    if (!targets.has(record.targetType as FeedbackTargetType)) {
      add('invalid_target_type', `${index}.targetType`, 'unknown target type');
    }
    if (!stringList(record.targetIds)) add('invalid_id_list', `${index}.targetIds`, 'targetIds must be duplicate-free strings');
    if (record.targetType === 'unknown' && Array.isArray(record.targetIds) && record.targetIds.length) {
      add('unknown_target_has_ids', `${index}.targetIds`, 'an unknown target cannot claim target IDs');
    } else if (record.targetType !== 'unknown' && Array.isArray(record.targetIds) && !record.targetIds.length) {
      add('known_target_without_ids', `${index}.targetIds`, 'a known target type requires at least one target ID');
    }
    if (record.decisionId === null && (record.targetType !== 'unknown'
        || !Array.isArray(record.targetIds) || record.targetIds.length !== 0)) {
      add('unresolved_binding', `${index}.decisionId`, 'unbound feedback must use targetType=unknown and no target IDs');
    }
    if (!text(record.claimText)) add('invalid_field', `${index}.claimText`, 'claimText must be a non-empty string');
    try {
      if (typeof record.scope === 'string') {
        if (!record.scope.trim()) throw Error('empty');
      } else assertScopePredicate(record.scope);
    } catch {
      add('invalid_scope', `${index}.scope`, 'scope must be a non-empty string or an exact scalar predicate');
    }
    if (!authorities.has(record.authority as FeedbackAuthority)) {
      add('invalid_authority', `${index}.authority`, 'unknown authority');
    }
    if (!Number.isFinite(record.confidence) || (record.confidence as number) < 0
        || (record.confidence as number) > 1) {
      add('invalid_confidence', `${index}.confidence`, 'confidence must be finite and in [0, 1]');
    }
    if (!stringList(record.sourceEventIds) || record.sourceEventIds.length === 0) {
      add('missing_source_events', `${index}.sourceEventIds`, 'feedback requires at least one source event');
    }
    if (!timestamp(record.observedAt)) add('invalid_timestamp', `${index}.observedAt`, 'observedAt must be a timestamp');
  } else if (record.kind === 'memory_assertion') {
    for (const key of ['subject', 'predicate'] as const) {
      if (!text(record[key])) add('invalid_field', `${index}.${key}`, `${key} must be a non-empty string`);
    }
    try {
      if (typeof record.scope === 'string') {
        if (!record.scope.trim()) throw Error('empty');
      } else assertScopePredicate(record.scope);
    } catch {
      add('invalid_scope', `${index}.scope`, 'scope must be a non-empty string or an exact scalar predicate');
    }
    if (!own(record, 'value') || !jsonValue(record.value)) {
      add('invalid_json_value', `${index}.value`, 'value must be JSON-serializable and finite');
    }
    for (const key of ['validFrom', 'validTo', 'supersededAt'] as const) {
      if (record[key] !== null && !timestamp(record[key])) {
        add('invalid_timestamp', `${index}.${key}`, `${key} must be null or a timestamp`);
      }
    }
    if (!timestamp(record.recordedAt)) add('invalid_timestamp', `${index}.recordedAt`, 'recordedAt must be a timestamp');
    if (!assertionStatuses.has(record.status as AssertionStatus)) {
      add('invalid_status', `${index}.status`, 'unknown assertion status');
    }
    if (!authorities.has(record.authority as FeedbackAuthority)) {
      add('invalid_authority', `${index}.authority`, 'unknown authority');
    }
    for (const key of ['sourceEventIds', 'supportedByClaimIds', 'contradictsAssertionIds'] as const) {
      if (!stringList(record[key])) add('invalid_id_list', `${index}.${key}`, `${key} must be duplicate-free strings`);
    }
    if (!stringList(record.sourceEventIds) || record.sourceEventIds.length === 0) {
      add('missing_source_events', `${index}.sourceEventIds`, 'an assertion requires at least one source event');
    }
    if (timestamp(record.validFrom) && timestamp(record.validTo)
        && Date.parse(record.validFrom) > Date.parse(record.validTo)) {
      add('invalid_valid_time', `${index}.validTo`, 'validTo cannot precede validFrom');
    }
    if (timestamp(record.recordedAt) && timestamp(record.supersededAt)
        && Date.parse(record.recordedAt) > Date.parse(record.supersededAt)) {
      add('invalid_transaction_time', `${index}.supersededAt`, 'supersededAt cannot precede recordedAt');
    }
    if ((record.status === 'superseded') !== (record.supersededAt !== null)) {
      add('inconsistent_supersession', `${index}.supersededAt`,
        'status=superseded and a non-null supersededAt must appear together');
    }
  } else if (record.kind === 'outcome') {
    if (!text(record.decisionId)) add('invalid_decision_link', `${index}.decisionId`, 'decisionId must be a non-empty string');
    if (!outcomeResults.has(record.result as OutcomeResult)) {
      add('invalid_result', `${index}.result`, 'unknown outcome result');
    }
    if (record.reward !== null && !Number.isFinite(record.reward)) {
      add('invalid_reward', `${index}.reward`, 'reward must be null or a finite number');
    }
    if (!object(record.metrics) || !jsonValue(record.metrics)) {
      add('invalid_metrics', `${index}.metrics`, 'metrics must be a JSON object');
    }
    if (!text(record.source)) add('invalid_field', `${index}.source`, 'source must be a non-empty string');
    if (!timestamp(record.observedAt)) add('invalid_timestamp', `${index}.observedAt`, 'observedAt must be a timestamp');
    if (typeof record.delayed !== 'boolean') add('invalid_field', `${index}.delayed`, 'delayed must be boolean');
    if (record.cost !== undefined) validateCost(record.cost, `${index}.cost`, add);
  } else {
    add('invalid_kind', `${index}.kind`, 'unknown replay record kind');
  }
  return issues;
}

/**
 * Validate an append-only JSONL replay before deriving learning samples.
 * It intentionally performs no storage, policy update, or model call.
 */
export function validateFeedbackReplay(records: readonly unknown[]): FeedbackReplayResult {
  const issues = records.flatMap(validateRecord);
  const counts: Record<FeedbackReplayRecord['kind'], number> = {
    decision_trace: 0, feedback_claim: 0, memory_assertion: 0, outcome: 0,
  };
  const ids = new Map<string, { kind: FeedbackReplayRecord['kind']; index: number; record: FeedbackReplayRecord }>();
  const decisions = new Map<string, { index: number; record: DecisionTrace }>();
  const claimsByDecision = new Map<string, string[]>();
  const outcomesByDecision = new Map<string, FeedbackOutcome[]>();

  for (const [index, raw] of records.entries()) {
    if (!object(raw) || !['decision_trace', 'feedback_claim', 'memory_assertion', 'outcome'].includes(String(raw.kind))) continue;
    const record = raw as unknown as FeedbackReplayRecord;
    counts[record.kind]++;
    if (!text(record.id)) continue;
    const previous = ids.get(record.id);
    if (previous) {
      issues.push({ index, recordId: record.id, code: 'duplicate_record_id', path: `${index}.id`,
        message: `record ID already used at index ${previous.index}` });
      continue;
    }
    ids.set(record.id, { kind: record.kind, index, record });
    if (record.kind === 'decision_trace') decisions.set(record.id, { index, record });
  }

  for (const [index, raw] of records.entries()) {
    if (!object(raw) || !text(raw.id)) continue;
    if (raw.kind === 'feedback_claim' && (raw.decisionId === null || text(raw.decisionId))) {
      if (raw.decisionId !== null) {
        const decision = decisions.get(raw.decisionId);
        if (!decision || decision.index >= index) {
          issues.push({ index, recordId: raw.id, code: 'missing_prior_decision', path: `${index}.decisionId`,
            message: 'feedback must reference a prior decision trace' });
        } else {
          claimsByDecision.set(raw.decisionId, [...(claimsByDecision.get(raw.decisionId) ?? []), raw.id]);
          if (timestamp(raw.observedAt) && timestamp(decision.record.decidedAt)
              && Date.parse(raw.observedAt) < Date.parse(decision.record.decidedAt)) {
            issues.push({ index, recordId: raw.id, code: 'causal_time_inversion', path: `${index}.observedAt`,
              message: 'feedback cannot precede its decision' });
          }
        }
      }
    } else if (raw.kind === 'outcome' && text(raw.decisionId)) {
      const decision = decisions.get(raw.decisionId);
      if (!decision || decision.index >= index) {
        issues.push({ index, recordId: raw.id, code: 'missing_prior_decision', path: `${index}.decisionId`,
          message: 'outcome must reference a prior decision trace' });
      } else {
        const outcome = raw as unknown as FeedbackOutcome;
        outcomesByDecision.set(raw.decisionId, [...(outcomesByDecision.get(raw.decisionId) ?? []), outcome]);
        if (timestamp(raw.observedAt) && timestamp(decision.record.decidedAt)
            && Date.parse(raw.observedAt) < Date.parse(decision.record.decidedAt)) {
          issues.push({ index, recordId: raw.id, code: 'causal_time_inversion', path: `${index}.observedAt`,
            message: 'outcome cannot precede its decision' });
        }
      }
    } else if (raw.kind === 'memory_assertion') {
      for (const [key, expectedKind] of [
        ['supportedByClaimIds', 'feedback_claim'], ['contradictsAssertionIds', 'memory_assertion'],
      ] as const) {
        if (!Array.isArray(raw[key])) continue;
        for (const linkedId of raw[key]) {
          if (typeof linkedId !== 'string') continue;
          const linked = ids.get(linkedId);
          if (!linked || linked.kind !== expectedKind || linked.index >= index) {
            issues.push({ index, recordId: raw.id, code: 'missing_prior_evidence', path: `${index}.${key}`,
              message: `${linkedId} must reference a prior ${expectedKind}` });
          }
        }
      }
    }
  }

  if (issues.length) return { ok: false, issues, counts, learningSamples: [], pendingDecisionIds: [] };
  const learningSamples: FeedbackLearningSample[] = [];
  const pendingDecisionIds: string[] = [];
  for (const decisionId of decisions.keys()) {
    const outcomes = outcomesByDecision.get(decisionId) ?? [];
    const numeric = outcomes.filter(outcome => outcome.reward !== null);
    if (!numeric.length) pendingDecisionIds.push(decisionId);
    else learningSamples.push({ decisionId, feedbackClaimIds: claimsByDecision.get(decisionId) ?? [],
      outcomeIds: numeric.map(outcome => outcome.id) });
  }
  return { ok: true, issues: [], counts, learningSamples, pendingDecisionIds };
}

function checked<T extends FeedbackReplayRecord>(record: T): T {
  const issues = validateRecord(record, 0);
  if (issues.length) throw Error(issues.map(issue => `${issue.path}: ${issue.message}`).join('; '));
  return structuredClone(record);
}

/** Materialize and validate a host-selected action; this function is not a policy. */
export function selectMemoryAction(input: DecisionTraceInput): DecisionTrace {
  return checked({ ...input, kind: 'decision_trace', schema: 1 });
}

/** Materialize a feedback observation without treating it as truth. */
export function observeFeedback(input: FeedbackClaimInput): FeedbackClaim {
  return checked({ ...input, kind: 'feedback_claim', schema: 1 });
}

/** Materialize an assertion separately from its supporting observation. */
export function recordMemoryAssertion(input: MemoryAssertionInput): MemoryAssertion {
  return checked({ ...input, kind: 'memory_assertion', schema: 1 });
}

/** Materialize a delayed result; replay decides whether it is learner-ready. */
export function recordOutcome(input: FeedbackOutcomeInput): FeedbackOutcome {
  return checked({ ...input, kind: 'outcome', schema: 1 });
}
