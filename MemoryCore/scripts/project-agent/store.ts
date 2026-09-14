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
      const snapshot = await memory.snapshot();
      const options = request.options
        ? {
            ...request.options,
            beforeOrder: (snapshot.observations.at(-1)?.order ?? 0) + 1,
          }
        : null;
      const selection =
        options && snapshot.constraints.length ? await memory.context(options) : null;
      result = { snapshot, selection };
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
