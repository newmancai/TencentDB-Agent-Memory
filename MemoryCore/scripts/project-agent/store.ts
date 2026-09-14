/** JSON stdin/stdout bridge; the Python host serializes processes with a file lock. */
import { readFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { ProjectMemory } from '../../src/core/memory-feedback/project-memory.js';

const request = JSON.parse(readFileSync(0, 'utf8'));
mkdirSync(dirname(request.database), { recursive: true });
const store = new VectorStore(request.database, 0);
store.init();
try {
  const memory = new ProjectMemory(store, request.owner, request.project);
  const loadRequestedContext = async () => {
    if (request.options) return memory.loadContext(request.options);
    return { snapshot: await memory.snapshot(), selection: null };
  };
  let result: unknown;
  switch (request.operation) {
    case 'snapshot':
      result = await memory.snapshot();
      break;
    case 'ingest':
      result = await memory.ingest(request.observation, request.proposals);
      break;
    case 'retract':
      result = await memory.retract(request.constraintId, request.observation);
      break;
    case 'context':
      result = await memory.context(request.options);
      break;
    case 'loadContext': {
      result = await loadRequestedContext();
      break;
    }
    case 'prepareRun': {
      const loaded = await loadRequestedContext();
      const lastOrder = loaded.snapshot.observations.at(-1)?.order ?? 0;
      // Keep the host's canonical field order because raw fallback is byte-visible prompt data.
      const observation = {
        id: request.observation.id,
        order: lastOrder + 1,
        role: request.observation.role,
        text: request.observation.text,
      };
      let ingest: unknown = null;
      let taskError: string | null = null;
      try {
        ingest = await memory.ingest(observation, []);
      } catch (error) {
        // Context loading succeeded. Preserve it even when the task write fails.
        taskError = String(error);
      }
      result = { ...loaded, task: { observation, ingest, error: taskError } };
      break;
    }
    default:
      throw Error('unknown project memory operation');
  }
  process.stdout.write(JSON.stringify({ ok: true, result }) + '\n');
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(error) }) + '\n');
  process.exitCode = 1;
} finally {
  store.close();
}
