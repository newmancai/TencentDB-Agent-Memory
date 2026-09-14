/** Minimal public-data adapter over MemoryCore's existing SQLite/FTS path. */

import { performance } from 'node:perf_hooks';
import { join } from 'node:path';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { executeMemorySearch } from '../../src/core/tools/memory-search.js';
import type { MemoryRecord } from '../../src/core/record/l1-writer.js';

export interface DialogueSession {
  type: string[]; topic: Array<string | null>; text: string;
  history_eval_query?: string[];
}
export interface Dialogue {
  context: { mentor: string; mentee: string; company: string };
  instructions: Array<Array<number[] | number>>;
  sessions: DialogueSession[];
}

export function currentRules(dialogue: Dialogue, topics: any) {
  const latest = new Map<number, { updateId: number; sourceSessionId: number; occurrence: number }>();
  const occurrences = new Map<number, number>();
  for (let sourceSessionId = 0; sourceSessionId < dialogue.instructions.length; sourceSessionId++) {
    const pairs = dialogue.instructions[sourceSessionId];
    if (pairs.length === 1 && pairs[0] === -1) continue;
    for (const [instructionId, updateId] of pairs as number[][]) {
      const occurrence = (occurrences.get(instructionId) ?? 0) + 1;
      occurrences.set(instructionId, occurrence);
      latest.set(instructionId, { updateId, sourceSessionId, occurrence });
    }
  }
  const byId = new Map<number, any>(topics.instructions.map((item: any) => [item.id, item]));
  return [...latest.entries()].sort(([left], [right]) => left - right).map(([instructionId, state]) => ({
    instruction_id: instructionId, update_id: state.updateId, occurrence: state.occurrence,
    source_session_id: state.sourceSessionId, eval_query: byId.get(instructionId).eval_query,
    text: byId.get(instructionId).text[state.updateId],
    object_type: byId.get(instructionId).regex[state.updateId][0],
    regex: byId.get(instructionId).regex[state.updateId][1],
  }));
}

export async function withDialogueStore<T>(
  dialogue: Dialogue, dialogueId: number, owner: string, root: string,
  work: (store: VectorStore) => Promise<T>,
) {
  const store = new VectorStore(join(root, `${owner}.sqlite`), 0);
  store.init();
  try {
    const base = {
      type: 'episodic', priority: 50, scene_name: 'memorycode-session',
      source_message_ids: [] as string[], metadata: {}, timestamps: [] as string[],
      createdAt: '2025-01-01T00:00:00.000Z', updatedAt: '2025-01-01T00:00:00.000Z',
      version: 1, sessionKey: owner, sessionId: owner, userId: owner,
      agentId: 'memorycode-adapter', taskId: owner,
    };
    for (let index = 0; index < dialogue.sessions.length; index++) {
      const record: MemoryRecord = {
        ...base, id: `${owner}:session:${index}`, content: dialogue.sessions[index].text,
        source_message_ids: [`dialogue_${dialogueId}:session:${index}`],
      };
      if (!await store.upsertL1(record, undefined)) throw Error('MemoryCore L1 write failed');
    }
    return await work(store);
  } finally {
    store.close();
  }
}

export async function retrieveSessions(
  store: VectorStore, dialogue: Dialogue, owner: string, query: string, limit: number,
) {
  const started = performance.now();
  const result = await executeMemorySearch({ query, limit, vectorStore: store, filter: { userId: owner } });
  const elapsedMs = performance.now() - started;
  const selected = result.results.map(row => ({
    id: row.id, session_id: Number(row.id.slice(row.id.lastIndexOf(':') + 1)),
    content: row.content, score: row.score,
  }));
  const latest = dialogue.sessions.length - 1;
  if (!selected.some(row => row.session_id === latest)) {
    if (selected.length >= limit) selected.pop();
    selected.push({
      id: `${owner}:session:${latest}`, session_id: latest,
      content: dialogue.sessions[latest].text, score: 0,
    });
  }
  selected.sort((left, right) => left.session_id - right.session_id);
  return { selected, strategy: result.strategy, elapsed_ms: elapsedMs };
}
