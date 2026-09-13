export type DependencyCandidateRelation = 'necessary' | 'possible' | 'none';

export interface DependencyCandidatePath {
  candidateMemoryId: string;
  affectedOldBasis: string;
  relation: DependencyCandidateRelation;
  evidenceQuote: string;
  reason: string;
}

export interface DependencyCandidateProposal {
  changedBasis: string;
  paths: readonly DependencyCandidatePath[];
}

export type DependencyCandidateStatus = 'off' | 'selected' | 'fallback';

export interface DependencyCandidateDecisionLog {
  schema: 1;
  feature: 'dependency_candidate_expansion';
  mode: 'baseline' | 'enabled';
  status: DependencyCandidateStatus;
  policyVersion: string;
  signalType: 'later_observation';
  k: number;
  candidateCount: number;
  pathCount: number;
  selectedCount: number;
  necessaryCount: number;
  possibleCount: number;
  auxiliaryPathUsed: boolean;
  fallback: boolean;
  fallbackReason: 'invalid_config' | 'invalid_proposal' | 'invalid_selection' | null;
  memoryMutationAllowed: false;
  elapsedMs: number;
}

export interface DependencyCandidateResult {
  /** Candidates to retrieve or verify; never an instruction to mutate them. */
  nominatedMemoryIds: readonly string[];
  status: DependencyCandidateStatus;
  reason: DependencyCandidateDecisionLog['fallbackReason'];
  decisionLog: DependencyCandidateDecisionLog;
}

function isPath(value: unknown): value is DependencyCandidatePath {
  if (!value || typeof value !== 'object') return false;
  const path = value as Record<string, unknown>;
  return typeof path.candidateMemoryId === 'string'
    && typeof path.affectedOldBasis === 'string'
    && (path.relation === 'necessary' || path.relation === 'possible' || path.relation === 'none')
    && typeof path.evidenceQuote === 'string'
    && typeof path.reason === 'string';
}

function parseProposal(value: unknown): DependencyCandidateProposal | null {
  if (!value || typeof value !== 'object') return null;
  const proposal = value as Record<string, unknown>;
  if (typeof proposal.changedBasis !== 'string' || !Array.isArray(proposal.paths)
      || !proposal.paths.every(isPath)) return null;
  return { changedBasis: proposal.changedBasis, paths: proposal.paths };
}

/**
 * Turn an already-computed dependency proposal into a bounded verification set.
 *
 * The caller owns retrieval and proposal generation. This adapter deliberately
 * has no memory-write handle: selected IDs may only be fetched or verified by a
 * later stage. Off and failure both produce an empty additive set.
 */
export function selectDependencyCandidates(p: {
  enabled: boolean;
  laterObservation: string;
  candidateMemoryIds: readonly string[];
  proposal: unknown;
  policyVersion: string;
  maxSelectedK?: number;
  maxCandidateCount?: number;
  maxPathCount?: number;
}): DependencyCandidateResult {
  const started = performance.now();
  const k = p.maxSelectedK ?? 8;
  const candidateLimit = p.maxCandidateCount ?? 64;
  const pathLimit = p.maxPathCount ?? 16;
  const uniqueCandidates = new Set(p.candidateMemoryIds);
  const validConfig = Number.isInteger(k) && k >= 1 && k <= 32
    && Number.isInteger(candidateLimit) && candidateLimit >= 1 && candidateLimit <= 256
    && Number.isInteger(pathLimit) && pathLimit >= 1 && pathLimit <= 64
    && typeof p.policyVersion === 'string' && !!p.policyVersion.trim()
    && typeof p.laterObservation === 'string' && !!p.laterObservation.trim()
    && p.candidateMemoryIds.length === uniqueCandidates.size
    && p.candidateMemoryIds.length <= candidateLimit
    && p.candidateMemoryIds.every(id => typeof id === 'string' && !!id.trim());

  let status: DependencyCandidateStatus = 'selected';
  let reason: DependencyCandidateDecisionLog['fallbackReason'] = null;
  let paths: readonly DependencyCandidatePath[] = [];
  let nominatedMemoryIds: string[] = [];

  if (!p.enabled) {
    status = 'off';
  } else if (!validConfig) {
    status = 'fallback';
    reason = 'invalid_config';
  } else {
    const proposal = parseProposal(p.proposal);
    if (!proposal || proposal.paths.length > pathLimit) {
      status = 'fallback';
      reason = 'invalid_proposal';
    } else {
      paths = proposal.paths;
      const active = paths.filter(path => path.relation !== 'none');
      const activeIsBounded = active.every(path => uniqueCandidates.has(path.candidateMemoryId)
        && !!path.affectedOldBasis.trim()
        && !!path.evidenceQuote
        && p.laterObservation.includes(path.evidenceQuote));
      nominatedMemoryIds = [...new Set(active.map(path => path.candidateMemoryId))];
      if (!activeIsBounded || nominatedMemoryIds.length > k) {
        status = 'fallback';
        reason = 'invalid_selection';
        nominatedMemoryIds = [];
      }
    }
  }

  const necessaryCount = status === 'selected'
    ? paths.filter(path => path.relation === 'necessary').length : 0;
  const possibleCount = status === 'selected'
    ? paths.filter(path => path.relation === 'possible').length : 0;
  const decisionLog: DependencyCandidateDecisionLog = {
    schema: 1,
    feature: 'dependency_candidate_expansion',
    mode: p.enabled ? 'enabled' : 'baseline',
    status,
    policyVersion: p.policyVersion,
    signalType: 'later_observation',
    k,
    candidateCount: p.candidateMemoryIds.length,
    pathCount: status === 'selected' ? paths.length : 0,
    selectedCount: nominatedMemoryIds.length,
    necessaryCount,
    possibleCount,
    auxiliaryPathUsed: p.enabled,
    fallback: status === 'fallback',
    fallbackReason: reason,
    memoryMutationAllowed: false,
    elapsedMs: performance.now() - started,
  };
  return { nominatedMemoryIds, status, reason, decisionLog };
}
