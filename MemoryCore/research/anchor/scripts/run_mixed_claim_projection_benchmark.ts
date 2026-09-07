#!/usr/bin/env -S npx tsx
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { ConversationMessage } from "../../../src/core/conversation/l0-recorder.js";
import type { ExtractedMemory } from "../../../src/core/record/l1-writer.js";
import { applyEvidenceScopedAdmission } from "../../../src/core/self-supervision/evidence-scoped-admission.js";

type ExpectedAction = "project" | "quarantine" | "unchanged";

interface ProjectionCase {
  source: string;
  candidate: string;
  expectedAction: ExpectedAction;
  expectedContent: string | null;
}

const cases: ProjectionCase[] = [
  {
    source: "Falcon release remains blocked by CAB. A canary is approved through Friday. Only for this incident, respond with INCIDENT|service|status.",
    candidate: "Falcon is blocked by CAB, a canary is approved through Friday, and the user requested INCIDENT|service|status replies.",
    expectedAction: "project",
    expectedContent: "Falcon release remains blocked by CAB. A canary is approved through Friday.",
  },
  {
    source: "The Delta invoice total is USD 480. This session, return the answer in JSON.",
    candidate: "The invoice total is USD 480 and the assistant must return the answer in JSON.",
    expectedAction: "project",
    expectedContent: "The Delta invoice total is USD 480.",
  },
  {
    source: "The Cedar backup completed at 02:10 UTC. For today's audit only, reply using AUDIT|job|time.",
    candidate: "The Cedar backup completed at 02:10 UTC; the user asked the assistant to reply using AUDIT|job|time.",
    expectedAction: "project",
    expectedContent: "The Cedar backup completed at 02:10 UTC.",
  },
  {
    source: "Mica access expires at 18:00. During the migration only, output as ACCESS|account|expiry.",
    candidate: "Mica access expires at 18:00 and the assistant should output as ACCESS|account|expiry.",
    expectedAction: "project",
    expectedContent: "Mica access expires at 18:00.",
  },
  {
    source: "青禾数据库已完成切换。新主库位于上海三区。本轮请按 CHECK|cluster|zone 回复。",
    candidate: "青禾数据库已完成切换，新主库位于上海三区，用户要求助手按 CHECK|cluster|zone 回复。",
    expectedAction: "project",
    expectedContent: "青禾数据库已完成切换。 新主库位于上海三区。",
  },
  {
    source: "云杉服务只能部署到预发布环境。授权在 9 月 12 日到期。仅限这个工单，请以 DEPLOY|env|expiry 回复。",
    candidate: "云杉服务仅允许预发布部署，授权到 9 月 12 日；请以 DEPLOY|env|expiry 回复。",
    expectedAction: "project",
    expectedContent: "云杉服务只能部署到预发布环境。 授权在 9 月 12 日到期。",
  },
  {
    source: "Project Iris owner is Li. 仅限本次，reply as OWNER|name.",
    candidate: "Iris 项目负责人是 Li，并要求助手回复 OWNER|name。",
    expectedAction: "project",
    expectedContent: "Project Iris owner is Li.",
  },
  {
    source: "Orchid maintenance starts at 01:00. For this ticket only, answer in the template ORCHID|start.",
    candidate: "Orchid maintenance starts at 01:00 and the user asked the assistant to answer in the template ORCHID|start.",
    expectedAction: "project",
    expectedContent: "Orchid maintenance starts at 01:00.",
  },
  {
    source: "For this task, region eu-west-1 is approved; reply as REGION|name.",
    candidate: "Region eu-west-1 is approved and the user requested REGION|name replies.",
    expectedAction: "quarantine",
    expectedContent: null,
  },
  {
    source: "本次窗口为 04:00，请按 WINDOW|time 回复。",
    candidate: "窗口为 04:00，用户要求按 WINDOW|time 回复。",
    expectedAction: "quarantine",
    expectedContent: null,
  },
  {
    source: "Today's API response format changed to JSON for this release.",
    candidate: "Today's API response format changed to JSON for this release.",
    expectedAction: "unchanged",
    expectedContent: "Today's API response format changed to JSON for this release.",
  },
  {
    source: "本次工单批准集成 A。",
    candidate: "本次工单批准集成 A。",
    expectedAction: "unchanged",
    expectedContent: "本次工单批准集成 A。",
  },
  {
    source: "The phrase 'reply as JSON' appears in the migration guide.",
    candidate: "The phrase 'reply as JSON' appears in the migration guide.",
    expectedAction: "unchanged",
    expectedContent: "The phrase 'reply as JSON' appears in the migration guide.",
  },
  {
    source: "今天批处理输出格式由 CSV 改为 Parquet。",
    candidate: "今天批处理输出格式由 CSV 改为 Parquet。",
    expectedAction: "unchanged",
    expectedContent: "今天批处理输出格式由 CSV 改为 Parquet。",
  },
];

function message(index: number, content: string): ConversationMessage {
  return { id: `source-${index + 1}`, role: "user", content, timestamp: index + 1 };
}

function memory(index: number, content: string): ExtractedMemory {
  return {
    type: "episodic",
    content,
    priority: 80,
    source_message_ids: [`source-${index + 1}`],
    metadata: {},
    scene_name: "projection-benchmark",
  };
}

const startedAt = performance.now();
const rows = cases.map((item, index) => {
  const decision = applyEvidenceScopedAdmission({
    messages: [message(index, item.source)],
    candidates: [memory(index, item.candidate)],
  }).decisions[0];
  const actualAction: ExpectedAction = decision.disposition === "quarantine"
    ? "quarantine"
    : decision.reasonCodes.includes("projected_from_cited_user_source") ? "project" : "unchanged";
  const actualContent = decision.after?.content ?? null;
  return {
    caseNumber: index + 1,
    expectedAction: item.expectedAction,
    actualAction,
    actionCorrect: actualAction === item.expectedAction,
    contentCorrect: actualContent === item.expectedContent,
    source: item.source,
    candidate: item.candidate,
    actualContent,
    reasonCodes: decision.reasonCodes,
  };
});
const elapsedMs = performance.now() - startedAt;
const result = {
  schemaVersion: "tdai-mixed-claim-projection-benchmark.v1",
  generatedAt: new Date().toISOString(),
  method: "deterministic adversarial component check; fixed handcrafted cases; not a blind model evaluation",
  metrics: {
    cases: rows.length,
    newSourceTemplates: new Set(cases.map((item) => item.source)).size,
    actionCorrect: rows.filter((row) => row.actionCorrect).length,
    contentCorrect: rows.filter((row) => row.contentCorrect).length,
    projected: rows.filter((row) => row.actualAction === "project").length,
    quarantined: rows.filter((row) => row.actualAction === "quarantine").length,
    unchanged: rows.filter((row) => row.actualAction === "unchanged").length,
    boundedProtocolActiveBefore: cases.filter((item) => item.expectedAction !== "unchanged").length,
    boundedProtocolActiveAfter: rows.filter((row) => row.actualContent !== null && /(?:INCIDENT|AUDIT|ACCESS|CHECK|DEPLOY|OWNER|ORCHID|REGION|WINDOW)\|/u.test(row.actualContent)).length,
    modelCalls: 0,
    modelTokens: 0,
    elapsedMs,
  },
  rows,
};

const rendered = JSON.stringify(result, null, 2) + "\n";
if (process.argv[2]) await writeFile(resolve(process.argv[2]), rendered);
process.stdout.write(rendered);
