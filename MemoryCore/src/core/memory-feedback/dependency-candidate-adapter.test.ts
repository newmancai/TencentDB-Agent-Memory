import { describe, expect, it } from 'vitest';
import { selectDependencyCandidates } from './dependency-candidate-adapter.js';

const laterObservation = 'I mailed my diploma last week and started a new job.';
const common = {
  enabled: true,
  laterObservation,
  candidateMemoryIds: ['student-status', 'work-routine'],
  policyVersion: 'dependency-candidate:v1',
};

describe('dependency candidate adapter', () => {
  it('keeps the feature off without inspecting an auxiliary proposal', () => {
    const result = selectDependencyCandidates({ ...common, enabled: false, proposal: null });
    expect(result).toMatchObject({ status: 'off', nominatedMemoryIds: [], reason: null });
    expect(result.decisionLog).toMatchObject({
      mode: 'baseline', auxiliaryPathUsed: false, fallback: false,
      selectedCount: 0, memoryMutationAllowed: false,
    });
  });

  it('nominates deduplicated necessary and possible candidates with exact evidence', () => {
    const result = selectDependencyCandidates({ ...common, proposal: {
      changedBasis: 'Education and work state changed.',
      paths: [
        { candidateMemoryId: 'student-status', affectedOldBasis: 'still a student',
          relation: 'necessary', evidenceQuote: 'mailed my diploma last week', reason: 'degree completed' },
        { candidateMemoryId: 'work-routine', affectedOldBasis: 'old schedule',
          relation: 'possible', evidenceQuote: 'started a new job', reason: 'schedule may change' },
        { candidateMemoryId: 'student-status', affectedOldBasis: 'student state',
          relation: 'possible', evidenceQuote: 'mailed my diploma', reason: 'same candidate' },
      ],
    }});
    expect(result).toMatchObject({
      status: 'selected', nominatedMemoryIds: ['student-status', 'work-routine'], reason: null,
    });
    expect(result.decisionLog).toMatchObject({
      pathCount: 3, selectedCount: 2, necessaryCount: 1, possibleCount: 2,
      memoryMutationAllowed: false,
    });
  });

  it('accepts a none-only proposal as a valid empty selection', () => {
    const result = selectDependencyCandidates({ ...common, proposal: {
      changedBasis: 'No relevant change.',
      paths: [{ candidateMemoryId: 'student-status', affectedOldBasis: '', relation: 'none',
        evidenceQuote: '', reason: 'unrelated' }],
    }});
    expect(result).toMatchObject({ status: 'selected', nominatedMemoryIds: [] });
    expect(result.decisionLog).toMatchObject({ pathCount: 1, selectedCount: 0, fallback: false });
  });

  it.each([
    [{ changedBasis: 'bad id', paths: [{ candidateMemoryId: 'outside', affectedOldBasis: 'x',
      relation: 'necessary', evidenceQuote: 'mailed my diploma', reason: 'x' }] }],
    [{ changedBasis: 'bad quote', paths: [{ candidateMemoryId: 'student-status', affectedOldBasis: 'x',
      relation: 'possible', evidenceQuote: 'not in source', reason: 'x' }] }],
  ])('falls back on an unbound active proposal', proposal => {
    const result = selectDependencyCandidates({ ...common, proposal });
    expect(result).toMatchObject({ status: 'fallback', nominatedMemoryIds: [], reason: 'invalid_selection' });
    expect(result.decisionLog).toMatchObject({ fallback: true, memoryMutationAllowed: false });
  });

  it('falls back on malformed, over-k, and over-capacity inputs', () => {
    const malformed = selectDependencyCandidates({ ...common, proposal: { paths: [] } });
    expect(malformed.reason).toBe('invalid_proposal');

    const overK = selectDependencyCandidates({ ...common, maxSelectedK: 1, proposal: {
      changedBasis: 'two candidates', paths: [
        { candidateMemoryId: 'student-status', affectedOldBasis: 'x', relation: 'necessary',
          evidenceQuote: 'mailed my diploma', reason: 'x' },
        { candidateMemoryId: 'work-routine', affectedOldBasis: 'y', relation: 'possible',
          evidenceQuote: 'started a new job', reason: 'y' },
      ],
    }});
    expect(overK.reason).toBe('invalid_selection');

    const overCapacity = selectDependencyCandidates({ ...common, maxCandidateCount: 1, proposal: {
      changedBasis: '', paths: [],
    }});
    expect(overCapacity.reason).toBe('invalid_config');
  });
});
