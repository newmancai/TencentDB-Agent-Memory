import { describe, expect, it } from 'vitest';

import { bindFeedbackTarget } from '../../benchmarks/support/memory-feedback/target.js';

const decision = {
  candidateMemoryIds: ['memory-1'],
  outputIds: ['answer-1'],
  toolCallIds: ['tool-1'],
};

describe('feedback target binding', () => {
  it('binds a trusted explicit memory reference only inside the candidate set', () => {
    expect(bindFeedbackTarget(decision, { explicitReferences: [
      { targetType: 'memory_assertion', targetId: 'memory-1' },
    ] })).toEqual({ status: 'bound', targetType: 'memory_assertion',
      targetIds: ['memory-1'], reason: 'explicit_reference' });
    expect(bindFeedbackTarget(decision, { explicitReferences: [
      { targetType: 'memory_assertion', targetId: 'foreign' },
    ] })).toMatchObject({ status: 'unknown', reason: 'invalid_reference' });
  });

  it('uses a host reply edge to bind the answer but not its memory cause', () => {
    expect(bindFeedbackTarget(decision, { replyToOutputId: 'answer-1' })).toEqual({
      status: 'bound', targetType: 'answer_span', targetIds: ['answer-1'], reason: 'reply_to_output',
    });
    expect(bindFeedbackTarget(decision, {})).toEqual({
      status: 'unknown', targetType: 'unknown', targetIds: [], reason: 'no_target_evidence',
    });
  });

  it('abstains on foreign reply edges and conflicting explicit targets', () => {
    expect(bindFeedbackTarget(decision, { replyToOutputId: 'other-answer' }))
      .toMatchObject({ status: 'unknown', reason: 'no_target_evidence' });
    expect(bindFeedbackTarget(decision, { explicitReferences: [
      { targetType: 'answer_span', targetId: 'answer-1' },
      { targetType: 'tool_call', targetId: 'tool-1' },
    ] })).toMatchObject({ status: 'unknown', reason: 'conflicting_references' });
  });

  it('deduplicates identical trusted references', () => {
    expect(bindFeedbackTarget(decision, { explicitReferences: [
      { targetType: 'tool_call', targetId: 'tool-1' },
      { targetType: 'tool_call', targetId: 'tool-1' },
    ] })).toMatchObject({ status: 'bound', targetType: 'tool_call', targetIds: ['tool-1'] });
  });
});
