import { describe, expect, it } from 'vitest';

import { matchMemoryScope } from '../../benchmarks/support/memory-feedback/scope.js';

describe('exact memory scope baseline', () => {
  const scope = { project: 'atlas', environment: 'staging', write: true } as const;

  it('includes only when every scope condition matches', () => {
    expect(matchMemoryScope(scope, {
      project: 'atlas', environment: 'staging', write: true, region: 'eu',
    })).toEqual({
      status: 'match', action: 'include',
      matchedKeys: ['project', 'environment', 'write'], conflictingKeys: [], missingKeys: [],
      reason: 'exact_match',
    });
  });

  it('omits on a known conflict even when another field is missing', () => {
    expect(matchMemoryScope(scope, { project: 'juniper', write: true })).toMatchObject({
      status: 'mismatch', action: 'omit', conflictingKeys: ['project'],
      missingKeys: ['environment'], reason: 'conflict',
    });
  });

  it('asks instead of guessing when context is missing', () => {
    expect(matchMemoryScope(scope, { project: 'atlas', write: true })).toMatchObject({
      status: 'unknown', action: 'ask', missingKeys: ['environment'], reason: 'missing_context',
    });
  });

  it('keeps legacy free-text scopes explicit but non-actionable', () => {
    expect(matchMemoryScope('project=atlas', { project: 'atlas' })).toMatchObject({
      status: 'unknown', action: 'ask', reason: 'unstructured_scope',
    });
  });

  it.each([{}, { project: Number.NaN }, []])('rejects invalid predicate %j', (value) => {
    expect(() => matchMemoryScope(value as never, { project: 'atlas' })).toThrow();
  });
});
