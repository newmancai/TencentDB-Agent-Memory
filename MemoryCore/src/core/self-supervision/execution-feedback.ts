import { createHash } from "node:crypto";
import type {
  LayerExposure,
  MemoryRelevanceDecision,
  TaskOutcomeObservation,
  ValidatorObservation,
} from "./types.js";
import type { ToolExecutionObservation } from "./tool-execution.js";

export type LocalExecutionStatus = "verified" | "contradicted" | "failed" | "unknown";
export type FeedbackStage =
  | "task_verified"
  | "non_memory_failure"
  | "retrieval"
  | "exposure_or_use"
  | "tool_execution"
  | "downstream_or_unknown"
  | "insufficient_evidence";

export interface TaskEvidenceAssessment {
  taskRunId: string;
  /** Tool receipts alone never promote this field to task success or failure. */
  outcomeStatus: TaskOutcomeObservation["status"];
  executionStatus: LocalExecutionStatus;
  feedbackStage: FeedbackStage;
  taskOutcomeAuthority: boolean;
  /** Eligible for a later attribution study, never direct positive/negative credit. */
  eligibleForMemoryAttributionStudy: boolean;
  reasonCodes: string[];
}

export interface TaskEvidenceInput {
  taskRunId: string;
  observations: readonly ToolExecutionObservation[];
  outcome: TaskOutcomeObservation | null;
  memoryRelevance: MemoryRelevanceDecision;
  exposures: readonly LayerExposure[];
}

export interface ObjectiveTaskOutcomeInput {
  output: unknown;
  environment: unknown;
  modelId: string;
  validators: readonly ValidatorObservation[];
}

export interface MissingPrefixRepairInput {
  output: string;
  requiredPrefix: string;
  /** The host must independently validate the unchanged semantic body. */
  bodyIsValid: (body: string) => boolean;
}

export interface MissingPrefixRepairResult {
  output: string;
  repaired: boolean;
  reason: "already_valid" | "missing_prefix_repaired" | "unsafe_or_invalid_body";
}

const hash = (value: unknown): string => createHash("sha256")
  .update(JSON.stringify(value)).digest("hex");

/**
 * Repair only a missing literal prefix. It never changes the semantic body and
 * abstains on multiline/delimited output or when the host cannot validate it.
 */
export function repairMissingOutputPrefix(input: MissingPrefixRepairInput): MissingPrefixRepairResult {
  const output = input.output.trim();
  if (output.startsWith(input.requiredPrefix)) {
    return { output, repaired: false, reason: "already_valid" };
  }
  if (!input.requiredPrefix || output.includes("\n") || output.includes("\r") || output.includes("|")
    || !input.bodyIsValid(output)) {
    return { output, repaired: false, reason: "unsafe_or_invalid_body" };
  }
  return { output: `${input.requiredPrefix}${output}`, repaired: true, reason: "missing_prefix_repaired" };
}

/** Build an all-required task outcome from objective host validators. */
export function buildObjectiveTaskOutcome(input: ObjectiveTaskOutcomeInput): TaskOutcomeObservation {
  const validators = input.validators.filter((row) => row.oracleKind !== "blind_judge");
  const status: TaskOutcomeObservation["status"] = validators.length === 0
    || validators.some((row) => row.status === "error" || row.status === "unverifiable")
    ? "unknown"
    : validators.some((row) => row.status === "fail") ? "failure" : "success";
  return {
    status,
    outputHash: hash(input.output),
    environmentHash: hash(input.environment),
    modelId: input.modelId,
    validators: validators.map((row) => ({ ...row })),
  };
}

/**
 * Deterministic weak-supervision projection over immutable task evidence.
 * It locates the first unsupported edge; it does not diagnose Memory content.
 */
export function assessTaskEvidence(input: TaskEvidenceInput): TaskEvidenceAssessment {
  const current = input.observations.filter((row) => row.taskRunId === input.taskRunId);
  const unboundOrStale = input.observations.length - current.length;
  const reasons: string[] = [];
  if (unboundOrStale > 0) reasons.push("ignored_unbound_or_stale_tool_evidence");

  const hasToolFailure = current.some((row) => row.validator.status === "fail"
    || row.validator.status === "error");
  const hasContradiction = current.some((row) => row.fieldChecks.some((field) => field.validity === "refuted"));
  const hasVerifiedEffect = current.some((row) => row.validator.status === "pass"
    && row.fieldChecks.some((field) => field.validity === "supported"));
  const executionStatus: LocalExecutionStatus = hasToolFailure ? "failed"
    : hasContradiction ? "contradicted"
      : hasVerifiedEffect ? "verified" : "unknown";

  const outcomeStatus = input.outcome?.status ?? "unknown";
  const objectiveValidators = input.outcome?.validators.filter((row) => row.oracleKind !== "blind_judge") ?? [];
  const authoritative = outcomeStatus === "success"
    ? objectiveValidators.length > 0 && objectiveValidators.every((row) => row.status === "pass")
    : outcomeStatus === "failure"
      ? objectiveValidators.some((row) => row.status === "fail")
      : outcomeStatus === "partial"
        ? objectiveValidators.some((row) => row.status === "pass")
          && objectiveValidators.some((row) => row.status === "fail")
        : false;
  if (!authoritative) reasons.push("no_authoritative_task_outcome");

  let feedbackStage: FeedbackStage = "insufficient_evidence";
  if (authoritative && outcomeStatus === "success") feedbackStage = "task_verified";
  else if (authoritative && (outcomeStatus === "failure" || outcomeStatus === "partial")) {
    if (input.memoryRelevance === "no_match") feedbackStage = "non_memory_failure";
    else if (input.memoryRelevance === "unknown") feedbackStage = "insufficient_evidence";
    else if (input.exposures.length === 0
      || input.exposures.every((row) => row.state === "retrieved")) feedbackStage = "retrieval";
    else if (!input.exposures.some((row) => row.state === "used")) feedbackStage = "exposure_or_use";
    else if (executionStatus === "failed" || executionStatus === "contradicted") feedbackStage = "tool_execution";
    else feedbackStage = "downstream_or_unknown";
  }

  if (feedbackStage === "retrieval") reasons.push("relevant_memory_not_exposed");
  if (feedbackStage === "exposure_or_use") reasons.push("memory_exposed_without_use_evidence");
  if (feedbackStage === "tool_execution") reasons.push("memory_used_before_execution_failure");

  return {
    taskRunId: input.taskRunId,
    outcomeStatus,
    executionStatus,
    feedbackStage,
    taskOutcomeAuthority: authoritative,
    eligibleForMemoryAttributionStudy: authoritative && input.memoryRelevance === "memory_relevant",
    reasonCodes: reasons,
  };
}
