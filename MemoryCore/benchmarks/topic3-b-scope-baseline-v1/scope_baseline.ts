/** Exact structured-scope component check; no model or external service. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import {
  JsonlFeedbackTraceStore,
  matchMemoryScope,
  recordMemoryAssertion,
  recordOutcome,
  selectMemoryAction,
  type ScopeMatchResult,
  type ScopePredicate,
} from '../support/memory-feedback/index.js';

const [output] = process.argv.slice(2);
assert(output, 'usage: tsx scope_baseline.ts OUTPUT_DIRECTORY');
await mkdir(output);

const cases: { id: string; scope: ScopePredicate; match: ScopePredicate;
  conflict: ScopePredicate; missing: ScopePredicate }[] = [
  { id: 'project-env', scope: { project: 'atlas', environment: 'staging' },
    match: { project: 'atlas', environment: 'staging', region: 'eu' },
    conflict: { project: 'atlas', environment: 'production' }, missing: { project: 'atlas' } },
  { id: 'language-runtime', scope: { language: 'python', runtime: 'cpython-3.13' },
    match: { language: 'python', runtime: 'cpython-3.13' },
    conflict: { language: 'rust', runtime: 'cpython-3.13' }, missing: { language: 'python' } },
  { id: 'audience-channel', scope: { audience: 'internal', channel: 'incident' },
    match: { audience: 'internal', channel: 'incident', severity: 2 },
    conflict: { audience: 'external', channel: 'incident' }, missing: { audience: 'internal' } },
  { id: 'operation-resource', scope: { operation: 'write', resource: 'invoice' },
    match: { operation: 'write', resource: 'invoice' },
    conflict: { operation: 'read', resource: 'invoice' }, missing: { operation: 'write' } },
  { id: 'jurisdiction-data', scope: { jurisdiction: 'EU', dataClass: 'personal' },
    match: { jurisdiction: 'EU', dataClass: 'personal' },
    conflict: { jurisdiction: 'US', dataClass: 'personal' }, missing: { jurisdiction: 'EU' } },
  { id: 'format-consumer', scope: { format: 'json', consumer: 'machine' },
    match: { format: 'json', consumer: 'machine' },
    conflict: { format: 'yaml', consumer: 'machine' }, missing: { format: 'json' } },
  { id: 'tenant-region', scope: { tenant: 'northwind', region: 'ap-south-2' },
    match: { tenant: 'northwind', region: 'ap-south-2' },
    conflict: { tenant: 'contoso', region: 'ap-south-2' }, missing: { tenant: 'northwind' } },
  { id: 'release-branch', scope: { release: 'v3', branch: 'stable' },
    match: { release: 'v3', branch: 'stable' },
    conflict: { release: 'v2', branch: 'stable' }, missing: { release: 'v3' } },
];

const ledger = new JsonlFeedbackTraceStore(output);
const rows: (ScopeMatchResult & {
  id: string;
  variant: 'match' | 'conflict' | 'missing';
  expected: 'include' | 'omit' | 'ask';
  correct: boolean;
})[] = [];
for (const item of cases) {
  const assertion = recordMemoryAssertion({
    id: `${item.id}:assertion`, subject: item.id, predicate: 'policy', value: 'enabled',
    scope: item.scope, validFrom: null, validTo: null,
    recordedAt: '2026-09-13T00:00:00.000Z', supersededAt: null,
    status: 'verified', authority: 'tool_readback', sourceEventIds: [`${item.id}:source`],
    supportedByClaimIds: [], contradictsAssertionIds: [],
  });
  ledger.append(assertion);
  for (const [variant, context, expected] of [
    ['match', item.match, 'include'], ['conflict', item.conflict, 'omit'], ['missing', item.missing, 'ask'],
  ] as const) {
    const result = matchMemoryScope(assertion.scope, context);
    const correct = result.action === expected;
    const decision = selectMemoryAction({
      id: `${item.id}:${variant}:decision`, contextId: `${item.id}:${variant}`,
      taskId: `${item.id}:scope-check`, contextEventIds: [`${item.id}:${variant}:context`],
      candidateMemoryIds: [assertion.id], action: result.action,
      selectedMemoryIds: result.action === 'include' ? [assertion.id] : [],
      policyVersion: 'exact-scope-conjunction:v1', propensity: 1,
      decidedAt: '2026-09-13T00:01:00.000Z', promptMemorySpans: [],
      outputIds: [`${item.id}:${variant}:scope-result`], toolCallIds: [],
    });
    ledger.append(decision);
    ledger.append(recordOutcome({
      id: `${item.id}:${variant}:outcome`, decisionId: decision.id,
      result: correct ? 'success' : 'failure', reward: correct ? 1 : 0,
      metrics: { expected, actual: result.action, status: result.status },
      source: 'exact-scope-component-checker', observedAt: '2026-09-13T00:02:00.000Z', delayed: false,
    }));
    rows.push({ id: item.id, variant, expected, ...result, correct });
  }
}
const replay = ledger.replay();
assert(replay.ok);
const summary = {
  protocol: 'topic3-b-exact-scope-baseline-v1',
  cases: cases.length,
  decisions: rows.length,
  correct: rows.filter(row => row.correct).length,
  byVariant: Object.fromEntries(['match', 'conflict', 'missing'].map(variant => {
    const selected = rows.filter(row => row.variant === variant);
    return [variant, { correct: selected.filter(row => row.correct).length, total: selected.length }];
  })),
  replay,
  scope: 'Synthetic exact scalar predicates. Tests deterministic scope application only; not natural-language scope extraction, target binding, or downstream model gain.',
};
await writeFile(join(output, 'rows.jsonl'), rows.map(row => JSON.stringify(row)).join('\n') + '\n');
await writeFile(join(output, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary));
