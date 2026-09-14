#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('../scripts/project-agent/project_agent.py', import.meta.url));
const child = spawn(
  process.env.MEMORY_AGENT_PYTHON || 'python3',
  [script, ...process.argv.slice(2)],
  {
    stdio: 'inherit',
    env: { ...process.env, MEMORY_AGENT_NODE: process.execPath },
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
