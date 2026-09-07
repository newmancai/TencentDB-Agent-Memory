import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  ExactLocalizationDatasetStore,
  buildGroundTruthGraph,
  createExactLocalizationExample,
  qualifyExactLocalizationExample,
  type GroundTruthMemoryGraph,
} from "./ground-truth.js";
import { createLayerAwareSignal } from "./layer-signal.js";
import { createCompleteTupleIdentifiabilityCertificate } from "./identifiability.js";
import { GatedCascadeLayerRouter, type RouteCandidate } from "./layer-router.js";
import {
  InMemoryShadowObservationStore,
  LayerObservationPlane,
  canonicalHash,
  createRootObservation,
  createShadowExecutionContext,
  memoryRelevanceSubjectBindingHash,
} from "./observation-plane.js";
import type {
  CompleteFeedbackTuple,
  LayerSignalEvidence,
  RootObservationInput,
  TaskOutcomeObservation,
} from "./types.js";

function graph(): GroundTruthMemoryGraph {
  return buildGroundTruthGraph({
    nodes: [
      {
        layer: "L0",
        id: "msg-user-1",
        version: 1,
        content: "项目 Atlas 的部署区域是上海。",
        metadata: { role: "user" },
        scope: { team: "team-a", project: "atlas" },
        entityBindings: { project: "atlas" },
        observedAt: "2026-09-01T00:00:00.000Z",
      },
      {
        layer: "L1",
        id: "l1-region",
        version: 3,
        content: "Atlas 部署在上海。",
        metadata: { logicalId: "atlas-region" },
        scope: { team: "team-a", project: "atlas" },
        entityBindings: { project: "atlas", region: "shanghai" },
        observedAt: "2026-09-01T00:01:00.000Z",
      },
      {
        layer: "L1",
        id: "l1-backup",
        version: 1,
        content: "Atlas 必须启用跨区备份。",
        metadata: { logicalId: "atlas-backup" },
        scope: { team: "team-a", project: "atlas" },
        entityBindings: { project: "atlas" },
        observedAt: "2026-09-01T00:02:00.000Z",
      },
      {
        layer: "L2",
        id: "l2-atlas-deploy",
        version: 5,
        content: "Atlas 在上海部署，并启用跨区备份。",
        metadata: { filename: "atlas-deploy.md" },
        scope: { team: "team-a", project: "atlas" },
        entityBindings: { project: "atlas", region: "shanghai" },
        observedAt: "2026-09-01T00:03:00.000Z",
      },
    ],
    edges: [
      {
        edgeId: "edge-msg-region",
        version: 1,
        relation: "L0_SUPPORTS_L1",
        from: { layer: "L0", id: "msg-user-1", version: 1 },
        to: { layer: "L1", id: "l1-region", version: 3 },
        metadata: { span: "部署区域是上海" },
      },
      {
        edgeId: "edge-region-scene",
        version: 2,
        relation: "L1_DERIVES_L2",
        from: { layer: "L1", id: "l1-region", version: 3 },
        to: { layer: "L2", id: "l2-atlas-deploy", version: 5 },
        metadata: { claims: ["region"] },
      },
      {
        edgeId: "edge-backup-scene",
        version: 1,
        relation: "L1_DERIVES_L2",
        from: { layer: "L1", id: "l1-backup", version: 1 },
        to: { layer: "L2", id: "l2-atlas-deploy", version: 5 },
        metadata: { claims: ["backup"] },
      },
    ],
  });
}

function snapshot(input: GroundTruthMemoryGraph) {
  return {
    nodes: input.nodes.map(({ content: _content, metadata: _metadata, scope: _scope, entityBindings: _bindings, ...node }) => node),
    edges: input.edges.map(({ metadata: _metadata, ...edge }) => edge),
  };
}

function rootInput(): RootObservationInput {
  const source = graph();
  const contextHash = canonicalHash("deploy atlas");
  const authoritySnapshotDigest = canonicalHash("atlas task contract snapshot v1");
  const authority = {
    authorityId: "atlas-task-contract",
    authorityVersion: "1",
    effectiveAt: "2026-09-03T00:00:00.000Z",
    authoritySnapshotDigest,
  };
  return {
    origin: "production",
    feedbackDepth: 0,
    taskRunId: "task-run-1",
    sessionId: "session-1",
    preRetrievalContextHash: contextHash,
    contextHash,
    memoryRelevance: {
      schemaVersion: "tdai-memory-relevance.v1",
      decision: "memory_relevant",
      basis: "deterministic_task_contract",
      evaluatorId: "atlas-task-contract-v1",
      evaluatorVersion: "1",
      evaluatorDigest: canonicalHash("atlas-task-contract-evaluator-v1"),
      policyDigest: canonicalHash("atlas-task-contract-policy-v1"),
      evaluatedAt: "2026-09-03T00:00:00.000Z",
      evidenceHash: canonicalHash("atlas task requires deployment Memory"),
      authority,
      calibrationArtifactDigest: null,
      subjectBindingHash: memoryRelevanceSubjectBindingHash({
        taskRunId: "task-run-1",
        sessionId: "session-1",
        preRetrievalContextHash: contextHash,
        authority,
      }),
      independentOfProductionRetrieval: true,
      evaluationSurface: "pre_retrieval_subject_and_authority_only",
    },
    graph: snapshot(source),
    exposures: [
      {
        exposureId: "exp-l1-region",
        node: { layer: "L1", id: "l1-region", version: 3 },
        state: "exposed",
        channel: "prompt_l1",
        rank: 1,
        score: 0.94,
        renderedHash: canonicalHash("Atlas 部署在上海。"),
        truncated: false,
        derivationEdges: [],
      },
      {
        exposureId: "exp-l2-atlas",
        node: { layer: "L2", id: "l2-atlas-deploy", version: 5 },
        state: "used",
        channel: "l2_file_read",
        rank: null,
        score: null,
        renderedHash: canonicalHash("Atlas 在上海部署，并启用跨区备份。"),
        truncated: false,
        derivationEdges: [
          { edgeId: "edge-region-scene", edgeVersion: 2 },
          { edgeId: "edge-backup-scene", edgeVersion: 1 },
        ],
      },
    ],
    outcome: null,
  };
}

function outcome(verdict: "pass" | "fail", environmentHash = "env-1"): TaskOutcomeObservation {
  return {
    status: verdict === "pass" ? "success" : "failure",
    outputHash: canonicalHash(verdict),
    environmentHash,
    modelId: "model-fixed",
    validators: [{
      validatorId: "deployment-assertion",
      validatorVersion: "1",
      oracleKind: "database",
      status: verdict,
      score: verdict === "pass" ? 1 : 0,
      evidenceHash: canonicalHash(`oracle-${verdict}`),
    }],
  };
}

const IDENTIFIABILITY_EVIDENCE: LayerSignalEvidence = {
  kind: "l1_l2_derivation",
  supportingIds: ["edge-region-scene"],
  claim: "capture authority excludes competing tuple and no-signal worlds",
  evidenceHash: canonicalHash("tuple-authority"),
  verifierId: "tuple-authority-v1",
};

function identifiedCertificate(
  tuple: CompleteFeedbackTuple,
  candidates: CompleteFeedbackTuple[] = [tuple],
) {
  return createCompleteTupleIdentifiabilityCertificate({
    verifierId: "tuple-authority-v1",
    basis: "capture_authority",
    status: "identified",
    candidateTuples: candidates,
    identifiedTuple: tuple,
    noSignalWorldExcluded: true,
    evidence: [IDENTIFIABILITY_EVIDENCE],
    reasonCodes: ["exact_tuple_authority"],
  });
}

describe("non-recursive shadow observation plane", () => {
  it("records a root once and makes replay results ineligible to enqueue feedback", async () => {
    const store = new InMemoryShadowObservationStore();
    const plane = new LayerObservationPlane(store, () => "2026-09-03T00:00:00.000Z");
    const first = await plane.collect(rootInput());
    const second = await plane.collect(rootInput());
    expect(first.accepted).toBe(true);
    expect(first.observation.schemaVersion).toBe("tdai-shadow-observation.v2");
    expect(Object.isFrozen(first.observation)).toBe(true);
    expect(Object.isFrozen(first.observation.memoryRelevance)).toBe(true);
    expect(Object.isFrozen(first.observation.graph.nodes[0])).toBe(true);
    expect(second).toMatchObject({ accepted: false, duplicate: true });

    const context = createShadowExecutionContext(first.observation.observationId);
    const event = await plane.recordReplay(first.observation, context, {
      traceId: first.observation.observationId,
      snapshotId: "snapshot-1",
      arms: [],
      comparable: false,
      abstainReason: "test",
    });
    expect(event).toMatchObject({
      eventType: "shadow_replay_result",
      memoryIngestionAllowed: false,
      mayEnqueueFeedback: false,
      executionContext: {
        feedbackDepth: 1,
        recallEnabled: false,
        captureEnabled: false,
        memoryWriteEnabled: false,
        feedbackReingestionEnabled: false,
      },
    });
    expect(store.events).toHaveLength(2);
  });

  it("cannot construct a root observation from self-supervision output", () => {
    expect(() => createRootObservation({
      ...rootInput(),
      origin: "self_supervision",
      feedbackDepth: 1,
    } as unknown as RootObservationInput, "2026-09-03T00:00:00.000Z")).toThrow(/origin/);
  });

  it("rejects a relevance decision replayed onto a different pre-retrieval subject", () => {
    const input = rootInput();
    input.preRetrievalContextHash = canonicalHash("different task subject");
    expect(() => createRootObservation(input, "2026-09-03T00:00:00.000Z")).toThrow(/input binding/);
  });

  it("binds the complete relevance authority reference, not only its snapshot digest", () => {
    const input = rootInput();
    input.memoryRelevance.authority!.authorityVersion = "2";
    expect(() => createRootObservation(input, "2026-09-03T00:00:00.000Z")).toThrow(/input binding/);
  });

  it("rejects an authority that was not effective when relevance was evaluated", () => {
    const input = rootInput();
    input.memoryRelevance.authority!.effectiveAt = "2026-09-03T00:00:01.000Z";
    expect(() => createRootObservation(input, "2026-09-03T00:00:01.000Z")).toThrow(/after evaluation/);
  });
});

describe("exact localization collection", () => {
  const task = {
    taskId: "deploy-atlas",
    queryHash: canonicalHash("deploy atlas"),
    oracleId: "deployment-assertion",
    oracleVersion: "1",
  };

  it.each([
    {
      name: "L1 node",
      injection: {
        targetType: "L1_NODE" as const,
        targetId: "l1-region",
        targetVersion: 3,
        faultType: "wrong_entity_binding" as const,
        suggestedAction: "repair_entity_binding" as const,
        patch: { entityBindings: { project: "borealis", region: "shanghai" } },
      },
    },
    {
      name: "L2 node",
      injection: {
        targetType: "L2_NODE" as const,
        targetId: "l2-atlas-deploy",
        targetVersion: 5,
        faultType: "missing_constraint" as const,
        suggestedAction: "rederive_l2" as const,
        patch: { content: "Atlas 在上海部署。" },
      },
    },
    {
      name: "L1 to L2 edge",
      injection: {
        targetType: "L1_L2_EDGE" as const,
        targetId: "edge-region-scene",
        targetVersion: 2,
        faultType: "broken_derivation" as const,
        suggestedAction: "repair_derivation" as const,
        patch: { from: { layer: "L1" as const, id: "l1-backup", version: 1 } },
      },
    },
  ])("constructs deterministic exact gold for a single $name fault", ({ injection }) => {
    const first = createExactLocalizationExample({ cleanGraph: graph(), injection, task, splitGroup: "atlas", seed: 7 });
    const second = createExactLocalizationExample({ cleanGraph: graph(), injection, task, splitGroup: "atlas", seed: 7 });
    expect(first.label.exampleId).toBe(second.label.exampleId);
    expect(first.label.target.targetType).toBe(injection.targetType);
    expect(first.label.target.targetId).toBe(injection.targetId);
    expect(first.label.target.targetVersion).toBe(injection.targetVersion);
    expect(first.label.structuralGroundTruth).toBe("exact_by_single_intervention");
    expect(first.label.cleanGraphHash).toBe(first.label.repairedGraphHash);
    expect(first.label.corruptedGraphHash).not.toBe(first.label.cleanGraphHash);
    expect(first.detectorView).not.toHaveProperty("faultType");
    expect(first.detectorView).not.toHaveProperty("target");
    expect(first.detectorView.corruptedGraph.nodes.every((node) => typeof node.content === "string")).toBe(true);
  });

  it("qualifies causal localization only with clean-pass/corrupt-fail/repair-pass/control-pass", () => {
    const example = createExactLocalizationExample({
      cleanGraph: graph(),
      injection: {
        targetType: "L2_NODE",
        targetId: "l2-atlas-deploy",
        targetVersion: 5,
        faultType: "missing_constraint",
        suggestedAction: "rederive_l2",
        patch: { content: "Atlas 在上海部署。" },
      },
      task,
      splitGroup: "atlas",
      seed: 7,
    });
    const qualified = qualifyExactLocalizationExample(example, {
      clean: outcome("pass"),
      corrupt: outcome("fail"),
      repair: outcome("pass"),
      negativeControl: outcome("pass"),
    });
    expect(qualified.label.causalQualification).toBe("qualified");

    const rejected = qualifyExactLocalizationExample(example, {
      clean: outcome("pass"),
      corrupt: outcome("fail", "different-env"),
      repair: outcome("pass"),
      negativeControl: outcome("pass"),
    });
    expect(rejected.label.causalQualification).toBe("rejected");
    expect(rejected.label.qualificationReasonCodes).toContain("environment_mismatch");
  });

  it("stores detector views and gold labels separately", () => {
    const root = mkdtempSync(join(tmpdir(), "tdai-exact-localization-"));
    try {
      const example = createExactLocalizationExample({
        cleanGraph: graph(),
        injection: {
          targetType: "L1_NODE",
          targetId: "l1-region",
          targetVersion: 3,
          faultType: "wrong_scope",
          suggestedAction: "repair_scope",
          patch: { scope: { team: "team-b", project: "atlas" } },
        },
        task,
        splitGroup: "atlas",
        seed: 9,
      });
      const store = new ExactLocalizationDatasetStore(root);
      store.append(example);
      const view = readFileSync(store.viewsPath, "utf8");
      const label = readFileSync(store.labelsPath, "utf8");
      const commit = readFileSync(store.commitsPath, "utf8");
      expect(view).not.toContain('"faultType"');
      expect(view).not.toContain('"structuralGroundTruth"');
      expect(label).toContain('"targetType":"L1_NODE"');
      expect(commit).toContain(`"exampleId":"${example.label.exampleId}"`);
      expect(() => new ExactLocalizationDatasetStore(root)).not.toThrow();
      expect(() => store.append(example)).toThrow(/Duplicate example/);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

describe("layer-aware feedback contract", () => {
  it("emits against the exact L1→L2 edge version", () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const tuple: CompleteFeedbackTuple = {
      target: {
        targetType: "L1_L2_EDGE",
        targetId: "edge-region-scene",
        targetVersion: 2,
        from: { layer: "L1", id: "l1-region", version: 3 },
        to: { layer: "L2", id: "l2-atlas-deploy", version: 5 },
      },
      faultType: "broken_derivation",
      suggestedAction: "repair_derivation",
    };
    const signal = createLayerAwareSignal(observation, {
      decision: "emit",
      ...tuple,
      supportingIds: ["l1-region", "l2-atlas-deploy"],
      validity: "refuted",
      utility: "untested",
      failureOwner: "derivation",
      confidence: 0.97,
      calibrationVersion: "calibration-dev-v1",
      evidence: [{
        kind: "l1_l2_derivation",
        supportingIds: ["edge-region-scene"],
        claim: "edge source does not support the L2 claim",
        evidenceHash: canonicalHash("derivation-check"),
        verifierId: "graph-validator-v1",
      }],
      identifiabilityCertificate: identifiedCertificate(tuple),
      replayStatus: "not_run",
      reasonCodes: ["exact_edge_mismatch"],
    }, "2026-09-03T00:00:01.000Z");
    expect(signal.target).toMatchObject({ targetType: "L1_L2_EDGE", targetVersion: 2 });
    expect(signal.schemaVersion).toBe("tdai-layer-feedback-signal.v2");
    expect(signal.optimizationReady).toBe(false);
  });

  it("rejects an exact certificate for an unresolved version-zero target", () => {
    expect(() => identifiedCertificate({
      target: { targetType: "L1_NODE", targetId: "legacy-l1", targetVersion: 0 },
      faultType: "unsupported_content",
      suggestedAction: "quarantine_candidate",
    })).toThrow(/positive integer/);
  });

  it("does not let exposure of one edge version authorize harmful attribution to another", () => {
    const input = rootInput();
    const current = input.graph.edges.find((edge) => edge.edgeId === "edge-region-scene")!;
    input.graph.edges.push({ ...structuredClone(current), version: 1 });
    const observation = createRootObservation(input, "2026-09-03T00:00:00.000Z");
    const tuple: CompleteFeedbackTuple = {
      target: {
        targetType: "L1_L2_EDGE",
        targetId: "edge-region-scene",
        targetVersion: 1,
        from: { layer: "L1", id: "l1-region", version: 3 },
        to: { layer: "L2", id: "l2-atlas-deploy", version: 5 },
      },
      faultType: "task_harmful",
      suggestedAction: "repair_derivation",
    };
    expect(() => createLayerAwareSignal(observation, {
      decision: "emit",
      ...tuple,
      supportingIds: ["edge-region-scene"],
      validity: "supported",
      utility: "harmful",
      failureOwner: "derivation",
      confidence: 0.99,
      calibrationVersion: "test",
      evidence: [{
        kind: "task_intervention",
        supportingIds: ["edge-region-scene"],
        claim: "masking the older edge changed the objective result",
        evidenceHash: canonicalHash("mask-edge-v1"),
        verifierId: "replay-v1",
      }],
      identifiabilityCertificate: identifiedCertificate(tuple),
      replayStatus: "replay_verified",
      reasonCodes: ["harmful_edge"],
    }, "2026-09-03T00:00:01.000Z")).toThrow(/exact target version|exposed or used/);
  });

  it("rejects task-harmful attribution without verified replay", () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const tuple: CompleteFeedbackTuple = {
      target: { targetType: "L1_NODE", targetId: "l1-region", targetVersion: 3 },
      faultType: "task_harmful",
      suggestedAction: "quarantine_candidate",
    };
    expect(() => createLayerAwareSignal(observation, {
      decision: "emit",
      ...tuple,
      supportingIds: [],
      validity: "supported",
      utility: "harmful",
      failureOwner: "memory_content",
      confidence: 0.99,
      calibrationVersion: "test",
      evidence: [{
        kind: "task_intervention",
        supportingIds: [],
        claim: "mask improved task",
        evidenceHash: canonicalHash("mask"),
        verifierId: "replay-v1",
      }],
      identifiabilityCertificate: identifiedCertificate(tuple),
      replayStatus: "incomplete",
      reasonCodes: [],
    }, "2026-09-03T00:00:01.000Z")).toThrow(/replay_verified/);
  });

  it("rejects task-harmful attribution to a retrieved-only target", () => {
    const input = rootInput();
    input.exposures[0] = { ...input.exposures[0]!, state: "retrieved" };
    const observation = createRootObservation(input, "2026-09-03T00:00:00.000Z");
    const tuple: CompleteFeedbackTuple = {
      target: { targetType: "L1_NODE", targetId: "l1-region", targetVersion: 3 },
      faultType: "task_harmful",
      suggestedAction: "quarantine_candidate",
    };
    expect(() => createLayerAwareSignal(observation, {
      decision: "emit",
      ...tuple,
      supportingIds: [],
      validity: "supported",
      utility: "harmful",
      failureOwner: "memory_content",
      confidence: 0.99,
      calibrationVersion: "test",
      evidence: [{
        kind: "task_intervention",
        supportingIds: [],
        claim: "mask improved task",
        evidenceHash: canonicalHash("mask"),
        verifierId: "replay-v1",
      }],
      identifiabilityCertificate: identifiedCertificate(tuple),
      replayStatus: "replay_verified",
      reasonCodes: [],
    }, "2026-09-03T00:00:01.000Z")).toThrow(/exposed or used/);
  });

  it("rejects environment/model ownership against a Memory target", () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const tuple: CompleteFeedbackTuple = {
      target: { targetType: "L1_NODE", targetId: "l1-region", targetVersion: 3 },
      faultType: "environment_or_model_failure",
      suggestedAction: "no_action",
    };
    expect(() => createLayerAwareSignal(observation, {
      decision: "emit",
      ...tuple,
      supportingIds: [],
      validity: "unverifiable",
      utility: "untested",
      failureOwner: "environment",
      confidence: 0.99,
      calibrationVersion: "test",
      evidence: [{ ...IDENTIFIABILITY_EVIDENCE, kind: "environment" }],
      identifiabilityCertificate: identifiedCertificate(tuple),
      replayStatus: "not_run",
      reasonCodes: [],
    }, "2026-09-03T00:00:01.000Z")).toThrow(/cannot carry a Memory target/);
  });

  it("rejects an emit without a complete-tuple certificate", () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    expect(() => createLayerAwareSignal(observation, {
      decision: "emit",
      target: { targetType: "L2_NODE", targetId: "l2-atlas-deploy", targetVersion: 5 },
      supportingIds: ["l1-backup"],
      faultType: "missing_constraint",
      suggestedAction: "rederive_l2",
      validity: "refuted",
      utility: "untested",
      failureOwner: "derivation",
      confidence: 0.99,
      calibrationVersion: "test",
      evidence: [IDENTIFIABILITY_EVIDENCE],
      identifiabilityCertificate: null,
      replayStatus: "not_run",
      reasonCodes: [],
    }, "2026-09-03T00:00:01.000Z")).toThrow(/identifiability certificate/);
  });
});

describe("gated cascade router", () => {
  const candidate: RouteCandidate = {
    target: { targetType: "L2_NODE", targetId: "l2-atlas-deploy", targetVersion: 5 },
    faultType: "missing_constraint",
    suggestedAction: "rederive_l2",
    validity: "refuted",
    utility: "untested",
    failureOwner: "derivation",
    rawScore: 0.96,
    supportingIds: ["l1-backup"],
    evidence: [{
      kind: "l1_l2_derivation",
      supportingIds: ["l1-backup"],
      claim: "backup constraint omitted",
      evidenceHash: canonicalHash("omission"),
      verifierId: "graph-v1",
    }],
    reasonCodes: ["decisive_l1_omitted"],
  };

  it("fails closed if a deserialized root is mutated after construction", async () => {
    const mutated = structuredClone(createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z"));
    mutated.memoryRelevance.decision = "no_match";
    let inspectorCalled = false;
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect() { inspectorCalled = true; return [candidate]; },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(_observation, candidates) { return identifiedCertificate(candidate, candidates); },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
    );
    const result = await router.route(mutated);
    expect(result.draft.reasonCodes[0]).toMatch(/gate0_invalid_root_observation/);
    expect(inspectorCalled).toBe(false);
  });

  it.each(["no_match", "unknown"] as const)(
    "abstains before candidate generation when independent relevance is %s",
    async (decision) => {
      const input = rootInput();
      const noMatchAuthorityDigest = canonicalHash("no-match task contract v1");
      input.memoryRelevance = decision === "unknown"
        ? {
          schemaVersion: "tdai-memory-relevance.v1",
          decision,
          basis: "unavailable",
          evaluatorId: "no-match-unavailable",
          evaluatorVersion: "1",
          evaluatorDigest: canonicalHash("no-match-unavailable-v1"),
          policyDigest: canonicalHash("no-match-unavailable-policy-v1"),
          evaluatedAt: "2026-09-03T00:00:00.000Z",
          evidenceHash: null,
          authority: null,
          calibrationArtifactDigest: null,
          subjectBindingHash: memoryRelevanceSubjectBindingHash({
            taskRunId: input.taskRunId,
            sessionId: input.sessionId,
            preRetrievalContextHash: input.preRetrievalContextHash,
            authority: null,
          }),
          independentOfProductionRetrieval: true,
          evaluationSurface: "pre_retrieval_subject_and_authority_only",
        }
        : {
          schemaVersion: "tdai-memory-relevance.v1",
          decision,
          basis: "deterministic_task_contract",
          evaluatorId: "no-match-contract-v1",
          evaluatorVersion: "1",
          evaluatorDigest: canonicalHash("no-match-contract-evaluator-v1"),
          policyDigest: canonicalHash("no-match-contract-policy-v1"),
          evaluatedAt: "2026-09-03T00:00:00.000Z",
          evidenceHash: canonicalHash("task requires no memory"),
          authority: {
            authorityId: "no-match-task-contract",
            authorityVersion: "1",
            effectiveAt: "2026-09-03T00:00:00.000Z",
            authoritySnapshotDigest: noMatchAuthorityDigest,
          },
          calibrationArtifactDigest: null,
          subjectBindingHash: memoryRelevanceSubjectBindingHash({
            taskRunId: input.taskRunId,
            sessionId: input.sessionId,
            preRetrievalContextHash: input.preRetrievalContextHash,
            authority: {
              authorityId: "no-match-task-contract",
              authorityVersion: "1",
              effectiveAt: "2026-09-03T00:00:00.000Z",
              authoritySnapshotDigest: noMatchAuthorityDigest,
            },
          }),
          independentOfProductionRetrieval: true,
          evaluationSurface: "pre_retrieval_subject_and_authority_only",
        };
      let inspectorCalled = false;
      const router = new GatedCascadeLayerRouter(
        {
          id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
          async inspect() { inspectorCalled = true; return [candidate]; },
        },
        {
          id: "tuple-authority-v1",
          basis: "capture_authority",
          authorityVersion: "1",
          async verify(_observation, candidates) { return identifiedCertificate(candidate, candidates); },
        },
        { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
      );
      const result = await router.route(createRootObservation(input, "2026-09-03T00:00:00.000Z"));
      expect(result.draft.decision).toBe("abstain");
      expect(result.draft.reasonCodes[0]).toMatch(/gate0_independent/);
      expect(inspectorCalled).toBe(false);
    },
  );

  it("passes only score-free, frozen projections to the identifiability authority", async () => {
    const input = rootInput();
    input.outcome = outcome("pass");
    (input as unknown as Record<string, unknown>).rawScore = 1;
    (input.exposures[0] as unknown as Record<string, unknown>).confidence = 1;
    (input.outcome.validators[0] as unknown as Record<string, unknown>).rawScore = 1;
    const observation = createRootObservation(input, "2026-09-03T00:00:00.000Z");
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect(scoreFreeObservation) {
          expect(scoreFreeObservation).not.toHaveProperty("rawScore");
          expect(scoreFreeObservation.exposures[0]).not.toHaveProperty("score");
          expect(scoreFreeObservation.exposures[0]).not.toHaveProperty("rank");
          expect(scoreFreeObservation.exposures[0]).not.toHaveProperty("confidence");
          expect(scoreFreeObservation.outcome?.validators[0]).not.toHaveProperty("score");
          expect(scoreFreeObservation.outcome?.validators[0]).not.toHaveProperty("rawScore");
          return [candidate];
        },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(scoreFreeObservation, scoreFreeCandidates) {
          expect(scoreFreeCandidates[0]).not.toHaveProperty("rawScore");
          expect(scoreFreeObservation.exposures[0]).not.toHaveProperty("score");
          expect(scoreFreeObservation.exposures[0]).not.toHaveProperty("rank");
          expect(scoreFreeObservation.outcome?.validators[0]).not.toHaveProperty("score");
          expect(Object.keys(scoreFreeCandidates[0]!).sort()).toEqual([
            "faultType", "suggestedAction", "target",
          ]);
          expect(Object.isFrozen(scoreFreeObservation)).toBe(true);
          expect(Object.isFrozen(scoreFreeCandidates)).toBe(true);
          return identifiedCertificate(candidate, scoreFreeCandidates);
        },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
    );
    expect((await router.route(observation)).draft.decision).toBe("emit");
  });

  it("excludes a graph-resident version-zero target before identifiability", async () => {
    const input = rootInput();
    input.graph.nodes.push({
      layer: "L1",
      id: "legacy-l1",
      version: 0,
      contentHash: canonicalHash("legacy"),
      metadataHash: canonicalHash({}),
      scopeHash: canonicalHash({}),
      entityBindingHash: canonicalHash({}),
      observedAt: "2026-09-03T00:00:00.000Z",
    });
    const unresolved = {
      ...candidate,
      target: { targetType: "L1_NODE" as const, targetId: "legacy-l1", targetVersion: 0 },
    };
    let verifierCalled = false;
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect() { return [unresolved]; },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(_observation, candidates) {
          verifierCalled = true;
          return identifiedCertificate(unresolved, candidates);
        },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
    );
    const result = await router.route(createRootObservation(input, "2026-09-03T00:00:00.000Z"));
    expect(result.draft.decision).toBe("abstain");
    expect(result.draft.reasonCodes).toContain("gate1_no_exact_version_candidate");
    expect(verifierCalled).toBe(false);
  });

  it("routes a high-confidence structural candidate without an API call", async () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect() { return [candidate]; },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(_observation, candidates) { return identifiedCertificate(candidate, candidates); },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
    );
    const result = await router.route(observation);
    expect(result.draft).toMatchObject({
      decision: "emit",
      target: { targetType: "L2_NODE", targetId: "l2-atlas-deploy", targetVersion: 5 },
      faultType: "missing_constraint",
      validity: "refuted",
      utility: "untested",
      failureOwner: "derivation",
      identifiabilityCertificate: { status: "identified", noSignalWorldExcluded: true },
    });
    expect(result.gateTrace.some((gate) => gate.gate === "escalation")).toBe(false);
  });

  it("does not let high scores replace complete-tuple identifiability", async () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const competing = {
      ...candidate,
      target: { targetType: "L1_NODE" as const, targetId: "l1-backup", targetVersion: 1 },
      rawScore: 0.93,
    };
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1",
        enumerationMode: "complete_admissible_tuple_universe",
        authorityVersion: "1",
        async inspect() {
          return [candidate, competing];
        },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(_observation, candidates) {
          return createCompleteTupleIdentifiabilityCertificate({
            verifierId: "tuple-authority-v1",
            basis: "capture_authority",
            status: "ambiguous",
            candidateTuples: candidates,
            competingTuples: candidates,
            noSignalWorldExcluded: true,
            evidence: [IDENTIFIABILITY_EVIDENCE],
            reasonCodes: ["two_compatible_tuples"],
          });
        },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
    );
    const result = await router.route(observation);
    expect(result.draft.decision).toBe("abstain");
    expect(result.draft.reasonCodes).toContain("gate2_complete_tuple_ambiguous");
    expect(result.draft.identifiabilityCertificate?.candidateTupleKeys).toHaveLength(2);
  });

  it("rejects a strong judge target/fault outside the certified candidate set", async () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const lowScoreCandidate = { ...candidate, rawScore: 0.4 };
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect() { return [lowScoreCandidate]; },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(_observation, candidates) { return identifiedCertificate(lowScoreCandidate, candidates); },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
      undefined,
      {
        id: "strong-judge-v1",
        async adjudicate() {
          return {
            ...lowScoreCandidate,
            target: { targetType: "L1_NODE", targetId: "l1-region", targetVersion: 3 },
            faultType: "wrong_scope",
            suggestedAction: "repair_scope",
            rawScore: 0.99,
          };
        },
      },
    );
    const result = await router.route(observation);
    expect(result.draft.decision).toBe("abstain");
    expect(result.draft.reasonCodes).toContain("gate3_strong_judge_out_of_set");
  });

  it("fails closed when a certificate is bound to a different candidate set", async () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const other = {
      ...candidate,
      target: { targetType: "L1_NODE" as const, targetId: "l1-backup", targetVersion: 1 },
    };
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect() { return [candidate]; },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify() { return identifiedCertificate(other, [other]); },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
    );
    const result = await router.route(observation);
    expect(result.draft.decision).toBe("abstain");
    expect(result.draft.reasonCodes[0]).toMatch(/candidate set/);
  });

  it("does not accept a score-bearing object as an identifiability certificate", async () => {
    const observation = createRootObservation(rootInput(), "2026-09-03T00:00:00.000Z");
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect() { return [candidate]; },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(_observation, candidates) {
          return { ...identifiedCertificate(candidate, candidates), score: 1 };
        },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
    );
    const result = await router.route(observation);
    expect(result.draft.decision).toBe("abstain");
    expect(result.draft.reasonCodes[0]).toMatch(/cannot be certified by a score/);
  });

  it("does not replay or blame a retrieved-only target as task harmful", async () => {
    const input = rootInput();
    input.exposures[0] = { ...input.exposures[0]!, state: "retrieved" };
    const observation = createRootObservation(input, "2026-09-03T00:00:00.000Z");
    const harmful: RouteCandidate = {
      ...candidate,
      target: { targetType: "L1_NODE", targetId: "l1-region", targetVersion: 3 },
      faultType: "task_harmful",
      suggestedAction: "quarantine_candidate",
      validity: "supported",
      utility: "harmful",
      failureOwner: "memory_content",
      rawScore: 0.99,
    };
    let replayCalled = false;
    const router = new GatedCascadeLayerRouter(
      {
        id: "rules-v1", enumerationMode: "complete_admissible_tuple_universe", authorityVersion: "1",
        async inspect() { return [harmful]; },
      },
      {
        id: "tuple-authority-v1",
        basis: "capture_authority",
        authorityVersion: "1",
        async verify(_observation, candidates) { return identifiedCertificate(harmful, candidates); },
      },
      { version: "isotonic-dev-v1", calibrate({ rawScore }) { return rawScore; } },
      undefined,
      undefined,
      {
        id: "replay-v1",
        async verify() {
          replayCalled = true;
          return { status: "replay_verified", score: 1, evidence: [] };
        },
      },
    );
    const result = await router.route(observation);
    expect(result.draft.decision).toBe("abstain");
    expect(result.draft.reasonCodes).toContain("gate4_harmful_target_not_exposed_or_used");
    expect(replayCalled).toBe(false);
  });
});
