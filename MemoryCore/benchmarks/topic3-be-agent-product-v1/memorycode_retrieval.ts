#!/usr/bin/env npx tsx
/** Full-release retrieval regression over every final-history MemoryCode query. */

import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { currentRules, retrieveSessions, withDialogueStore, type Dialogue } from './memorycode_store.js';

const arg = (name: string) => {
  const at = process.argv.indexOf(name);
  if (at < 0 || !process.argv[at + 1]) throw Error(`missing ${name}`);
  return process.argv[at + 1];
};

function quantile(values: number[], probability: number) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const position = (sorted.length - 1) * probability;
  const lower = Math.floor(position), upper = Math.ceil(position);
  return lower === upper ? sorted[lower]
    : sorted[lower] * (upper - position) + sorted[upper] * (position - lower);
}

function distribution(values: number[]) {
  return {
    count: values.length,
    mean: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null,
    p50: quantile(values, .5), p95: quantile(values, .95),
  };
}

function priorSources(dialogue: Dialogue, instructionIds: Set<number>, latest: Set<number>) {
  const sources = new Set<number>();
  for (let sessionId = 0; sessionId < dialogue.instructions.length; sessionId++) {
    const pairs = dialogue.instructions[sessionId];
    if (pairs.length === 1 && pairs[0] === -1) continue;
    for (const [instructionId] of pairs as number[][]) {
      if (instructionIds.has(instructionId) && !latest.has(sessionId)) sources.add(sessionId);
    }
  }
  return [...sources].sort((left, right) => left - right);
}

function group(rows: any[]) {
  const updates = rows.filter(row => row.target_status === 'update');
  return {
    queries: rows.length,
    target_session_recall: rows.filter(row => row.target_recall).length / rows.length,
    selected_sessions: distribution(rows.map(row => row.selected_count)),
    latency_ms: distribution(rows.map(row => row.elapsed_ms)),
    update_queries: updates.length,
    update_stale_collision: updates.length
      ? updates.filter(row => row.stale_collision).length / updates.length : null,
    update_stale_only: updates.length
      ? updates.filter(row => row.stale_only).length / updates.length : null,
  };
}

async function main() {
  const datasetRoot = arg('--dataset-root');
  const output = arg('--output');
  const receiptsOutput = arg('--receipts-output');
  const limit = Number(process.argv.includes('--k') ? arg('--k') : 8);
  if (!Number.isInteger(limit) || limit < 1 || limit > 32) throw Error('k must be in [1, 32]');
  const topics = JSON.parse(await readFile(join(datasetRoot, 'topics.json'), 'utf8'));
  const root = await mkdtemp(join(tmpdir(), 'memorycode-retrieval-'));
  const receipts: any[] = [];
  try {
    for (let dialogueId = 1; dialogueId <= 360; dialogueId++) {
      const dialogue: Dialogue = JSON.parse(
        await readFile(join(datasetRoot, 'dataset', `dialogue_${dialogueId}.json`), 'utf8'),
      );
      const rules = currentRules(dialogue, topics);
      const queries = dialogue.sessions.at(-1)?.history_eval_query ?? [];
      const owner = `memorycode-full-${dialogueId}`;
      await withDialogueStore(dialogue, dialogueId, owner, root, async store => {
        for (const query of queries) {
          const targets = rules.filter(rule => rule.eval_query === query);
          if (!targets.length) throw Error(`unmapped query in dialogue ${dialogueId}: ${query}`);
          const result = await retrieveSessions(store, dialogue, owner, query, limit);
          const selected = result.selected.map(row => row.session_id);
          const latestSources = new Set<number>(targets.map(rule => rule.source_session_id));
          const oldSources = priorSources(
            dialogue, new Set(targets.map(rule => rule.instruction_id)), latestSources,
          );
          const recalled = [...latestSources].every(sessionId => selected.includes(sessionId));
          const staleCollision = oldSources.some(sessionId => selected.includes(sessionId));
          receipts.push({
            schema: 1, dialogue_id: dialogueId, session_count: dialogue.sessions.length,
            history_class: dialogueId <= 210 ? 'short' : 'long', query,
            target_status: targets.some(rule => rule.occurrence > 1) ? 'update' : 'add',
            target_object_types: [...new Set(targets.map(rule => rule.object_type))].sort(),
            target_source_session_ids: [...latestSources].sort((left, right) => left - right),
            prior_target_source_session_ids: oldSources,
            target_age_sessions: Math.max(...[...latestSources].map(id => dialogue.sessions.length - 1 - id)),
            selected_session_ids: selected, selected_count: selected.length,
            target_recall: recalled, stale_collision: staleCollision,
            stale_only: !recalled && staleCollision, strategy: result.strategy,
            elapsed_ms: result.elapsed_ms, k: limit, latest_session_forced: true,
            inference_label_fields_used: [],
          });
        }
      });
    }
    const lines = receipts.map(receipt => JSON.stringify(receipt)).join('\n') + '\n';
    await mkdir(dirname(receiptsOutput), { recursive: true });
    await writeFile(receiptsOutput, lines);
    const by = (field: string) => Object.fromEntries(
      [...new Set(receipts.map(row => String(row[field])))].sort((left, right) => left.localeCompare(right, undefined, { numeric: true }))
        .map(value => [value, group(receipts.filter(row => String(row[field]) === value))]),
    );
    const objectRows = receipts.flatMap(row => row.target_object_types.map((objectType: string) => ({ ...row, object_type: objectType })));
    const summary = {
      schema: 1, protocol: 'topic3-be-memorycode-full-retrieval-v1', status: 'pass',
      dataset: {
        name: 'CohereLabsCommunity/MemoryCode', dialogues: 360,
        source_commit: '1ab87e119b2f9a498de8075219e1c07f6041b394',
        hf_revision: '32d888b11c73c67be91414e571dfe98c5c20feac',
      },
      configuration: {
        layer: 'raw session chunks in MemoryCore L1', index: 'native SQLite FTS5', k: limit,
        latest_session_forced: true, retrieval_inputs: ['session.text', 'eval_query'],
        scoring_only_fields: ['instructions', 'topics.eval_query', 'topics.regex'],
        capacity: 'at most k records per query; one SQLite store per dialogue',
      },
      independent_dialogue_clusters: 360, ...group(receipts),
      by_history_class: by('history_class'), by_session_count: by('session_count'),
      by_target_status: by('target_status'),
      by_target_object: Object.fromEntries(
        [...new Set(objectRows.map(row => row.object_type))].sort()
          .map(objectType => [objectType, group(objectRows.filter(row => row.object_type === objectType))]),
      ),
      receipts: {
        rows: receipts.length, bytes: Buffer.byteLength(lines),
        sha256: createHash('sha256').update(lines).digest('hex'),
        committed: false, regeneration: 'memorycode_retrieval.ts with the pinned public dataset',
      },
    };
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, JSON.stringify(summary, null, 2) + '\n');
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

await main();
