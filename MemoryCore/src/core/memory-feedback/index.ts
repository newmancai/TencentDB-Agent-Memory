export { FeedbackMemory, verifyBounded, validateCandidate, replacementContent } from './lifecycle.js';
export type { Candidate, SourceRecord } from './lifecycle.js';
export { FeedbackPolicy } from './policy.js';
export type { PolicyState, Relation, Verification } from './policy.js';
export { processFeedback } from './process.js';
export { selectAnswerFeedback, parseAnswerFeedback } from './answer-feedback.js';
export type { AnswerFeedbackObservation, AnswerFeedbackResult } from './answer-feedback.js';
export { runAnswerFeedbackAdapter } from './answer-feedback-adapter.js';
export type {
  AnswerFeedbackAdapterResult,
  AnswerFeedbackDecisionLog,
} from './answer-feedback-adapter.js';
export {
  observeFeedback,
  recordMemoryAssertion,
  recordOutcome,
  selectMemoryAction,
  validateFeedbackReplay,
} from './trace.js';
export type {
  AssertionStatus,
  DecisionTrace,
  DecisionTraceInput,
  FeedbackAuthority,
  FeedbackClaim,
  FeedbackClaimInput,
  FeedbackLearningSample,
  FeedbackObservationType,
  FeedbackOutcome,
  FeedbackOutcomeInput,
  FeedbackReplayIssue,
  FeedbackReplayRecord,
  FeedbackReplayResult,
  FeedbackTargetType,
  JsonValue,
  MemoryAction,
  MemoryAssertion,
  MemoryAssertionInput,
  OutcomeResult,
  PromptMemorySpan,
  TraceCost,
} from './trace.js';
export { JsonlFeedbackTraceStore } from './trace-store.js';
export type { FeedbackTraceStore } from './trace-store.js';
export { decisionTraceFromRecallObservation } from './recall-trace-adapter.js';
export type { RecallDecisionTraceInput } from './recall-trace-adapter.js';
export { assertScopePredicate, matchMemoryScope } from './scope.js';
export type { FeedbackScope, ScopeMatchResult, ScopePredicate, ScopeScalar } from './scope.js';
export { bindFeedbackTarget } from './target.js';
export type {
  FeedbackTargetBinding,
  FeedbackTargetEvidence,
  FeedbackTargetReference,
  TargetableDecision,
} from './target.js';
export { compileFeedbackAssertionCandidate } from './candidate.js';
export type { FeedbackAssertionCandidateInput, FeedbackAssertionProposal } from './candidate.js';
