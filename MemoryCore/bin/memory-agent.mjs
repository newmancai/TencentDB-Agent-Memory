#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('../scripts/project-agent/project_agent.py', import.meta.url));
const storeBundle = fileURLToPath(new URL('../dist/project-agent-store.mjs', import.meta.url));
const childEnv = { ...process.env, MEMORY_AGENT_NODE: process.execPath };
if (!childEnv.MEMORY_AGENT_STORE_BUNDLE && existsSync(storeBundle)) {
  childEnv.MEMORY_AGENT_STORE_BUNDLE = storeBundle;
}
const child = spawn(
  process.env.MEMORY_AGENT_PYTHON || 'python3',
  [script, ...process.argv.slice(2)],
  {
    stdio: 'inherit',
    env: childEnv,
  },
);
child.on('error', (error) => {
  process.stderr.write(`memory-agent: ${error.message}. Python 3.10+ is required.\n`);
  process.exitCode = 1;
});
// Forward cancellation so the Python host can stop its separate agent process group.
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill('SIGINT'));
}
child.on('exit', (code, signal) => {
  process.exitCode = code ?? (signal ? 130 : 1);
});
