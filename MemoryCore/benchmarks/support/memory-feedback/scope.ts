/** Deterministic scope baseline used by feedback experiments. */
export type ScopeScalar = null | boolean | number | string;
export type ScopePredicate = Readonly<Record<string, ScopeScalar>>;
export type FeedbackScope = string | ScopePredicate;

export interface ScopeMatchResult {
  status: 'match' | 'mismatch' | 'unknown';
  action: 'include' | 'omit' | 'ask';
  matchedKeys: readonly string[];
  conflictingKeys: readonly string[];
  missingKeys: readonly string[];
  reason: 'exact_match' | 'conflict' | 'missing_context' | 'unstructured_scope';
}

function validScalar(value: unknown): value is ScopeScalar {
  return value === null || typeof value === 'string' || typeof value === 'boolean'
    || (typeof value === 'number' && Number.isFinite(value));
}

export function assertScopePredicate(value: unknown, name = 'scope predicate'): asserts value is ScopePredicate {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error(`${name} must be an object`);
  const entries = Object.entries(value);
  if (!entries.length || entries.some(([key, item]) => !key.trim() || !validScalar(item))) {
    throw Error(`${name} must contain non-empty keys and finite scalar values`);
  }
}

/** High-precision baseline: exact conjunction, abstaining on missing context. */
export function matchMemoryScope(scope: FeedbackScope, context: ScopePredicate): ScopeMatchResult {
  assertScopePredicate(context, 'scope context');
  if (typeof scope === 'string') {
    if (!scope.trim()) throw Error('scope must be non-empty');
    return { status: 'unknown', action: 'ask', matchedKeys: [], conflictingKeys: [], missingKeys: [],
      reason: 'unstructured_scope' };
  }
  assertScopePredicate(scope);
  const matchedKeys: string[] = [], conflictingKeys: string[] = [], missingKeys: string[] = [];
  for (const [key, expected] of Object.entries(scope)) {
    if (!Object.prototype.hasOwnProperty.call(context, key)) missingKeys.push(key);
    else if (context[key] === expected) matchedKeys.push(key);
    else conflictingKeys.push(key);
  }
  if (conflictingKeys.length) {
    return { status: 'mismatch', action: 'omit', matchedKeys, conflictingKeys, missingKeys, reason: 'conflict' };
  }
  if (missingKeys.length) {
    return { status: 'unknown', action: 'ask', matchedKeys, conflictingKeys, missingKeys,
      reason: 'missing_context' };
  }
  return { status: 'match', action: 'include', matchedKeys, conflictingKeys, missingKeys,
    reason: 'exact_match' };
}
