import { describe, expect, it } from "vitest";

import { executeMemorySearch } from "./memory-search.js";

const row = (record_id: string, content: string) => ({
  record_id,
  content,
  type: "episodic",
  priority: 90,
  scene_name: "test",
  score: 1,
  version: 1,
  timestamp_start: "2026-09-07T00:00:00Z",
  timestamp_end: "2026-09-07T00:00:00Z",
});

describe("executeMemorySearch exact-ID intervention", () => {
  it("keeps an excluded record out of an explicit FTS search", async () => {
    const vectorStore = {
      isFtsAvailable: () => true,
      getCapabilities: () => ({ nativeHybridSearch: false }),
      searchL1Fts: async () => [row("keep", "supported fact"), row("drop", "spurious rule")],
    } as any;

    const result = await executeMemorySearch({
      query: "fact rule",
      limit: 5,
      excludedRecordIds: ["drop"],
      vectorStore,
    });

    expect(result.results.map((item) => item.id)).toEqual(["keep"]);
    expect(result.total).toBe(1);
  });
});
