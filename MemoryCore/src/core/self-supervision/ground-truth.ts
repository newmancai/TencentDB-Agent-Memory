import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { assertMemoryGraph, canonicalHash } from "./observation-plane.js";
import type {
  LayerFaultType,
  LayerMemoryNode,
  MemoryFeedbackTarget,
  MemoryGraphEdge,
  MemoryLayer,
  MemoryNodeRef,
  SuggestedAction,
  TaskOutcomeObservation,
} from "./types.js";

export interface RawGraphNode {
  layer: MemoryLayer;
  id: string;
  version: number;
  content: string;
  metadata: Record<string, unknown>;
  scope: Record<string, string>;
  entityBindings: Record<string, string>;
  observedAt: string;
}

export interface GroundTruthGraphNode extends LayerMemoryNode {
  content: string;
  metadata: Record<string, unknown>;
  scope: Record<string, string>;
  entityBindings: Record<string, string>;
}

export interface GroundTruthGraphEdge extends MemoryGraphEdge {
  metadata: Record<string, unknown>;
}

export interface GroundTruthMemoryGraph {
  nodes: GroundTruthGraphNode[];
  edges: GroundTruthGraphEdge[];
}

/**
 * The model-facing graph contains the corrupted, already-sanitized evidence.
 * It intentionally has no clean graph, repair graph, mutation manifest, or gold
 * target, but it cannot be hash-only: semantic faults require source/content.
 */
export type LocalizationDetectorGraph = GroundTruthMemoryGraph;

export interface RawGraphEdge {
  edgeId: string;
  version: number;
  relation: MemoryGraphEdge["relation"];
  from: MemoryNodeRef;
  to: MemoryNodeRef;
  metadata: Record<string, unknown>;
}

function materializeNode(node: RawGraphNode): GroundTruthGraphNode {
  return {
    ...structuredClone(node),
    contentHash: canonicalHash(node.content),
    metadataHash: canonicalHash(node.metadata),
    scopeHash: canonicalHash(node.scope),
    entityBindingHash: canonicalHash(node.entityBindings),
  };
}

function materializeEdge(edge: RawGraphEdge): GroundTruthGraphEdge {
  return {
    ...structuredClone(edge),
    metadataHash: canonicalHash(edge.metadata),
  };
}

export function buildGroundTruthGraph(input: { nodes: RawGraphNode[]; edges: RawGraphEdge[] }): GroundTruthMemoryGraph {
  const graph: GroundTruthMemoryGraph = {
    nodes: input.nodes.map(materializeNode),
    edges: input.edges.map(materializeEdge),
  };
  assertMemoryGraph(graph);
  return graph;
}

export interface NodeFaultInjection {
  targetType: "L1_NODE" | "L2_NODE";
  targetId: string;
  targetVersion: number;
  faultType: LayerFaultType;
  suggestedAction: SuggestedAction;
  patch: Partial<Pick<RawGraphNode, "content" | "metadata" | "scope" | "entityBindings">>;
}

export interface EdgeFaultInjection {
  targetType: "L1_L2_EDGE";
  targetId: string;
  targetVersion: number;
  faultType: LayerFaultType;
  suggestedAction: SuggestedAction;
  patch: Partial<Pick<RawGraphEdge, "from" | "to" | "metadata">>;
}

export type ExactFaultInjection = NodeFaultInjection | EdgeFaultInjection;

export interface ExactMutationManifest {
  operator: "single_node_patch" | "single_edge_patch";
  target: MemoryFeedbackTarget;
  faultType: LayerFaultType;
  suggestedAction: SuggestedAction;
  changedFields: string[];
  beforeEntityHash: string;
  afterEntityHash: string;
  injectorVersion: "tdai-exact-injector.v1";
}

export interface LocalizationTaskSpec {
  taskId: string;
  queryHash: string;
  oracleId: string;
  oracleVersion: string;
}

export interface LocalizationDetectorView {
  schemaVersion: "tdai-localization-view.v1";
  exampleId: string;
  splitGroup: string;
  task: LocalizationTaskSpec;
  corruptedGraph: LocalizationDetectorGraph;
  corruptedGraphHash: string;
  dataClassification: "shadow_benchmark";
  memoryIngestionAllowed: false;
}

export interface ExactLocalizationLabel {
  schemaVersion: "tdai-exact-localization-label.v1";
  exampleId: string;
  target: MemoryFeedbackTarget;
  faultType: LayerFaultType;
  suggestedAction: SuggestedAction;
  mutation: ExactMutationManifest;
  cleanGraphHash: string;
  corruptedGraphHash: string;
  repairedGraphHash: string;
  structuralGroundTruth: "exact_by_single_intervention";
  causalQualification: "pending" | "qualified" | "rejected";
  qualificationReasonCodes: string[];
  optimizationReady: false;
}

export interface ExactLocalizationExample {
  detectorView: LocalizationDetectorView;
  label: ExactLocalizationLabel;
  cleanGraph: GroundTruthMemoryGraph;
  corruptedGraph: GroundTruthMemoryGraph;
  repairedGraph: GroundTruthMemoryGraph;
}

function locateNode(graph: GroundTruthMemoryGraph, injection: NodeFaultInjection): GroundTruthGraphNode {
  const layer = injection.targetType === "L1_NODE" ? "L1" : "L2";
  const matches = graph.nodes.filter(
    (node) => node.layer === layer && node.id === injection.targetId && node.version === injection.targetVersion,
  );
  if (matches.length !== 1) throw new Error(`Injection target must resolve to exactly one ${injection.targetType}`);
  return matches[0]!;
}

function locateEdge(graph: GroundTruthMemoryGraph, injection: EdgeFaultInjection): GroundTruthGraphEdge {
  const matches = graph.edges.filter(
    (edge) => edge.edgeId === injection.targetId && edge.version === injection.targetVersion,
  );
  if (matches.length !== 1 || matches[0]!.relation !== "L1_DERIVES_L2") {
    throw new Error("Injection target must resolve to exactly one L1_DERIVES_L2 edge");
  }
  return matches[0]!;
}

function applyNodePatch(node: GroundTruthGraphNode, patch: NodeFaultInjection["patch"]): string[] {
  const allowed = ["content", "metadata", "scope", "entityBindings"] as const;
  const changed: string[] = [];
  for (const key of allowed) {
    if (patch[key] === undefined) continue;
    if (canonicalHash(node[key]) === canonicalHash(patch[key])) continue;
    (node as RawGraphNode)[key] = structuredClone(patch[key] as never);
    changed.push(key);
  }
  node.contentHash = canonicalHash(node.content);
  node.metadataHash = canonicalHash(node.metadata);
  node.scopeHash = canonicalHash(node.scope);
  node.entityBindingHash = canonicalHash(node.entityBindings);
  return changed;
}

function applyEdgePatch(edge: GroundTruthGraphEdge, patch: EdgeFaultInjection["patch"]): string[] {
  const allowed = ["from", "to", "metadata"] as const;
  const changed: string[] = [];
  for (const key of allowed) {
    if (patch[key] === undefined) continue;
    if (canonicalHash(edge[key]) === canonicalHash(patch[key])) continue;
    (edge as RawGraphEdge)[key] = structuredClone(patch[key] as never);
    changed.push(key);
  }
  edge.metadataHash = canonicalHash(edge.metadata);
  return changed;
}

function targetFromNode(node: GroundTruthGraphNode): MemoryFeedbackTarget {
  if (node.layer === "L1") return { targetType: "L1_NODE", targetId: node.id, targetVersion: node.version };
  if (node.layer === "L2") return { targetType: "L2_NODE", targetId: node.id, targetVersion: node.version };
  throw new Error("L0 nodes cannot be feedback targets");
}

function targetFromEdge(edge: GroundTruthGraphEdge): MemoryFeedbackTarget {
  if (edge.from.layer !== "L1" || edge.to.layer !== "L2") throw new Error("Feedback edge must connect L1 to L2");
  return {
    targetType: "L1_L2_EDGE",
    targetId: edge.edgeId,
    targetVersion: edge.version,
    from: { ...edge.from, layer: "L1" },
    to: { ...edge.to, layer: "L2" },
  };
}

function assertSingleEntityMutation(
  clean: GroundTruthMemoryGraph,
  corrupted: GroundTruthMemoryGraph,
  targetKind: "node" | "edge",
  targetId: string,
  targetVersion: number,
): void {
  const nodeDiffs = clean.nodes.filter((node, index) => canonicalHash(node) !== canonicalHash(corrupted.nodes[index]));
  const edgeDiffs = clean.edges.filter((edge, index) => canonicalHash(edge) !== canonicalHash(corrupted.edges[index]));
  if (targetKind === "node") {
    if (nodeDiffs.length !== 1 || edgeDiffs.length !== 0) throw new Error("Fault injection changed more than one graph entity");
    if (nodeDiffs[0]!.id !== targetId || nodeDiffs[0]!.version !== targetVersion) throw new Error("Changed node is not the declared target");
  } else {
    if (edgeDiffs.length !== 1 || nodeDiffs.length !== 0) throw new Error("Fault injection changed more than one graph entity");
    if (edgeDiffs[0]!.edgeId !== targetId || edgeDiffs[0]!.version !== targetVersion) throw new Error("Changed edge is not the declared target");
  }
}

export function createExactLocalizationExample(input: {
  cleanGraph: GroundTruthMemoryGraph;
  injection: ExactFaultInjection;
  task: LocalizationTaskSpec;
  splitGroup: string;
  seed: number;
}): ExactLocalizationExample {
  if (!input.splitGroup.trim()) throw new Error("splitGroup is required");
  if (!Number.isSafeInteger(input.seed)) throw new Error("seed must be an integer");
  for (const [field, value] of Object.entries(input.task)) {
    if (!value.trim()) throw new Error(`task.${field} is required`);
  }
  assertMemoryGraph(input.cleanGraph);
  const cleanGraph = structuredClone(input.cleanGraph);
  const corruptedGraph = structuredClone(input.cleanGraph);
  const repairedGraph = structuredClone(input.cleanGraph);
  let target: MemoryFeedbackTarget;
  let changedFields: string[];
  let beforeEntityHash: string;
  let afterEntityHash: string;
  let operator: ExactMutationManifest["operator"];

  if (input.injection.targetType === "L1_L2_EDGE") {
    const before = locateEdge(cleanGraph, input.injection);
    const after = locateEdge(corruptedGraph, input.injection);
    beforeEntityHash = canonicalHash(before);
    changedFields = applyEdgePatch(after, input.injection.patch);
    assertMemoryGraph(corruptedGraph);
    target = targetFromEdge(after);
    afterEntityHash = canonicalHash(after);
    operator = "single_edge_patch";
    assertSingleEntityMutation(cleanGraph, corruptedGraph, "edge", input.injection.targetId, input.injection.targetVersion);
  } else {
    const before = locateNode(cleanGraph, input.injection);
    const after = locateNode(corruptedGraph, input.injection);
    beforeEntityHash = canonicalHash(before);
    changedFields = applyNodePatch(after, input.injection.patch);
    assertMemoryGraph(corruptedGraph);
    target = targetFromNode(after);
    afterEntityHash = canonicalHash(after);
    operator = "single_node_patch";
    assertSingleEntityMutation(cleanGraph, corruptedGraph, "node", input.injection.targetId, input.injection.targetVersion);
  }
  if (changedFields.length === 0 || beforeEntityHash === afterEntityHash) {
    throw new Error("Fault injection must make a non-empty change");
  }

  const cleanGraphHash = canonicalHash(cleanGraph);
  const corruptedGraphHash = canonicalHash(corruptedGraph);
  const repairedGraphHash = canonicalHash(repairedGraph);
  if (cleanGraphHash !== repairedGraphHash || cleanGraphHash === corruptedGraphHash) {
    throw new Error("Clean/corrupt/repair triplet invariant failed");
  }
  const exampleHash = canonicalHash({
    cleanGraphHash,
    injection: input.injection,
    task: input.task,
    splitGroup: input.splitGroup,
    seed: input.seed,
  });
  const exampleId = `loc-${exampleHash.slice(0, 24)}`;
  const mutation: ExactMutationManifest = {
    operator,
    target,
    faultType: input.injection.faultType,
    suggestedAction: input.injection.suggestedAction,
    changedFields,
    beforeEntityHash,
    afterEntityHash,
    injectorVersion: "tdai-exact-injector.v1",
  };
  return {
    detectorView: {
      schemaVersion: "tdai-localization-view.v1",
      exampleId,
      splitGroup: input.splitGroup,
      task: structuredClone(input.task),
      corruptedGraph: structuredClone(corruptedGraph),
      corruptedGraphHash,
      dataClassification: "shadow_benchmark",
      memoryIngestionAllowed: false,
    },
    label: {
      schemaVersion: "tdai-exact-localization-label.v1",
      exampleId,
      target,
      faultType: input.injection.faultType,
      suggestedAction: input.injection.suggestedAction,
      mutation,
      cleanGraphHash,
      corruptedGraphHash,
      repairedGraphHash,
      structuralGroundTruth: "exact_by_single_intervention",
      causalQualification: "pending",
      qualificationReasonCodes: ["awaiting_clean_corrupt_repair_and_negative_control"],
      optimizationReady: false,
    },
    cleanGraph,
    corruptedGraph,
    repairedGraph,
  };
}

export interface QualificationRuns {
  clean: TaskOutcomeObservation;
  corrupt: TaskOutcomeObservation;
  repair: TaskOutcomeObservation;
  negativeControl: TaskOutcomeObservation;
}

function deterministicValidatorKey(outcome: TaskOutcomeObservation): string {
  return outcome.validators
    .filter((validator) => validator.oracleKind !== "blind_judge")
    .map((validator) => `${validator.validatorId}@${validator.validatorVersion}`)
    .sort()
    .join("|");
}

function objectiveVerdict(outcome: TaskOutcomeObservation): "pass" | "fail" | "unverifiable" {
  const validators = outcome.validators.filter((validator) => validator.oracleKind !== "blind_judge");
  if (validators.length === 0 || validators.some((validator) => validator.status === "error" || validator.status === "unverifiable")) {
    return "unverifiable";
  }
  if (validators.some((validator) => validator.status === "fail")) return "fail";
  return validators.every((validator) => validator.status === "pass") ? "pass" : "unverifiable";
}

export function qualifyExactLocalizationExample(
  example: ExactLocalizationExample,
  runs: QualificationRuns,
): ExactLocalizationExample {
  const output = structuredClone(example);
  const all = [runs.clean, runs.corrupt, runs.repair, runs.negativeControl];
  const environmentComparable = new Set(all.map((run) => run.environmentHash)).size === 1;
  const modelComparable = new Set(all.map((run) => run.modelId)).size === 1;
  const validatorComparable = new Set(all.map(deterministicValidatorKey)).size === 1
    && deterministicValidatorKey(runs.clean).length > 0;
  const declaredOracle = `${example.detectorView.task.oracleId}@${example.detectorView.task.oracleVersion}`;
  const declaredOraclePresent = all.every((run) => deterministicValidatorKey(run).split("|").includes(declaredOracle));
  const verdicts = {
    clean: objectiveVerdict(runs.clean),
    corrupt: objectiveVerdict(runs.corrupt),
    repair: objectiveVerdict(runs.repair),
    negativeControl: objectiveVerdict(runs.negativeControl),
  };
  const reasons: string[] = [];
  if (!environmentComparable) reasons.push("environment_mismatch");
  if (!modelComparable) reasons.push("model_mismatch");
  if (!validatorComparable) reasons.push("validator_mismatch_or_missing_objective_oracle");
  if (!declaredOraclePresent) reasons.push("declared_oracle_missing");
  if (verdicts.clean !== "pass") reasons.push(`clean_${verdicts.clean}`);
  if (verdicts.corrupt !== "fail") reasons.push(`corrupt_${verdicts.corrupt}`);
  if (verdicts.repair !== "pass") reasons.push(`repair_${verdicts.repair}`);
  if (verdicts.negativeControl !== "pass") reasons.push(`negative_control_${verdicts.negativeControl}`);
  output.label.causalQualification = reasons.length === 0 ? "qualified" : "rejected";
  output.label.qualificationReasonCodes = reasons.length === 0 ? ["clean_pass_corrupt_fail_repair_pass_control_pass"] : reasons;
  return output;
}

export class ExactLocalizationDatasetStore {
  readonly viewsPath: string;
  readonly labelsPath: string;
  readonly commitsPath: string;
  private readonly exampleIds = new Set<string>();

  constructor(rootDirectory: string) {
    if (!rootDirectory.trim()) throw new Error("Dataset root directory is required");
    mkdirSync(rootDirectory, { recursive: true, mode: 0o700 });
    this.viewsPath = resolve(rootDirectory, "localization-views.v1.jsonl");
    this.labelsPath = resolve(rootDirectory, "localization-labels.v1.jsonl");
    this.commitsPath = resolve(rootDirectory, "localization-commits.v1.jsonl");
    const viewHashes = this.readRowHashes(this.viewsPath, "view");
    const labelHashes = this.readRowHashes(this.labelsPath, "label");
    try {
      const raw = readFileSync(this.commitsPath, "utf8");
      for (const line of raw.split("\n").filter(Boolean)) {
        const row = JSON.parse(line) as { exampleId?: string; viewHash?: string; labelHash?: string };
        if (!row.exampleId || !row.viewHash || !row.labelHash) throw new Error("Malformed localization commit row");
        if (!viewHashes.has(row.exampleId) || !labelHashes.has(row.exampleId)) {
          throw new Error(`Committed localization example is incomplete: ${row.exampleId}`);
        }
        if (viewHashes.get(row.exampleId) !== row.viewHash || labelHashes.get(row.exampleId) !== row.labelHash) {
          throw new Error(`Localization commit hash mismatch: ${row.exampleId}`);
        }
        this.exampleIds.add(row.exampleId);
      }
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    const uncommitted = [...new Set([...viewHashes.keys(), ...labelHashes.keys()])]
      .filter((id) => !this.exampleIds.has(id));
    if (uncommitted.length > 0) {
      throw new Error(`Incomplete localization dataset transaction: ${uncommitted.join(",")}`);
    }
  }

  private readRowHashes(path: string, kind: "view" | "label"): Map<string, string> {
    const hashes = new Map<string, string>();
    try {
      const raw = readFileSync(path, "utf8");
      for (const line of raw.split("\n").filter(Boolean)) {
        const row = JSON.parse(line) as { exampleId?: string };
        if (!row.exampleId) throw new Error(`Malformed localization ${kind} row`);
        if (hashes.has(row.exampleId)) throw new Error(`Duplicate localization ${kind} row ${row.exampleId}`);
        hashes.set(row.exampleId, canonicalHash(row));
      }
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    return hashes;
  }

  append(example: ExactLocalizationExample): void {
    if (this.exampleIds.has(example.label.exampleId)) throw new Error(`Duplicate example ${example.label.exampleId}`);
    if (example.detectorView.exampleId !== example.label.exampleId) throw new Error("View/label example ID mismatch");
    if (example.detectorView.memoryIngestionAllowed !== false || example.label.optimizationReady !== false) {
      throw new Error("Localization dataset must remain shadow-only");
    }
    // Detector inputs and gold labels are physically separated to make leak audits simple.
    appendFileSync(this.viewsPath, `${JSON.stringify(example.detectorView)}\n`, { encoding: "utf8", mode: 0o600 });
    appendFileSync(this.labelsPath, `${JSON.stringify(example.label)}\n`, { encoding: "utf8", mode: 0o600 });
    // A pair becomes consumable only after this final commit marker. A crash before
    // it is detected on reopen and cannot silently create a partially-labelled row.
    appendFileSync(this.commitsPath, `${JSON.stringify({
      exampleId: example.label.exampleId,
      viewHash: canonicalHash(example.detectorView),
      labelHash: canonicalHash(example.label),
    })}\n`, { encoding: "utf8", mode: 0o600 });
    this.exampleIds.add(example.label.exampleId);
  }
}
