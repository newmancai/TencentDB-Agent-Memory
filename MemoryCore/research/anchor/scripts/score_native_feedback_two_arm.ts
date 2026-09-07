import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { performance } from "node:perf_hooks";

import { assessTaskEvidence, buildObjectiveTaskOutcome, repairMissingOutputPrefix } from "../../../src/core/self-supervision/execution-feedback.js";
import type { ToolExecutionObservation } from "../../../src/core/self-supervision/tool-execution.js";
import type { LayerExposure, ValidatorObservation } from "../../../src/core/self-supervision/types.js";

const root = path.resolve(process.argv[2] ?? "");
if (!root.startsWith("/tmp/") || root === "/tmp") throw new Error("run root below /tmp required");
const plan = JSON.parse(await readFile(path.join(root, "run-plan.json"), "utf8"));
const digest = (value: unknown) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
const expected: Record<string, string> = {
  format_conflict: "CHECK|INTG-AP-010,INTG-AP-011",
  fact_preservation: "IDS|INTG-EU-002,INTG-US-004,INTG-AP-006",
};
const expectedIds: Record<string, string[]> = {
  format_conflict: ["INTG-AP-010", "INTG-AP-011"],
  fact_preservation: ["INTG-EU-002", "INTG-US-004", "INTG-AP-006"],
};

function exposureRows(raw: any): LayerExposure[] {
  return (raw.candidates ?? []).map((row: any) => ({
    exposureId: `${raw.eventId}:${row.recordId}`,
    node: { layer: "L1", id: row.recordId, version: row.version },
    state: row.used ? "used" : row.exposed ? "exposed" : "retrieved",
    channel: "prompt_l1", rank: row.promptRank, score: row.score,
    renderedHash: row.renderedHash, truncated: row.truncated, derivationEdges: [],
  }));
}

const rows: any[] = [];
const projectionTimes: number[] = [];
for (const [targetName] of Object.entries(plan.targets)) {
  for (const [block, arm] of plan.schedule as Array<[number, string]>) {
    const dir = path.join(root, "targets", targetName, `block-${block}-${arm}`);
    const result = JSON.parse(await readFile(path.join(dir, "result.json"), "utf8"));
    const exposureRaw = JSON.parse(await readFile(path.join(dir, "artifacts/tdai/exposure.json"), "utf8"));
    const observations = JSON.parse(await readFile(path.join(dir,
      "artifacts/tdai/tool-execution-observations.json"), "utf8")) as ToolExecutionObservation[];
    const sidecarEvents = (await readFile(path.join(dir, "artifacts/tdai/events.jsonl"), "utf8"))
      .split("\n").filter(Boolean).map((line) => JSON.parse(line));
    const activeL1Searches = sidecarEvents.filter((event) =>
      event.op === "active_search" && event.data?.layer === "L1");
    const searchInterventionApplied = activeL1Searches.length === 0 ? null : activeL1Searches.every((event) =>
      arm !== "adjusted" || (event.data.excludedRecordIds ?? []).includes(plan.adjustmentTarget.recordId));
    const excludedRecordLeaked = activeL1Searches.some((event) =>
      arm === "adjusted" && String(event.data?.result?.text ?? "").includes("BATCH|approved_ids|blocked_ids"));
    const exactOutput = String(result.final ?? "").trim() === expected[targetName];
    const observedIds = String(result.final ?? "").match(/INTG-[A-Z]+-\d+/g) ?? [];
    const semanticFactsCorrect = JSON.stringify(observedIds) === JSON.stringify(expectedIds[targetName]);
    const outputProtocolCorrect = String(result.final ?? "").trim().startsWith(
      targetName === "format_conflict" ? "CHECK|" : "IDS|",
    );
    const prefixRepair = repairMissingOutputPrefix({
      output: String(result.final ?? ""),
      requiredPrefix: targetName === "format_conflict" ? "CHECK|" : "IDS|",
      bodyIsValid: (body) => JSON.stringify(body.match(/INTG-[A-Z]+-\d+/g) ?? [])
        === JSON.stringify(expectedIds[targetName])
        && body === expectedIds[targetName].join(","),
    });
    const hostNormalizedExact = prefixRepair.output === expected[targetName];
    const noMutations = (result.audit?.updates ?? []).length === 0;
    const hasRequiredRead = targetName !== "format_conflict" || observations.some((row) =>
      row.tool === "config_list_integrations" && row.taskRunId === exposureRaw.taskRunId);
    const validators: ValidatorObservation[] = [
      { validatorId: "exact_output", validatorVersion: "1", oracleKind: "exact",
        status: exactOutput ? "pass" : "fail", score: exactOutput ? 1 : 0, evidenceHash: digest(result.final) },
      { validatorId: "no_mutations", validatorVersion: "1", oracleKind: "database",
        status: noMutations ? "pass" : "fail", score: noMutations ? 1 : 0, evidenceHash: digest(result.audit?.updates ?? []) },
      { validatorId: "required_read", validatorVersion: "1", oracleKind: "constraint",
        status: hasRequiredRead ? "pass" : "fail", score: hasRequiredRead ? 1 : 0, evidenceHash: digest(observations) },
    ];
    const outcome = buildObjectiveTaskOutcome({ output: result.final, environment: result.state,
      modelId: plan.model.model, validators });
    const started = performance.now();
    const assessment = assessTaskEvidence({ taskRunId: exposureRaw.taskRunId, observations, outcome,
      memoryRelevance: targetName === "fact_preservation" ? "memory_relevant" : "unknown",
      exposures: exposureRows(exposureRaw) });
    projectionTimes.push(performance.now() - started);
    rows.push({ target: targetName, block, arm, final: result.final, exactOutput,
      semanticFactsCorrect, outputProtocolCorrect, noMutations,
      prefixRepair, hostNormalizedExact,
      activeL1SearchCount: activeL1Searches.length, searchInterventionApplied, excludedRecordLeaked,
      hasRequiredRead, taskRunId: exposureRaw.taskRunId, nativeBoundObservations: observations.filter((row) =>
        row.taskRunId === exposureRaw.taskRunId).length, observationCount: observations.length,
      outcome, assessment, cost: result.cost, elapsedSeconds: result.elapsed_seconds });
  }
}

const byArm = (arm: string) => rows.filter((row) => row.arm === arm);
const metricsFor = (arm: string) => {
  const selected = byArm(arm);
  return { passed: selected.filter((row) => row.outcome.status === "success").length,
    total: selected.length, passRate: selected.filter((row) => row.outcome.status === "success").length / selected.length,
    severeRegressions: selected.filter((row) => !row.noMutations).length,
    semanticFactsCorrect: selected.filter((row) => row.semanticFactsCorrect).length,
    outputProtocolCorrect: selected.filter((row) => row.outputProtocolCorrect).length,
    hostNormalizedExact: selected.filter((row) => row.hostNormalizedExact).length,
    calls: selected.reduce((sum, row) => sum + row.cost.calls, 0),
    inputTokens: selected.reduce((sum, row) => sum + row.cost.input_tokens, 0),
    outputTokens: selected.reduce((sum, row) => sum + row.cost.output_tokens, 0),
    generationMs: selected.reduce((sum, row) => sum + row.cost.generation_ms, 0) };
};
const unadjusted = metricsFor("unadjusted");
const adjusted = metricsFor("adjusted");
const observations = rows.reduce((sum, row) => sum + row.observationCount, 0);
const nativeBound = rows.reduce((sum, row) => sum + row.nativeBoundObservations, 0);
const result = {
  schemaVersion: "tdai-native-feedback-two-arm-result.v2",
  runRoot: root,
  claim: "new synthetic business targets; real local Qwen; development n=2/arm/target",
  rows,
  metrics: { unadjusted, adjusted, passRateDelta: adjusted.passRate - unadjusted.passRate,
    nativeTaskBinding: { count: nativeBound, total: observations, rate: observations ? nativeBound / observations : 1 },
    objectiveOutcomeCoverage: rows.filter((row) => row.outcome.status !== "unknown").length / rows.length,
    adjustedActiveSearchIntervention: {
      passed: rows.filter((row) => row.arm === "adjusted" && row.searchInterventionApplied === true).length,
      total: rows.filter((row) => row.arm === "adjusted" && row.searchInterventionApplied !== null).length,
      excludedRecordLeaks: rows.filter((row) => row.arm === "adjusted" && row.excludedRecordLeaked).length,
    },
    feedbackStageCounts: Object.fromEntries([...new Set(rows.map((row) => row.assessment.feedbackStage))]
      .map((stage) => [stage, rows.filter((row) => row.assessment.feedbackStage === stage).length])),
    projectionMs: { total: projectionTimes.reduce((a, b) => a + b, 0),
      p95: [...projectionTimes].sort((a, b) => a - b)[Math.ceil(projectionTimes.length * .95) - 1] ?? 0 },
    modelCallsPerSuccess: {
      unadjusted: unadjusted.passed ? unadjusted.calls / unadjusted.passed : null,
      adjusted: adjusted.passed ? adjusted.calls / adjusted.passed : null,
    } },
  productionMemoryActions: 0,
};
await writeFile(path.join(root, "result.json"), `${JSON.stringify(result, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(result.metrics, null, 2)}\n`);
