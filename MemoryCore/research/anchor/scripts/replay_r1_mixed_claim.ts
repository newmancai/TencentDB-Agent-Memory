#!/usr/bin/env -S node --import tsx
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { ConversationMessage } from "../../../src/core/conversation/l0-recorder.js";
import type { ExtractedMemory } from "../../../src/core/record/l1-writer.js";
import { applyEvidenceScopedAdmission } from "../../../src/core/self-supervision/evidence-scoped-admission.js";

const eventsPath = resolve(process.argv[2]);
const sourcesPath = resolve(process.argv[3]);
const outputPath = resolve(process.argv[4]);
const marker = "REVIEW|vendor|decision|expiry";

const events = (await readFile(eventsPath, "utf8"))
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line)) as Array<Record<string, any>>;
const flush = events.find((row) => row.op === "flush");
if (!flush) throw new Error("flush event not found");
const oldDecisions = flush.data.batches[0].admissionDecisions as Array<Record<string, any>>;
const candidates = oldDecisions.map((decision) => decision.before) as ExtractedMemory[];
const sourceArtifact = JSON.parse(await readFile(sourcesPath, "utf8")) as {
  messages: Array<{ role: ConversationMessage["role"]; content: string; timestamp: number }>;
};
const sourceId = candidates[0].source_message_ids[0];
const userSource = sourceArtifact.messages.find((message) => message.role === "user");
if (!userSource) throw new Error("user source not found");
const messages: ConversationMessage[] = [{ id: sourceId, ...userSource }];

const startedAt = performance.now();
const replay = applyEvidenceScopedAdmission({ candidates, messages });
const elapsedMs = performance.now() - startedAt;
const oldActive = oldDecisions.flatMap((decision) => decision.after ? [decision.after as ExtractedMemory] : []);
const newActive = replay.admitted;
const projectedFact = newActive.find((memory) => memory.type === "episodic")?.content ?? null;
const factTokens = ["production is blocked", "staging-only pilot", "2027-03-31"];

const result = {
  schemaVersion: "tdai-r1-mixed-claim-replay.v1",
  generatedAt: new Date().toISOString(),
  scope: "read-only replay of the saved r1 Qwen candidate and its cited user source",
  sourceArtifacts: { eventsPath, sourcesPath },
  metrics: {
    candidates: candidates.length,
    oldActiveRecords: oldActive.length,
    newActiveRecords: newActive.length,
    oldActiveMarkerRecords: oldActive.filter((memory) => memory.content.includes(marker)).length,
    newActiveMarkerRecords: newActive.filter((memory) => memory.content.includes(marker)).length,
    factTokensPreserved: factTokens.filter((token) => projectedFact?.toLowerCase().includes(token)).length,
    totalFactTokens: factTokens.length,
    modelCalls: 0,
    modelTokens: 0,
    elapsedMs,
  },
  oldDecisions: oldDecisions.map((decision) => ({
    candidateIndex: decision.candidateIndex,
    disposition: decision.disposition,
    reasonCodes: decision.reasonCodes,
    afterContent: decision.after?.content ?? null,
  })),
  newDecisions: replay.decisions.map((decision) => ({
    candidateIndex: decision.candidateIndex,
    validity: decision.validity,
    disposition: decision.disposition,
    reasonCodes: decision.reasonCodes,
    afterContent: decision.after?.content ?? null,
  })),
};

await writeFile(outputPath, JSON.stringify(result, null, 2) + "\n");
process.stdout.write(JSON.stringify(result, null, 2) + "\n");
