import { describe, expect, it } from "vitest";

import { canonicalHash } from "./observation-plane.js";
import {
  evaluateIndependentMemoryRelevance,
  unavailableMemoryRelevance,
} from "./memory-relevance.js";

describe("independent Memory relevance", () => {
  it("gives the evaluator only a frozen pre-retrieval subject and binds its result", async () => {
    const preRetrievalContextHash = canonicalHash("task before recall");
    const authoritySnapshotDigest = canonicalHash("task contract snapshot");
    const relevance = await evaluateIndependentMemoryRelevance({
      subject: {
        taskRunId: "task-1",
        sessionId: "session-1",
        preRetrievalContextHash,
        authority: {
          authorityId: "task-contract",
          authorityVersion: "1",
          effectiveAt: "2026-09-04T00:00:00.000Z",
          authoritySnapshotDigest,
        },
      },
      evaluator: {
        id: "deterministic-task-contract-v1",
        version: "1",
        evaluatorDigest: canonicalHash("evaluator"),
        policyDigest: canonicalHash("policy"),
        basis: "deterministic_task_contract",
        calibrationArtifactDigest: null,
        inputSurface: "pre_retrieval_subject_and_authority_only",
        async evaluate(subject) {
          expect(Object.keys(subject).sort()).toEqual([
            "authority", "preRetrievalContextHash", "sessionId", "taskRunId",
          ]);
          expect(Object.isFrozen(subject)).toBe(true);
          expect(Object.isFrozen(subject.authority)).toBe(true);
          expect(subject).not.toHaveProperty("candidates");
          expect(subject).not.toHaveProperty("score");
          return { decision: "no_match", evidenceHash: canonicalHash("no memory required") };
        },
      },
      evaluatedAt: "2026-09-04T00:00:01.000Z",
    });

    expect(relevance).toMatchObject({
      decision: "no_match",
      authority: { authoritySnapshotDigest },
      independentOfProductionRetrieval: true,
      evaluationSurface: "pre_retrieval_subject_and_authority_only",
    });
    expect(Object.isFrozen(relevance)).toBe(true);
  });

  it("constructs an explicit unknown/abstain input when authority is unavailable", () => {
    const relevance = unavailableMemoryRelevance({
      taskRunId: "task-1",
      sessionId: "session-1",
      preRetrievalContextHash: canonicalHash("task before recall"),
      evaluatedAt: "2026-09-04T00:00:01.000Z",
    });
    expect(relevance).toMatchObject({
      decision: "unknown",
      basis: "unavailable",
      authority: null,
      evidenceHash: null,
    });
  });

  it("rejects authority that becomes effective only after evaluation", async () => {
    await expect(evaluateIndependentMemoryRelevance({
      subject: {
        taskRunId: "task-1",
        sessionId: "session-1",
        preRetrievalContextHash: canonicalHash("task before recall"),
        authority: {
          authorityId: "future-contract",
          authorityVersion: "1",
          effectiveAt: "2026-09-04T00:00:02.000Z",
          authoritySnapshotDigest: canonicalHash("future contract snapshot"),
        },
      },
      evaluator: {
        id: "deterministic-task-contract-v1",
        version: "1",
        evaluatorDigest: canonicalHash("evaluator"),
        policyDigest: canonicalHash("policy"),
        basis: "deterministic_task_contract",
        calibrationArtifactDigest: null,
        inputSurface: "pre_retrieval_subject_and_authority_only",
        async evaluate() {
          throw new Error("must not be called");
        },
      },
      evaluatedAt: "2026-09-04T00:00:01.000Z",
    })).rejects.toThrow(/after evaluation/);
  });
});
