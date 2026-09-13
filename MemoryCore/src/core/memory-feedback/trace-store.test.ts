import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { JsonlFeedbackTraceStore } from './trace-store.js';
import { recordOutcome, selectMemoryAction } from './trace.js';

const decision = () => selectMemoryAction({
  id: 'decision-store-1', contextId: 'context-1', taskId: 'task-1',
  contextEventIds: ['request-1'], candidateMemoryIds: ['memory-1'],
  action: 'include', selectedMemoryIds: ['memory-1'], policyVersion: 'deterministic:v1',
  propensity: 1, decidedAt: '2026-09-13T00:00:00.000Z',
  promptMemorySpans: [{ memoryId: 'memory-1', start: 0, end: 8 }],
  outputIds: ['answer-1'], toolCallIds: [],
});

describe('JSONL feedback trace store', () => {
  it('persists and replays a learner-ready decision across restart', () => {
    const root = mkdtempSync(join(tmpdir(), 'tdai-feedback-trace-'));
    try {
      const store = new JsonlFeedbackTraceStore(root);
      const selected = decision();
      store.append(selected);
      store.append(recordOutcome({
        id: 'outcome-store-1', decisionId: selected.id, result: 'success', reward: 1,
        metrics: { checkerPass: true }, source: 'development-checker',
        observedAt: '2026-09-13T00:01:00.000Z', delayed: false,
      }));
      expect(new JsonlFeedbackTraceStore(root).replay()).toMatchObject({
        ok: true,
        learningSamples: [{ decisionId: selected.id, outcomeIds: ['outcome-store-1'] }],
      });
      expect(readFileSync(store.filePath, 'utf8').trim().split('\n')).toHaveLength(2);
      expect(() => store.append(selected)).toThrow('duplicate_record_id');
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('rejects an outcome without a prior decision before writing it', () => {
    const root = mkdtempSync(join(tmpdir(), 'tdai-feedback-trace-'));
    try {
      const store = new JsonlFeedbackTraceStore(root);
      expect(() => store.append(recordOutcome({
        id: 'orphan-outcome', decisionId: 'missing', result: 'failure', reward: 0,
        metrics: {}, source: 'development-checker',
        observedAt: '2026-09-13T00:01:00.000Z', delayed: false,
      }))).toThrow('missing_prior_decision');
      expect(store.readAll()).toEqual([]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});
