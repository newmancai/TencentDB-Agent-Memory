import { readFile, writeFile } from 'node:fs/promises';

import { validateFeedbackReplay } from '../../src/core/memory-feedback/trace.js';

const [input, output] = process.argv.slice(2);
if (!input) throw Error('usage: tsx replay_trace.ts INPUT_JSONL [OUTPUT_JSON]');
const raw = await readFile(input, 'utf8');
const records = raw.split('\n').filter(Boolean).map((line, index) => {
  try { return JSON.parse(line); }
  catch (error) { throw Error(`Malformed replay row ${index + 1}: ${(error as Error).message}`); }
});
const replay = validateFeedbackReplay(records);
const rendered = JSON.stringify(replay, null, 2) + '\n';
if (output) await writeFile(output, rendered);
process.stdout.write(rendered);
if (!replay.ok) process.exitCode = 1;
