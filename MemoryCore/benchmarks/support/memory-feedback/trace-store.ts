/** Benchmark-only JSONL replay store. */
import { appendFileSync, mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  validateFeedbackReplay,
  type FeedbackReplayRecord,
  type FeedbackReplayResult,
} from './trace.js';

export interface FeedbackTraceStore {
  append(record: FeedbackReplayRecord): void;
  readAll(): FeedbackReplayRecord[];
  replay(): FeedbackReplayResult;
}

/** Explicit, local, single-process append-only ledger for development and shadow use. */
export class JsonlFeedbackTraceStore implements FeedbackTraceStore {
  readonly filePath: string;

  constructor(rootDirectory: string, fileName = 'memory-feedback-trace.v1.jsonl') {
    if (!rootDirectory.trim()) throw Error('Feedback trace root directory is required');
    if (!/^[a-zA-Z0-9._-]+\.jsonl$/.test(fileName)) {
      throw Error('Feedback trace filename must be a plain .jsonl basename');
    }
    mkdirSync(rootDirectory, { recursive: true, mode: 0o700 });
    this.filePath = resolve(rootDirectory, fileName);
    this.readAll();
  }

  append(record: FeedbackReplayRecord): void {
    const current = this.readAll();
    const replay = validateFeedbackReplay([...current, record]);
    if (!replay.ok) throw Error(`Invalid feedback trace append: ${formatIssues(replay)}`);
    appendFileSync(this.filePath, `${JSON.stringify(record)}\n`, { encoding: 'utf8', mode: 0o600 });
  }

  readAll(): FeedbackReplayRecord[] {
    let raw: string;
    try {
      raw = readFileSync(this.filePath, 'utf8');
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    }
    const records = raw.split('\n').filter(Boolean).map((line, index) => {
      try {
        return JSON.parse(line) as FeedbackReplayRecord;
      } catch (error) {
        throw Error(`Malformed feedback trace row ${index + 1}: ${(error as Error).message}`);
      }
    });
    const replay = validateFeedbackReplay(records);
    if (!replay.ok) throw Error(`Invalid feedback trace ledger: ${formatIssues(replay)}`);
    return structuredClone(records);
  }

  replay(): FeedbackReplayResult {
    return validateFeedbackReplay(this.readAll());
  }
}

function formatIssues(replay: FeedbackReplayResult): string {
  return replay.issues.map(issue => `${issue.path} ${issue.code}: ${issue.message}`).join('; ');
}
