/** Benchmark-only bridge from MCP calls to the real MemoryCore SQLite L1 path. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import { join } from "node:path";

import { writeMemory } from "../../src/core/record/l1-writer.js";
import { VectorStore } from "../../src/core/store/sqlite.js";
import { executeMemorySearch } from "../../src/core/tools/memory-search.js";

const USER_ID = "trigger-bench-user";
const AGENT_ID = "trigger-bench-codex";
const SESSION_ID = "isolated-turn";

type Operation = "seed" | "search" | "write" | "dump";

function recordId(prefix: string, value: string, index = 0): string {
  return `${prefix}-${index}-${createHash("sha256").update(value).digest("hex").slice(0, 16)}`;
}

async function readStdin(): Promise<Record<string, unknown>> {
  let text = "";
  for await (const chunk of process.stdin) text += chunk;
  return text.trim() ? JSON.parse(text) : {};
}

async function storeRecord(
  store: VectorStore,
  baseDir: string,
  content: string,
  id: string,
  sourceId: string,
) {
  return writeMemory({
    baseDir,
    sessionKey: SESSION_ID,
    sessionId: SESSION_ID,
    userId: USER_ID,
    agentId: AGENT_ID,
    vectorStore: store,
    memory: {
      content,
      type: "instruction",
      priority: 80,
      scene_name: "trigger-bench",
      source_message_ids: [sourceId],
      metadata: {},
    },
    decision: { record_id: id, action: "store", target_ids: [] },
  });
}

const [operationRaw, baseDir] = process.argv.slice(2);
const operation = operationRaw as Operation;
assert(["seed", "search", "write", "dump"].includes(operation),
  "usage: tsx trigger_memory_bridge.ts seed|search|write|dump STORE_DIRECTORY");
assert(baseDir, "missing store directory");
await mkdir(baseDir, { recursive: true });

const store = new VectorStore(join(baseDir, "memory.sqlite"), 0);
await store.init();
try {
  if (operation === "seed") {
    const input = await readStdin();
    const memories = input.memories;
    assert(Array.isArray(memories), "seed memories must be an array");
    assert(await store.countL1({ userId: USER_ID }) === 0, "seed target is not empty");
    const stored = [];
    for (const [index, item] of memories.entries()) {
      assert(item && typeof item === "object", "invalid seed memory");
      const name = String((item as Record<string, unknown>).name ?? `memory-${index + 1}`);
      const content = String((item as Record<string, unknown>).content ?? "").trim();
      assert(content, "empty seed content");
      const record = await storeRecord(
        store,
        baseDir,
        `${name}: ${content}`,
        recordId("seed", `${name}\n${content}`, index),
        `seed-${index + 1}`,
      );
      assert(record, "seed write failed");
      stored.push({ id: record.id, content: record.content });
    }
    console.log(JSON.stringify({ ok: true, stored }));
  } else if (operation === "search") {
    const input = await readStdin();
    const query = String(input.query ?? "").trim();
    assert(query && query.length <= 1000, "query must contain 1..1000 characters");
    const limit = Math.max(1, Math.min(20, Number(input.limit ?? 10) || 10));
    const result = query === "*"
      ? {
          results: (await store.queryL1Records({ userId: USER_ID })).slice(0, limit).map((row) => ({
            id: row.record_id,
            content: row.content,
            type: row.type,
            priority: row.priority,
            scene_name: row.scene_name,
            score: 1,
            version: row.version,
            created_at: row.created_time,
            updated_at: row.updated_time,
          })),
          total: await store.countL1({ userId: USER_ID }),
          strategy: "list-all",
        }
      : await executeMemorySearch({
          query,
          limit,
          filter: { userId: USER_ID },
          vectorStore: store,
        });
    console.log(JSON.stringify({ ok: true, ...result }));
  } else if (operation === "write") {
    const input = await readStdin();
    const content = String(input.content ?? "").trim();
    const name = String(input.name ?? "memory").trim().slice(0, 120) || "memory";
    assert(content && content.length <= 4000, "content must contain 1..4000 characters");
    const existing = await store.countL1({ userId: USER_ID });
    const record = await storeRecord(
      store,
      baseDir,
      `${name}: ${content}`,
      recordId("write", `${name}\n${content}`, existing),
      `tool-write-${existing + 1}`,
    );
    assert(record, "MemoryCore write returned no record");
    console.log(JSON.stringify({ ok: true, id: record.id, content: record.content }));
  } else {
    const rows = await store.queryL1Records({ userId: USER_ID });
    console.log(JSON.stringify({
      ok: true,
      records: rows.map((row) => ({
        id: row.record_id,
        content: row.content,
        type: row.type,
        priority: row.priority,
        createdAt: row.created_time,
        updatedAt: row.updated_time,
      })),
    }));
  }
} finally {
  store.close();
}
