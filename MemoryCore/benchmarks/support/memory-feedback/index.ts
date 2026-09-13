export {
  observeFeedback,
  recordMemoryAssertion,
  recordOutcome,
  selectMemoryAction,
  validateFeedbackReplay,
} from './trace.js';
export type * from './trace.js';
export { JsonlFeedbackTraceStore } from './trace-store.js';
export type { FeedbackTraceStore } from './trace-store.js';
export { decisionTraceFromRecallObservation } from './recall-trace-adapter.js';
export type { RecallDecisionTraceInput } from './recall-trace-adapter.js';
export { assertScopePredicate, matchMemoryScope } from './scope.js';
export type * from './scope.js';
export { bindFeedbackTarget } from './target.js';
export type * from './target.js';
export { compileFeedbackAssertionCandidate } from './candidate.js';
export type * from './candidate.js';
