import { createHash } from "node:crypto";

import type { L1SearchResult } from "../store/types.js";
import type { StructuredRecallTrace } from "./types.js";

export interface RecallRenderObservation {
  recordId: string;
  renderedText: string;
  injected: boolean;
  truncated: boolean;
}
export interface BuildRecallTraceInput {
  traceId: string;
  recordedAt: string;
  sessionId: string;
  sessionKey: string;
  userId: string;
  agentId: string;
  taskId: string;
  query: string;
  renderedPrompt: string;
  recalled: L1SearchResult[];
  renderObservations: RecallRenderObservation[];
}

interface ProvenanceMetadata {
  logicalId: string | null;
  sourceIds: string[];
}

function hash(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function parseProvenance(metadataJson: string, recordId: string, warnings: string[]): ProvenanceMetadata {
  if (!metadataJson.trim()) return { logicalId: null, sourceIds: [] };
  let metadata: unknown;
  try {
    metadata = JSON.parse(metadataJson);
  } catch {
    warnings.push(`invalid_metadata_json:${recordId}`);
    return { logicalId: null, sourceIds: [] };
  }
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    warnings.push(`invalid_metadata_shape:${recordId}`);
    return { logicalId: null, sourceIds: [] };
  }
  const provenance = (metadata as Record<string, unknown>)._tdai_provenance;
  if (!provenance || typeof provenance !== "object" || Array.isArray(provenance)) {
    return { logicalId: null, sourceIds: [] };
  }
  const row = provenance as Record<string, unknown>;
  const logicalId = typeof row.logicalId === "string" && row.logicalId.trim() ? row.logicalId : null;
  const sourceIds = Array.isArray(row.sourceIds)
    ? row.sourceIds.filter((sourceId): sourceId is string => typeof sourceId === "string" && Boolean(sourceId.trim()))
    : [];
  if (row.sourceIds !== undefined && sourceIds.length !== (Array.isArray(row.sourceIds) ? row.sourceIds.length : 0)) {
    warnings.push(`invalid_provenance_source_ids:${recordId}`);
  }
  return { logicalId, sourceIds };
}

export function buildStructuredRecallTrace(input: BuildRecallTraceInput): StructuredRecallTrace {
  if (!input.traceId || !input.query || !input.renderedPrompt) {
    throw new Error("traceId, query and renderedPrompt are required");
  }
  const recalledIds = input.recalled.map((row) => row.record_id);
  if (new Set(recalledIds).size !== recalledIds.length) throw new Error("Recalled record IDs must be unique");
  const observations = new Map<string, RecallRenderObservation>();
  for (const observation of input.renderObservations) {
    if (observations.has(observation.recordId)) throw new Error(`Duplicate render observation ${observation.recordId}`);
    observations.set(observation.recordId, observation);
  }
  const unknownObservation = input.renderObservations.find((observation) => !recalledIds.includes(observation.recordId));
  if (unknownObservation) throw new Error(`Render observation references unknown record ${unknownObservation.recordId}`);
  const missingObservation = recalledIds.find((recordId) => !observations.has(recordId));
  if (missingObservation) throw new Error(`Missing render observation for ${missingObservation}`);

  const warnings: string[] = [];
  const candidates = input.recalled.map((row, index) => {
    const observation = observations.get(row.record_id)!;
    const provenance = parseProvenance(row.metadata_json, row.record_id, warnings);
    if (observation.injected && !observation.renderedText) {
      throw new Error(`Injected candidate ${row.record_id} requires renderedText`);
    }
    return {
      recordId: row.record_id,
      logicalId: provenance.logicalId,
      version: row.version,
      contentHash: hash(row.content),
      renderedHash: hash(observation.renderedText),
      observedAt: row.timestamp_start || row.timestamp_str,
      rank: index + 1,
      score: row.score,
      injected: observation.injected,
      truncated: observation.truncated,
      sourceIds: provenance.sourceIds,
      metadataHash: hash(row.metadata_json)
    };
  });
  return {
    schemaVersion: "tdai-recall-trace.v1",
    traceId: input.traceId,
    recordedAt: input.recordedAt,
    sessionId: input.sessionId,
    sessionKey: input.sessionKey,
    userId: input.userId,
    agentId: input.agentId,
    taskId: input.taskId,
    queryHash: hash(input.query),
    renderedPromptHash: hash(input.renderedPrompt),
    candidates,
    warnings
  };
}
