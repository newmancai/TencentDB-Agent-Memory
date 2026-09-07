import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { performance } from "node:perf_hooks";

import { assessTaskEvidence } from "../../../src/core/self-supervision/execution-feedback.js";
import { applyTieredDeterministicAdmission } from "../../../src/core/self-supervision/tiered-memory-admission.js";
import type { FinalMemoryDraft } from "../../../src/core/self-supervision/final-draft-admission.js";
import type { ToolExecutionObservation } from "../../../src/core/self-supervision/tool-execution.js";
import type { LayerExposure, TaskOutcomeObservation } from "../../../src/core/self-supervision/types.js";

type Json = Record<string, any>;

const evidenceRoot = path.resolve(process.cwd(),
  "../../.local-evidence/mainline-2026-09-06/zero-feedback-phase1-r1/run-r1");
const outputPath = path.resolve(process.cwd(),
  "research/memory-battle/memory-feedback-phase2/feedback-closure-result.v1.json");

async function json(file: string): Promise<Json> {
  return JSON.parse(await readFile(file, "utf8"));
}

function percentile(values: number[], q: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(sorted.length * q) - 1)] ?? 0;
}

function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function outcome(status: "success" | "failure", run: Json, result: Json): TaskOutcomeObservation {
  return {
    status,
    outputHash: digest(result.final),
    environmentHash: digest(result.state),
    modelId: "phase1-recorded-run",
    validators: [{
      validatorId: "phase1_action_task_pass",
      validatorVersion: "2026-09-06",
      oracleKind: "database",
      status: status === "success" ? "pass" : "fail",
      score: status === "success" ? 1 : 0,
      evidenceHash: digest({ case: run.case, arm: run.arm, actionTaskPass: run.action_task_pass,
        final: result.final, state: result.state }),
    }],
  };
}

function exposures(raw: Json): LayerExposure[] {
  return (raw.candidates ?? []).map((row: Json) => ({
    exposureId: `${raw.eventId}:${row.recordId}`,
    node: { layer: "L1", id: row.recordId, version: row.version ?? 1 },
    state: row.used ? "used" : row.exposed ? "exposed" : "retrieved",
    channel: "prompt_l1",
    rank: row.promptRank ?? row.retrievalRank ?? null,
    score: row.score ?? null,
    renderedHash: row.renderedHash ?? null,
    truncated: Boolean(row.truncated),
    derivationEdges: [],
  }));
}

async function replayTargets() {
  const summary = await json(path.join(evidenceRoot, "summary.json"));
  const rows: Json[] = [];
  let nativeBound = 0;
  let recoveredBound = 0;
  let observationCount = 0;
  const projectionLatencyMs: number[] = [];

  for (const run of summary.results as Json[]) {
    const base = path.join(evidenceRoot, run.case, run.arm);
    const rawExposure = await json(path.join(base, "artifacts/tdai/exposure.json"));
    const rawObservations = await json(path.join(base, "artifacts/tdai/tool-execution-observations.json"));
    const recordedResult = await json(path.join(base, "result.json"));
    const taskRunId = rawExposure.taskRunId as string;
    const observations = (rawObservations as ToolExecutionObservation[]).map((row) => {
      observationCount += 1;
      if (row.taskRunId === taskRunId) nativeBound += 1;
      const recoverable = row.taskRunId == null && row.sessionId === taskRunId;
      if (recoverable) recoveredBound += 1;
      return { ...row, taskRunId: recoverable ? taskRunId : row.taskRunId ?? null };
    });
    const started = performance.now();
    const assessment = assessTaskEvidence({
      taskRunId,
      observations,
      outcome: outcome(run.action_task_pass ? "success" : "failure", run, recordedResult),
      memoryRelevance: ["near", "far"].includes(run.case) ? "memory_relevant" : "no_match",
      exposures: exposures(rawExposure),
    });
    projectionLatencyMs.push(performance.now() - started);
    const expectedStage = run.action_task_pass ? "task_verified"
      : run.case === "far" && run.arm === "candidate" ? "exposure_or_use" : "insufficient_evidence";
    rows.push({ case: run.case, arm: run.arm, actionTaskPass: run.action_task_pass,
      expectedStage, stageMatchesReview: assessment.feedbackStage === expectedStage, assessment });
  }
  return {
    rows,
    metrics: {
      targetRuns: rows.length,
      toolObservations: observationCount,
      nativeTaskBinding: { count: nativeBound, rate: observationCount ? nativeBound / observationCount : 0 },
      deterministicallyRecoveredBinding: {
        count: recoveredBound, rate: observationCount ? recoveredBound / observationCount : 0,
        basis: "isolated episode exposure.taskRunId equals observation.sessionId",
      },
      authoritativeOutcomeCoverage: rows.filter((row) => row.assessment.taskOutcomeAuthority).length / rows.length,
      localExecutionJudgeableCoverage: rows.filter((row) => row.assessment.executionStatus !== "unknown").length / rows.length,
      reviewedStageAgreement: rows.filter((row) => row.stageMatchesReview).length / rows.length,
      stageCounts: Object.fromEntries([...new Set(rows.map((row) => row.assessment.feedbackStage))]
        .map((stage) => [stage, rows.filter((row) => row.assessment.feedbackStage === stage).length])),
      modelCalls: 0,
      tokens: 0,
      projectionLatencyMs: {
        total: projectionLatencyMs.reduce((a, b) => a + b, 0),
        p95: percentile(projectionLatencyMs, 0.95),
      },
    },
  };
}

async function scopeAdjustment() {
  const extractionLine = (await readFile(path.join(evidenceRoot,
    "source/artifacts/tdai/extraction-model.jsonl"), "utf8")).trim().split("\n")[0]!;
  const extraction = JSON.parse(extractionLine);
  const extracted = JSON.parse(extraction.response.choices[0].message.content)[0].memories as Json[];
  const instruction = extracted.find((row) => row.type === "instruction")!;
  const event = extracted.find((row) => row.type === "episodic")!;
  const userMessageId = instruction.source_message_ids[0] as string;
  const sourceInput = await json(path.join(evidenceRoot, "source/execution-input.json"));
  const instructionDraft: FinalMemoryDraft = {
    candidateIndex: 0,
    recordId: "phase1-spurious-format-instruction",
    action: "store",
    targetIds: [],
    content: instruction.content,
    type: "instruction",
    priority: instruction.priority,
    sceneName: "phase1-source",
    sourceMessageIds: instruction.source_message_ids,
    metadata: instruction.metadata,
  };
  const [decision] = applyTieredDeterministicAdmission({
    drafts: [instructionDraft],
    evidenceWindow: [{ id: userMessageId, role: "user", content: sourceInput.task.prompt.text }],
  });
  const approvedIds = ["INTG-EU-002", "INTG-US-004", "INTG-AP-006"];
  const eventStillSupportsLookup = approvedIds.every((id) => event.content.includes(id));
  return {
    source: "phase1 actual Qwen extraction",
    before: { retainedRecords: 2, behaviorTypedRecords: 1, eventRecords: 1 },
    feedbackDecision: decision,
    afterShadowAdjustment: {
      retainedRetrievableEventRecords: 1,
      activeBehaviorRulesFromFormatCandidate: decision.activation === "active_behavior_rule" ? 1 : 0,
      quarantinedRecords: decision.storageDisposition === "quarantine" ? 1 : 0,
      rawL0Preserved: true,
    },
    componentChecks: {
      temporaryFormatNotActivatedCrossTask: decision.activation !== "active_behavior_rule",
      approvedSubsetStillAvailableInEvent: eventStillSupportsLookup,
      passed: Number(decision.activation !== "active_behavior_rule") + Number(eventStillSupportsLookup),
      total: 2,
    },
    limitation: "Component-level shadow replay only; no new model task was executed.",
  };
}

const started = performance.now();
const taskEvidenceReplay = await replayTargets();
const memoryAdjustment = await scopeAdjustment();
if (taskEvidenceReplay.metrics.reviewedStageAgreement !== 1) {
  throw new Error("feedback-stage replay disagrees with reviewed development traces");
}
if (memoryAdjustment.componentChecks.passed !== memoryAdjustment.componentChecks.total) {
  throw new Error("shadow memory adjustment component check failed");
}
const result = {
  schemaVersion: "tdai-feedback-closure-result.v1",
  generatedAt: new Date().toISOString(),
  evidence: "zero-feedback-phase1-r1 persisted traces",
  evaluationBoundary: "offline development replay; post-run action grader is not runtime feedback",
  taskEvidenceReplay,
  memoryAdjustment,
  closureDecision: {
    memoryUtilityCredit: "none",
    reason: "single observational failure localizes to exposure/use but does not identify harmful Memory content",
    admissionAction: "quarantine_unproven_behavior_activation",
    preservedEvidence: ["raw_l0", "episodic_l1"],
    executionAction: "require_current_task_receipt",
    optimizationReady: false,
  },
  totalRunnerMs: performance.now() - started,
  productionMemoryActions: 0,
};
await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
