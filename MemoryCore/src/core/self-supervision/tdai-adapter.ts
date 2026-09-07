import type { L0QueryRow, L1RecordRow, ProfileRecord } from "../store/types.js";
import { assertMemoryGraph, canonicalHash } from "./observation-plane.js";
import type {
  LayerExposure,
  MemoryGraphEdge,
  MemoryGraphSnapshot,
  MemoryNodeRef,
  RecallCandidateTrace,
} from "./types.js";

interface ParsedProvenance {
  sourceIds: string[];
  entityBindings: Record<string, string>;
  replaces: MemoryNodeRef[];
}

export interface L2LineageRecord {
  l2: MemoryNodeRef & { layer: "L2" };
  sources: Array<MemoryNodeRef & { layer: "L1" }>;
  edgeVersion: number;
  claimIds: string[];
  aggregatorVersion: string;
}

export interface BuildTdaiGraphInput {
  l0: L0QueryRow[];
  l1: L1RecordRow[];
  l2: ProfileRecord[];
  /**
   * Optional source IDs recovered from append-only L1 JSONL/version snapshots.
   * The current SQLite read path drops source_message_ids, so callers must pass
   * this map or persist _tdai_provenance before exact L0→L1 edges are possible.
   */
  l1SourceIdsByRecord?: Readonly<Record<string, string[]>>;
  /** L2 lineage is currently absent from scene block/index files and must be sidecar-supplied. */
  l2Lineage?: L2LineageRecord[];
}

export interface BuildTdaiGraphResult {
  graph: MemoryGraphSnapshot;
  warnings: string[];
  missingAssociations: Array<"L0_L1_SOURCE" | "L1_L2_DERIVATION" | "L2_VERSION">;
}

function parseMetadata(metadataJson: string, recordId: string, warnings: string[]): ParsedProvenance {
  let metadata: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(metadataJson) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) metadata = parsed as Record<string, unknown>;
    else warnings.push(`invalid_l1_metadata_shape:${recordId}`);
  } catch {
    warnings.push(`invalid_l1_metadata_json:${recordId}`);
  }
  const raw = metadata._tdai_provenance;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return { sourceIds: [], entityBindings: {}, replaces: [] };
  }
  const provenance = raw as Record<string, unknown>;
  const rawSources = provenance.sourceIds ?? provenance.source_message_ids;
  const sourceIds = Array.isArray(rawSources)
    ? [...new Set(rawSources.filter((value): value is string => typeof value === "string" && Boolean(value.trim())))]
    : [];
  const entityBindings = Object.fromEntries(
    Object.entries(
      provenance.entityBindings && typeof provenance.entityBindings === "object" && !Array.isArray(provenance.entityBindings)
        ? provenance.entityBindings as Record<string, unknown>
        : {},
    ).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
  );
  const replaces: MemoryNodeRef[] = Array.isArray(provenance.replaces)
    ? provenance.replaces.flatMap((value) => {
      if (!value || typeof value !== "object" || Array.isArray(value)) return [];
      const ref = value as Record<string, unknown>;
      return typeof ref.id === "string" && Number.isSafeInteger(ref.version)
        ? [{ layer: "L1" as const, id: ref.id, version: Number(ref.version) }]
        : [];
    })
    : [];
  return { sourceIds, entityBindings, replaces };
}

function stableEdgeId(relation: MemoryGraphEdge["relation"], from: MemoryNodeRef, to: MemoryNodeRef): string {
  return `edge:v1:${canonicalHash({ relation, from, to }).slice(0, 32)}`;
}

function refKey(ref: MemoryNodeRef): string {
  return `${ref.layer}\u001f${ref.id}\u001f${ref.version}`;
}

export function buildTdaiMemoryGraph(input: BuildTdaiGraphInput): BuildTdaiGraphResult {
  const warnings: string[] = [];
  const missing = new Set<BuildTdaiGraphResult["missingAssociations"][number]>();
  const nodes: MemoryGraphSnapshot["nodes"] = [];
  const edges: MemoryGraphSnapshot["edges"] = [];
  const l0Refs = new Map<string, MemoryNodeRef>();
  const l1Refs = new Map<string, MemoryNodeRef>();
  const l2Refs = new Map<string, MemoryNodeRef>();
  const l1Provenance = new Map<string, ParsedProvenance>();

  for (const row of input.l0) {
    const ref: MemoryNodeRef = { layer: "L0", id: row.record_id, version: 1 };
    l0Refs.set(row.record_id, ref);
    nodes.push({
      ...ref,
      contentHash: canonicalHash(row.message_text),
      metadataHash: canonicalHash({ role: row.role, recordedAt: row.recorded_at }),
      scopeHash: canonicalHash({
        sessionKey: row.session_key,
        sessionId: row.session_id,
        teamId: row.team_id,
        taskId: row.task_id,
        userId: row.user_id,
        agentId: row.agent_id,
      }),
      entityBindingHash: canonicalHash({}),
      observedAt: row.recorded_at,
    });
  }

  for (const row of input.l1) {
    const ref: MemoryNodeRef = { layer: "L1", id: row.record_id, version: row.version ?? 0 };
    const parsed = parseMetadata(row.metadata_json, row.record_id, warnings);
    const recoveredSourceIds = input.l1SourceIdsByRecord?.[row.record_id] ?? [];
    parsed.sourceIds = [...new Set([...parsed.sourceIds, ...recoveredSourceIds])];
    l1Refs.set(row.record_id, ref);
    l1Provenance.set(row.record_id, parsed);
    nodes.push({
      ...ref,
      contentHash: canonicalHash(row.content),
      metadataHash: canonicalHash(row.metadata_json),
      scopeHash: canonicalHash({
        sessionKey: row.session_key,
        sessionId: row.session_id,
        teamId: row.team_id,
        taskId: row.task_id,
        userId: row.user_id,
        agentId: row.agent_id,
        sceneName: row.scene_name,
      }),
      entityBindingHash: canonicalHash(parsed.entityBindings),
      observedAt: row.updated_time || row.timestamp_start || row.timestamp_str,
    });
  }

  for (const row of input.l2.filter((profile) => profile.type === "l2")) {
    const ref: MemoryNodeRef = { layer: "L2", id: row.id, version: row.version ?? 0 };
    l2Refs.set(row.id, ref);
    if ((row.version ?? 0) === 0) {
      warnings.push(`unresolved_l2_version:${row.id}`);
      missing.add("L2_VERSION");
    }
    nodes.push({
      ...ref,
      contentHash: canonicalHash(row.content),
      metadataHash: canonicalHash({ filename: row.filename, contentMd5: row.contentMd5 }),
      scopeHash: canonicalHash({
        teamId: row.teamId ?? "",
        userId: row.userId ?? "",
        agentId: row.agentId ?? "",
        sessionId: row.sessionId ?? "",
      }),
      entityBindingHash: canonicalHash({ filename: row.filename }),
      observedAt: new Date(row.updatedAtMs).toISOString(),
    });
  }

  for (const [recordId, provenance] of l1Provenance) {
    const target = l1Refs.get(recordId)!;
    if (provenance.sourceIds.length === 0) {
      warnings.push(`missing_l0_l1_source:${recordId}`);
      missing.add("L0_L1_SOURCE");
    }
    for (const sourceId of provenance.sourceIds) {
      const source = l0Refs.get(sourceId);
      if (!source) {
        warnings.push(`unknown_l0_source:${recordId}:${sourceId}`);
        missing.add("L0_L1_SOURCE");
        continue;
      }
      edges.push({
        edgeId: stableEdgeId("L0_SUPPORTS_L1", source, target),
        version: 1,
        relation: "L0_SUPPORTS_L1",
        from: source,
        to: target,
        metadataHash: canonicalHash({ source: "_tdai_provenance" }),
      });
    }
    for (const replaced of provenance.replaces) {
      const existing = l1Refs.get(replaced.id);
      if (!existing || existing.version !== replaced.version) {
        warnings.push(`unknown_replaced_l1:${recordId}:${replaced.id}@${replaced.version}`);
        continue;
      }
      edges.push({
        edgeId: stableEdgeId("L1_SUPERSEDES_L1", target, existing),
        version: 1,
        relation: "L1_SUPERSEDES_L1",
        from: target,
        to: existing,
        metadataHash: canonicalHash({ source: "_tdai_provenance.replaces" }),
      });
    }
  }

  const lineages = input.l2Lineage ?? [];
  const lineageTargets = new Set(lineages.map((lineage) => refKey(lineage.l2)));
  for (const l2 of l2Refs.values()) {
    if (!lineageTargets.has(refKey(l2))) {
      warnings.push(`missing_l1_l2_derivation:${l2.id}@${l2.version}`);
      missing.add("L1_L2_DERIVATION");
    }
  }
  for (const lineage of lineages) {
    const target = l2Refs.get(lineage.l2.id);
    if (!target || target.version !== lineage.l2.version) {
      warnings.push(`unknown_l2_lineage_target:${lineage.l2.id}@${lineage.l2.version}`);
      missing.add("L1_L2_DERIVATION");
      continue;
    }
    for (const declaredSource of lineage.sources) {
      const source = l1Refs.get(declaredSource.id);
      if (!source || source.version !== declaredSource.version) {
        warnings.push(`unknown_l2_lineage_source:${declaredSource.id}@${declaredSource.version}`);
        missing.add("L1_L2_DERIVATION");
        continue;
      }
      edges.push({
        edgeId: stableEdgeId("L1_DERIVES_L2", source, target),
        version: lineage.edgeVersion,
        relation: "L1_DERIVES_L2",
        from: source,
        to: target,
        metadataHash: canonicalHash({
          claimIds: lineage.claimIds,
          aggregatorVersion: lineage.aggregatorVersion,
        }),
      });
    }
  }

  const graph = { nodes, edges };
  assertMemoryGraph(graph);
  return { graph, warnings, missingAssociations: [...missing].sort() };
}

export interface L2ExposureObservation {
  exposureId: string;
  l2Id: string;
  l2Version: number;
  channel: "system_l2_navigation" | "l2_file_read";
  used: boolean;
  renderedHash: string;
  truncated: boolean;
  derivationEdges: Array<{ edgeId: string; edgeVersion: number }>;
}

export function buildLayerExposures(input: {
  l1: RecallCandidateTrace[];
  l2: L2ExposureObservation[];
}): LayerExposure[] {
  const l1 = input.l1.map((candidate): LayerExposure => ({
    exposureId: `l1:${candidate.recordId}:${candidate.version}:${candidate.rank}`,
    node: { layer: "L1", id: candidate.recordId, version: candidate.version },
    state: candidate.injected ? "exposed" : "retrieved",
    channel: "prompt_l1",
    rank: candidate.rank,
    score: candidate.score,
    renderedHash: candidate.injected ? candidate.renderedHash : null,
    truncated: candidate.truncated,
    derivationEdges: [],
  }));
  const l2 = input.l2.map((observation): LayerExposure => ({
    exposureId: observation.exposureId,
    node: { layer: "L2", id: observation.l2Id, version: observation.l2Version },
    state: observation.used ? "used" : "exposed",
    channel: observation.channel,
    rank: null,
    score: null,
    renderedHash: observation.renderedHash,
    truncated: observation.truncated,
    derivationEdges: structuredClone(observation.derivationEdges),
  }));
  return [...l1, ...l2];
}
