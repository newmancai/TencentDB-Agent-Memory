export {
  FeedbackMemory,
  FeedbackPolicy,
  processFeedback,
  replacementContent,
  validateCandidate,
  verifyBounded,
} from './lifecycle.js';
export type { Candidate, PolicyState, Relation, SourceRecord, Verification } from './lifecycle.js';

export {
  parseAnswerFeedback,
  runAnswerFeedbackAdapter,
  selectAnswerFeedback,
} from './answer-feedback.js';
export type {
  AnswerFeedbackAdapterResult,
  AnswerFeedbackDecisionLog,
  AnswerFeedbackObservation,
  AnswerFeedbackResult,
  FeedbackObservationType,
} from './answer-feedback.js';

export { selectDependencyCandidates } from './dependency-candidate-adapter.js';
export type {
  DependencyCandidateDecisionLog,
  DependencyCandidatePath,
  DependencyCandidateProposal,
  DependencyCandidateRelation,
  DependencyCandidateResult,
  DependencyCandidateStatus,
} from './dependency-candidate-adapter.js';

export { ProjectMemory } from './project-memory.js';
export type {
  ConstraintProposal,
  ConstraintRetraction,
  ConstraintScope,
  ProjectAction,
  ProjectConstraint,
  ProjectContextOptions,
  ProjectContextResult,
  ProjectIngestResult,
  ProjectMemorySnapshot,
  ProjectObservation,
} from './project-memory.js';
