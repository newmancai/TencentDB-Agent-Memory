import type { FeedbackClaim, MemoryAssertion } from './trace.js';

export type FeedbackAssertionProposal =
  | { action: 'propose'; evidence_quote: string; proposition: string; scope: 'current_interaction' }
  | { action: 'abstain'; evidence_quote: ''; proposition: ''; scope: 'none' };

export interface FeedbackAssertionCandidateInput {
  id: string;
  recordedAt: string;
}

/**
 * Fail-closed boundary between an untrusted semantic extractor and assertion state.
 * The result is always a current-interaction candidate; this function never verifies
 * or promotes durable memory.
 */
export function compileFeedbackAssertionCandidate(
  claim: FeedbackClaim,
  proposal: FeedbackAssertionProposal,
  input: FeedbackAssertionCandidateInput,
): MemoryAssertion | null {
  if (proposal.action === 'abstain') {
    if (proposal.evidence_quote !== '' || proposal.proposition !== '' || proposal.scope !== 'none') {
      throw Error('An abstention must not carry assertion content or scope');
    }
    return null;
  }
  if (claim.decisionId === null || claim.targetType !== 'answer_span' || claim.targetIds.length !== 1) {
    throw Error('A candidate correction requires one answer target bound to a decision');
  }
  if (claim.authority !== 'explicit_user') {
    throw Error('A candidate correction requires explicit user authority');
  }
  if (!proposal.evidence_quote.trim() || !claim.claimText.includes(proposal.evidence_quote)) {
    throw Error('Candidate evidence must be a nonempty verbatim span of the feedback claim');
  }
  if (!proposal.proposition.trim()) throw Error('Candidate proposition is required');
  if (proposal.scope !== 'current_interaction' || claim.scope !== 'current interaction') {
    throw Error('Raw correction candidates must remain scoped to the current interaction');
  }
  if (!input.id.trim() || !Number.isFinite(Date.parse(input.recordedAt))) {
    throw Error('Candidate id and recordedAt timestamp are required');
  }
  return {
    kind: 'memory_assertion', schema: 1, id: input.id,
    subject: claim.targetIds[0], predicate: 'explicit_user_correction',
    value: { proposition: proposal.proposition, evidenceQuote: proposal.evidence_quote },
    scope: claim.scope, validFrom: claim.observedAt, validTo: null,
    recordedAt: input.recordedAt, supersededAt: null, status: 'candidate',
    authority: 'explicit_user', sourceEventIds: [...claim.sourceEventIds],
    supportedByClaimIds: [claim.id], contradictsAssertionIds: [],
  };
}
