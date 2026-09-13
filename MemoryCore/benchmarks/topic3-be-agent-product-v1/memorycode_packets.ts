#!/usr/bin/env npx tsx
/** Build label-blind MemoryCore retrieval packets plus ordinary/oracle controls. */

import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { currentRules, retrieveSessions, withDialogueStore, type Dialogue } from './memorycode_store.js';

interface Target { instruction_id: number; update_id: number; source_session_id: number }
interface Task {
  id: string; dialogue_id: number; session_count: number; history_class: string;
  target_status: string; eval_query: string; targets: Target[];
}

const arg = (name: string) => {
  const at = process.argv.indexOf(name);
  if (at < 0 || !process.argv[at + 1]) throw Error(`missing ${name}`);
  return process.argv[at + 1];
};

function prompt(dialogue: Dialogue, query: string, body: string) {
  return {
    system: [
      `You are ${dialogue.context.mentee}, a software engineer at ${dialogue.context.company}.`,
      `Your mentor ${dialogue.context.mentor} has given you mandatory coding guidelines.`,
      'Output valid Python code only. Do not explain or provide example usage.',
    ].join(' '),
    user: [
      `This is context from your conversations with ${dialogue.context.mentor}:`,
      body,
      `Based on this information, write a ${query}.`,
      'Follow all latest applicable coding guidelines, including updates.',
    ].join('\n\n'),
  };
}

function fullHistory(dialogue: Dialogue) {
  return dialogue.sessions.map((session, index) => `Session ${index}\n${session.text}`).join('\n\n');
}

async function retrieve(dialogue: Dialogue, task: Task, limit: number, root: string) {
  return withDialogueStore(dialogue, task.dialogue_id, task.id, root,
    store => retrieveSessions(store, dialogue, task.id, task.eval_query, limit));
}

async function main() {
  const datasetRoot = arg('--dataset-root');
  const selectionPath = arg('--selection');
  const output = arg('--output');
  const limit = Number(process.argv.includes('--k') ? arg('--k') : 8);
  if (!Number.isInteger(limit) || limit < 1 || limit > 32) throw Error('k must be in [1, 32]');
  const selection = JSON.parse(await readFile(selectionPath, 'utf8'));
  const topics = JSON.parse(await readFile(join(datasetRoot, 'topics.json'), 'utf8'));
  const temp = await mkdtemp(join(tmpdir(), 'memorycode-packets-'));
  const packets = [];
  try {
    for (const task of selection.selection.tasks as Task[]) {
      const path = join(datasetRoot, 'dataset', `dialogue_${task.dialogue_id}.json`);
      const dialogue: Dialogue = JSON.parse(await readFile(path, 'utf8'));
      const retrieval = await retrieve(dialogue, task, limit, temp);
      const activeRules = currentRules(dialogue, topics);
      const sourceIds = retrieval.selected.map(row => row.session_id);
      const targetSourceIds = [...new Set(task.targets.map(target => target.source_session_id))];
      const common = {
        schema: 1, task_id: task.id, dialogue_id: task.dialogue_id,
        session_count: task.session_count, history_class: task.history_class,
        target_status: task.target_status, eval_query: task.eval_query, targets: task.targets,
        active_rules: activeRules,
      };
      packets.push({
        ...common,
        arms: {
          full_history: {
            mode: 'baseline', ...prompt(dialogue, task.eval_query, fullHistory(dialogue)),
            source_session_ids: dialogue.sessions.map((_, index) => index),
          },
          memorycore_l0: {
            mode: 'enabled',
            ...prompt(dialogue, task.eval_query, retrieval.selected
              .map(row => `Session ${row.session_id}\n${row.content}`).join('\n\n')),
            source_session_ids: sourceIds,
          },
          latest_guidelines_oracle: {
            mode: 'oracle', ...prompt(dialogue, task.eval_query,
              `Latest coding guidelines (privileged evaluation metadata):\n${activeRules.map(rule => `- ${rule.text}`).join('\n')}`),
            injected_rule_source_session_ids: [...new Set(activeRules.map(rule => rule.source_session_id))].sort((a, b) => a - b),
            source_session_ids: targetSourceIds,
          },
        },
        retrieval: {
          k: limit, strategy: retrieval.strategy, candidate_count: dialogue.sessions.length,
          selected_count: retrieval.selected.length, selected_session_ids: sourceIds,
          target_source_session_ids: targetSourceIds,
          target_recall: targetSourceIds.every(id => sourceIds.includes(id)),
          latest_session_forced: true, elapsed_ms: retrieval.elapsed_ms,
          inference_label_fields_used: [],
        },
      });
    }
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, packets.map(packet => JSON.stringify(packet)).join('\n') + '\n');
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}

await main();
