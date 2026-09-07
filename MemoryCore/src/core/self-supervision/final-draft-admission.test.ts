import { describe, expect, it, vi } from "vitest";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { ConversationMessage } from "../conversation/l0-recorder.js";
import { extractL1Memories } from "../record/l1-extractor.js";
import type { DedupDecision, ExtractedMemory } from "../record/l1-writer.js";
import {
  buildFinalMemoryDrafts,
  gateDedupDecisions,
  reviewFinalMemoryDrafts,
  type ScopeAssessmentV1,
} from "./final-draft-admission.js";

const message = (id: string, content: string, role: ConversationMessage["role"] = "user"): ConversationMessage => ({
  id, content, role, timestamp: 1,
});
const memory = (overrides: Partial<ExtractedMemory & { record_id: string }> = {}): ExtractedMemory & { record_id: string } => ({
  record_id: "new-1", content: "Always send reports to Bob.", type: "instruction", priority: 80,
  source_message_ids: ["u1"], metadata: {}, scene_name: "reports", ...overrides,
});
const assessment = (overrides: Partial<ScopeAssessmentV1> = {}): ScopeAssessmentV1 => ({
  applicability: "not_applicable", contentSupport: "supported", adoption: "unknown",
  scope: { subject: null, condition: null, horizon: "unknown", validFrom: null, validUntil: null },
  evidence: [{ messageId: "u1", excerpt: "Always use ISO dates", supports: "content" }],
  ...overrides,
});

describe("final-draft admission v1", () => {
  it("builds the exact semantic draft after dedup rewrites", () => {
    const memories = [memory({ content: "Use CSV.", type: "episodic" })];
    const decisions: DedupDecision[] = [{
      record_id: "new-1", action: "update", target_ids: ["old-1"],
      merged_content: "Always use CSV.", merged_type: "work_method", merged_priority: 99,
    }];
    expect(buildFinalMemoryDrafts({ memories, decisions })[0]).toMatchObject({
      action: "update", targetIds: ["old-1"], content: "Always use CSV.", type: "work_method", priority: 99,
    });
  });

  it("rejects a fluent but source-unsupported final claim", async () => {
    const drafts = buildFinalMemoryDrafts({ memories: [memory()], decisions: [] });
    const decisions = await reviewFinalMemoryDrafts({
      drafts, evidenceWindow: [message("u1", "Always use ISO dates for reports.")],
      strategy: "single_structured",
      reviewer: { review: async () => assessment({ contentSupport: "refuted" }) },
    });
    expect(decisions[0]).toMatchObject({ disposition: "quarantine" });
    expect(decisions[0].reasonCodes).toContain("content_refuted");
    expect(gateDedupDecisions([], decisions)[0]).toEqual({ record_id: "new-1", action: "skip", target_ids: [] });
  });

  it("routes behavior by assessed meaning, including work_method, not the type enum", async () => {
    const draft = buildFinalMemoryDrafts({ memories: [memory({
      content: "Never share reports externally.", type: "work_method",
    })], decisions: [] });
    const rule = assessment({
      applicability: "behavior_rule", adoption: "established",
      scope: { subject: "reports", condition: null, horizon: "cross_task", validFrom: null, validUntil: null },
      evidence: [
        { messageId: "u1", excerpt: "never share reports externally", supports: "content" },
        { messageId: "u1", excerpt: "Going forward", supports: "scope" },
        { messageId: "u1", excerpt: "Going forward, never", supports: "adoption" },
      ],
    });
    const [decision] = await reviewFinalMemoryDrafts({
      drafts: draft,
      evidenceWindow: [message("u1", "Going forward, never share reports externally.")],
      strategy: "independent_behavior_verifier", reviewer: { review: async () => rule },
    });
    expect(decision).toMatchObject({ disposition: "retain", reasonCodes: ["final_draft_supported"] });
  });

  it("quarantines session rules, invalid excerpts, and reviewer failures", async () => {
    const drafts = buildFinalMemoryDrafts({ memories: [memory()], decisions: [] });
    const window = [message("u1", "For this session, send reports to Bob.")];
    const bounded = await reviewFinalMemoryDrafts({
      drafts, evidenceWindow: window, strategy: "single_structured",
      reviewer: { review: async () => assessment({
        applicability: "behavior_rule", adoption: "established",
        scope: { subject: "reports", condition: null, horizon: "session", validFrom: null, validUntil: null },
        evidence: [
          { messageId: "u1", excerpt: "send reports to Bob", supports: "content" },
          { messageId: "u1", excerpt: "not in source", supports: "scope" },
          { messageId: "u1", excerpt: "For this session", supports: "adoption" },
        ],
      }) },
    });
    expect(bounded[0].disposition).toBe("quarantine");
    expect(bounded[0].reasonCodes).toEqual(expect.arrayContaining(["scope_session", "invalid_evidence_reference"]));

    const failed = await reviewFinalMemoryDrafts({
      drafts, evidenceWindow: window, strategy: "single_structured",
      reviewer: { review: async () => { throw new Error("provider down"); } },
    });
    expect(failed[0]).toMatchObject({ disposition: "quarantine", reasonCodes: ["reviewer_error"] });
  });

  it("defers update/merge before side effects and gates their dedup actions", async () => {
    const reviewer = { review: vi.fn(async () => assessment()) };
    const original: DedupDecision[] = [{ record_id: "new-1", action: "merge", target_ids: ["old-1"] }];
    const drafts = buildFinalMemoryDrafts({ memories: [memory()], decisions: original });
    const reviewed = await reviewFinalMemoryDrafts({
      drafts, evidenceWindow: [message("u1", "source")], strategy: "single_structured", reviewer,
    });
    expect(reviewer.review).not.toHaveBeenCalled();
    expect(reviewed[0]).toMatchObject({ disposition: "deferred", reasonCodes: ["complex_rewrite_deferred_v1"] });
    expect(gateDedupDecisions(original, reviewed)[0]).toEqual({ record_id: "new-1", action: "skip", target_ids: [] });
  });

  it("uses one batch review and quarantines an omitted batch result", async () => {
    const memories = [memory(), memory({ record_id: "new-2", content: "Use ISO dates." })];
    const drafts = buildFinalMemoryDrafts({ memories, decisions: [] });
    const review = vi.fn(async () => assessment());
    const reviewBatch = vi.fn(async () => [{ recordId: "new-1", assessment: assessment({
      contentSupport: "refuted",
    }) }]);
    const decisions = await reviewFinalMemoryDrafts({
      drafts, evidenceWindow: [message("u1", "Always use ISO dates")],
      strategy: "single_structured", reviewer: { review, reviewBatch },
    });
    expect(reviewBatch).toHaveBeenCalledOnce();
    expect(review).not.toHaveBeenCalled();
    expect(decisions.map((item) => item.disposition)).toEqual(["quarantine", "quarantine"]);
    expect(decisions[1].reasonCodes).toEqual(["reviewer_error"]);
  });

  it("integrates before persistence and durably queues withheld drafts", async () => {
    const baseDir = await mkdtemp(join(tmpdir(), "tdai-final-draft-"));
    try {
      const source = "For this task only, approve integration A and return JSON.";
      const result = await extractL1Memories({
        messages: [message("u1", source)], sessionKey: "s1", sessionId: "s1", baseDir, config: {},
        options: {
          enableDedup: false,
          llmRunner: { run: async () => JSON.stringify([{
            scene_name: "approval", message_ids: ["u1"], memories: [
              { content: "Integration A was approved for this task.", type: "episodic", priority: 80, source_message_ids: ["u1"], metadata: {} },
              { content: "Always return JSON.", type: "instruction", priority: 80, source_message_ids: ["u1"], metadata: {} },
            ],
          }]) },
          finalDraftAdmission: {
            strategy: "single_structured",
            reviewer: { review: async ({ draft }) => draft.type === "episodic"
              ? assessment({ evidence: [{ messageId: "u1", excerpt: "approve integration A", supports: "content" }] })
              : assessment({ contentSupport: "refuted", evidence: [{ messageId: "u1", excerpt: "For this task only", supports: "content" }] }) },
          },
        },
      });
      expect(result.storedCount).toBe(1);
      expect(result.finalDraftAdmissionDecisions?.map((item) => item.disposition)).toEqual(["retain", "quarantine"]);
      expect(result.reviewQueuePersisted).toBe(true);
      const queue = await readFile(join(baseDir, "review_queue", `${new Date().toLocaleDateString("en-CA")}.jsonl`), "utf8");
      expect(queue).toContain("Always return JSON");
      const records = await readFile(join(baseDir, "records", `${new Date().toLocaleDateString("en-CA")}.jsonl`), "utf8");
      expect(records).toContain("approved for this task");
      expect(records).not.toContain("Always return JSON");
    } finally {
      await rm(baseDir, { recursive: true, force: true });
    }
  });
});
