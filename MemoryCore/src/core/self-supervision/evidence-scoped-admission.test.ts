import { describe, expect, it } from "vitest";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { ConversationMessage } from "../conversation/l0-recorder.js";
import { extractL1Memories } from "../record/l1-extractor.js";
import type { ExtractedMemory } from "../record/l1-writer.js";
import { applyEvidenceScopedAdmission } from "./evidence-scoped-admission.js";

const message = (id: string, content: string, role: ConversationMessage["role"] = "user"): ConversationMessage => ({
  id, content, role, timestamp: 1,
});
const memory = (type: ExtractedMemory["type"], content: string, ids = ["u1"]): ExtractedMemory => ({
  type, content, priority: 90, source_message_ids: ids, metadata: {}, scene_name: "test",
});

describe("evidence-scoped L1 admission", () => {
  it("quarantines an instruction promoted from an explicitly session-bounded source", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "For this session, approve A only. Return BATCH|approved|blocked.")],
      candidates: [
        memory("episodic", "The user approved A for this session."),
        memory("instruction", "The user requires this format for all future requests."),
      ],
    });
    expect(result.admitted).toHaveLength(1);
    expect(result.admitted[0].type).toBe("episodic");
    expect(result.decisions[1]).toMatchObject({
      validity: "refuted", disposition: "quarantine",
      reasonCodes: expect.arrayContaining(["source_explicitly_bounded"]),
    });
  });

  it("retains a long-term instruction only when the cited user source says so", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "Going forward, always answer release checks as a three-column table.")],
      candidates: [memory("instruction", "Always use a three-column table for release checks.")],
    });
    expect(result.admitted).toHaveLength(1);
    expect(result.decisions[0]).toMatchObject({ validity: "supported", disposition: "retain" });
  });

  it("keeps ambiguous instructions reviewable but out of active memory", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "Please answer as JSON.")],
      candidates: [memory("instruction", "The user wants JSON answers.")],
    });
    expect(result.admitted).toHaveLength(0);
    expect(result.decisions[0]).toMatchObject({
      validity: "unknown", disposition: "quarantine",
      reasonCodes: expect.arrayContaining(["durable_scope_not_established"]),
    });
  });

  it("does not let assistant text establish user authority", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("a1", "The user wants this forever.", "assistant")],
      candidates: [memory("instruction", "Always use this format.", ["a1"])],
    });
    expect(result.decisions[0]).toMatchObject({ validity: "unknown", disposition: "quarantine" });
    expect(result.decisions[0].reasonCodes).toContain("missing_cited_user_source");
  });

  it("records language mismatch without dropping a useful event", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "For this task only, approve integration A.")],
      candidates: [memory("episodic", "用户批准了集成 A。")],
    });
    expect(result.admitted).toHaveLength(1);
    expect(result.decisions[0].reasonCodes).toContain("candidate_language_mismatch");
  });

  it("projects an English source fact when a translated episodic candidate includes a one-ticket reply format", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "Vendor Boreal review: production is blocked pending SOC 2. A staging-only pilot is allowed through 2027-03-31. For this ticket only, reply as REVIEW|vendor|decision|expiry.")],
      candidates: [memory("episodic", "用户决定仅允许预发布试点，有效期至 2027-03-31，且要求 AI 以 REVIEW|vendor|decision|expiry 格式回复。")],
    });
    expect(result.admitted).toHaveLength(1);
    expect(result.admitted[0].content).toBe("Vendor Boreal review: production is blocked pending SOC 2. A staging-only pilot is allowed through 2027-03-31.");
    expect(result.decisions[0]).toMatchObject({ validity: "supported", disposition: "retain" });
    expect(result.decisions[0].reasonCodes).toEqual(expect.arrayContaining([
      "bounded_response_protocol_removed", "projected_from_cited_user_source", "candidate_language_mismatch",
    ]));
  });

  it("projects Chinese fact sentences without keeping a task-only output template", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "极光发布的维护窗口是 9 月 9 日 02:00 到 03:00。变更冻结到 03:30。仅限本次工单，请按 WINDOW|service|start|end 回复。")],
      candidates: [memory("episodic", "极光维护窗口为 9 月 9 日 02:00 到 03:00，冻结至 03:30；用户要求按 WINDOW|service|start|end 回复。")],
    });
    expect(result.admitted[0].content).toBe("极光发布的维护窗口是 9 月 9 日 02:00 到 03:00。 变更冻结到 03:30。");
    expect(result.admitted[0].content).not.toContain("WINDOW|");
  });

  it("quarantines a mixed candidate when fact and temporary protocol cannot be safely separated", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "For this task only, approve integration A and reply as BATCH|approved|blocked.")],
      candidates: [memory("episodic", "Integration A was approved and the user requested BATCH|approved|blocked replies.")],
    });
    expect(result.admitted).toHaveLength(0);
    expect(result.decisions[0]).toMatchObject({
      validity: "unknown", disposition: "quarantine",
      reasonCodes: expect.arrayContaining(["mixed_fact_behavior_unresolved"]),
    });
  });

  it("does not mistake a factual API format change for an agent response directive", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "Today's API response format changed to JSON for this release.")],
      candidates: [memory("episodic", "Today's API response format changed to JSON for this release.")],
    });
    expect(result.admitted[0].content).toBe("Today's API response format changed to JSON for this release.");
    expect(result.decisions[0].reasonCodes).toContain("non_instruction_not_changed");
  });

  it("leaves a clean temporary event alone when it contains no reply directive", () => {
    const result = applyEvidenceScopedAdmission({
      messages: [message("u1", "For this task only, approve integration A. Reply as BATCH|approved|blocked.")],
      candidates: [memory("episodic", "Integration A was approved for this task.")],
    });
    expect(result.admitted[0].content).toBe("Integration A was approved for this task.");
    expect(result.decisions[0].reasonCodes).toContain("non_instruction_not_changed");
  });

  it("handles quoted authority, negation, and a later user scope revision", () => {
    const quoted = applyEvidenceScopedAdmission({
      messages: [message("u1", "Alice said, ‘always use CSV for her exports.’")],
      candidates: [memory("instruction", "Always use CSV for the user's exports.")],
    }).decisions[0];
    expect(quoted).toMatchObject({ validity: "unknown", disposition: "quarantine" });

    const negated = applyEvidenceScopedAdmission({
      messages: [message("u1", "I used to always request XML, but that is no longer my preference.")],
      candidates: [memory("instruction", "Always use XML.")],
    }).decisions[0];
    expect(negated).toMatchObject({ validity: "refuted", disposition: "quarantine" });

    const revised = applyEvidenceScopedAdmission({
      messages: [message("u1", "Use CSV for this task."), message("u2", "Actually, make CSV the permanent standard.")],
      candidates: [memory("instruction", "Use CSV as the standard.", ["u1", "u2"])],
    }).decisions[0];
    expect(revised).toMatchObject({ validity: "supported", disposition: "retain" });
  });

  it("quarantines a language-mismatched instruction while preserving its scope judgment", () => {
    const decision = applyEvidenceScopedAdmission({
      messages: [message("u1", "Going forward, always use ISO dates.")],
      candidates: [memory("instruction", "以后始终使用 ISO 日期。")],
    }).decisions[0];
    expect(decision).toMatchObject({ validity: "supported", disposition: "quarantine" });
    expect(decision.reasonCodes).toContain("candidate_language_mismatch");
  });

  it("is callable from the L1 pipeline before persistence", async () => {
    const baseDir = await mkdtemp(join(tmpdir(), "tdai-admission-"));
    try {
      const result = await extractL1Memories({
        messages: [message("u1", "For this session only, approve integration A and return BATCH|approved|blocked.")],
        sessionKey: "s1",
        sessionId: "s1",
        baseDir,
        config: {},
        options: {
          enableDedup: false,
          admissionPolicy: "evidence_scoped_v1",
          llmRunner: { run: async () => JSON.stringify([{
            scene_name: "release approval",
            message_ids: ["u1"],
            memories: [
              { content: "Integration A was approved for this session.", type: "episodic", priority: 90, source_message_ids: ["u1"], metadata: {} },
              { content: "Always use BATCH format for future requests.", type: "instruction", priority: 90, source_message_ids: ["u1"], metadata: {} },
            ],
          }]) },
        },
      });
      expect(result).toMatchObject({ extractedCount: 2, admittedCount: 1, quarantinedCount: 1, storedCount: 1 });
      const shard = (await readFile(join(baseDir, "records", new Date().toLocaleDateString("en-CA") + ".jsonl"), "utf8")).trim();
      expect(shard).toContain("approved for this session");
      expect(shard).not.toContain("Always use BATCH");
    } finally {
      await rm(baseDir, { recursive: true, force: true });
    }
  });
});
