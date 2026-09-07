import { describe, expect, it } from "vitest";

import type { L0QueryRow, L1RecordRow, ProfileRecord } from "../store/types.js";
import { buildLayerExposures, buildTdaiMemoryGraph } from "./tdai-adapter.js";

const l0: L0QueryRow = {
  record_id: "msg-1",
  session_key: "session-key",
  session_id: "session-1",
  team_id: "team-1",
  task_id: "task-1",
  user_id: "user-1",
  agent_id: "agent-1",
  role: "user",
  message_text: "Atlas 部署在上海。",
  recorded_at: "2026-09-01T00:00:00.000Z",
  timestamp: 1788220800000,
};

const l1: L1RecordRow = {
  record_id: "l1-1",
  content: "Atlas 部署在上海。",
  type: "work_fact",
  priority: 90,
  scene_name: "atlas",
  session_key: "session-key",
  session_id: "session-1",
  team_id: "team-1",
  task_id: "task-1",
  user_id: "user-1",
  agent_id: "agent-1",
  version: 2,
  timestamp_str: "2026-09-01T00:00:00.000Z",
  timestamp_start: "2026-09-01T00:00:00.000Z",
  timestamp_end: "2026-09-01T00:00:00.000Z",
  created_time: "2026-09-01T00:01:00.000Z",
  updated_time: "2026-09-01T00:01:00.000Z",
  metadata_json: JSON.stringify({
    _tdai_provenance: {
      sourceIds: ["msg-1"],
      entityBindings: { project: "atlas", region: "shanghai" },
    },
  }),
};

const l2: ProfileRecord = {
  id: "l2-1",
  type: "l2",
  filename: "atlas.md",
  content: "Atlas 上海部署场景。",
  contentMd5: "md5",
  teamId: "team-1",
  agentId: "agent-1",
  version: 4,
  createdAtMs: 1788220800000,
  updatedAtMs: 1788220860000,
};

describe("TDAI graph adapter", () => {
  it("constructs only explicitly supported provenance and lineage edges", () => {
    const result = buildTdaiMemoryGraph({
      l0: [l0],
      l1: [l1],
      l2: [l2],
      l2Lineage: [{
        l2: { layer: "L2", id: "l2-1", version: 4 },
        sources: [{ layer: "L1", id: "l1-1", version: 2 }],
        edgeVersion: 1,
        claimIds: ["deployment-region"],
        aggregatorVersion: "scene-extractor-v1",
      }],
    });
    expect(result.graph.nodes).toHaveLength(3);
    expect(result.graph.edges.map((edge) => edge.relation).sort()).toEqual([
      "L0_SUPPORTS_L1",
      "L1_DERIVES_L2",
    ]);
    expect(result.missingAssociations).toEqual([]);
  });

  it("reports missing current-code associations instead of fabricating them", () => {
    const result = buildTdaiMemoryGraph({
      l0: [l0],
      l1: [{ ...l1, metadata_json: "{}" }],
      l2: [{ ...l2, version: 0 }],
    });
    expect(result.graph.edges).toEqual([]);
    expect(result.missingAssociations).toEqual([
      "L0_L1_SOURCE",
      "L1_L2_DERIVATION",
      "L2_VERSION",
    ]);
    expect(result.warnings).toContain("missing_l0_l1_source:l1-1");
    expect(result.warnings).toContain("missing_l1_l2_derivation:l2-1@0");
  });

  it("distinguishes retrieved from actually exposed L1 and records L2 file use", () => {
    const exposures = buildLayerExposures({
      l1: [{
        recordId: "l1-1",
        logicalId: null,
        version: 2,
        contentHash: "content",
        renderedHash: "rendered",
        observedAt: "2026-09-01T00:01:00.000Z",
        rank: 1,
        score: 0.9,
        injected: false,
        truncated: true,
        sourceIds: ["msg-1"],
        metadataHash: "metadata",
      }],
      l2: [{
        exposureId: "l2-read-1",
        l2Id: "l2-1",
        l2Version: 4,
        channel: "l2_file_read",
        used: true,
        renderedHash: "l2-rendered",
        truncated: false,
        derivationEdges: [{ edgeId: "edge-1", edgeVersion: 1 }],
      }],
    });
    expect(exposures[0]).toMatchObject({ state: "retrieved", renderedHash: null });
    expect(exposures[1]).toMatchObject({ state: "used", channel: "l2_file_read" });
  });
});
