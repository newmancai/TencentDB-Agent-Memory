/** Reopen completed native stores in a fresh process; no model or label access. */
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { FeedbackMemory } from '../../src/core/memory-feedback/index.js';
const [prepared, results, output] = process.argv.slice(2);
const tasks = JSON.parse(await readFile(prepared, 'utf8'));
const prior = new Map((await readFile(results, 'utf8')).trim().split('\n').map(s => { const r = JSON.parse(s); return [r.id, r]; }));
const checks = [];
for (const t of tasks) {
  const base = new VectorStore(join(t.directory, 'base.sqlite'), 0); base.init();
  try {
    for (const mode of ['base', 'fixed', 'adaptive']) {
      const root = join(t.directory, mode === 'base' ? 'fixed' : mode);
      const aux = new VectorStore(join(root, 'aux.sqlite'), 0); aux.init();
      try {
        const view = new FeedbackMemory(t.owner, root, base, aux);
        const read = await view.search(t.query, { enabled: mode !== 'base' });
        const expected = prior.get(t.id)?.arms[mode].read.result;
        checks.push({ id: t.id, mode, pass: !read.fallback && JSON.stringify(read.result) === JSON.stringify(expected) });
      } finally { aux.close(); }
    }
  } finally { base.close(); }
}
const result = { checks: checks.length, passed: checks.filter(c => c.pass).length, details: checks };
await writeFile(output, JSON.stringify(result, null, 2));
console.log(JSON.stringify({ checks: result.checks, passed: result.passed }));
if (result.passed !== result.checks) process.exitCode = 1;
