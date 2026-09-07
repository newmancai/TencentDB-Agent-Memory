import { describe, expect, it } from "vitest";
import { applyTieredDeterministicAdmission } from "./tiered-memory-admission.js";
import type { FinalMemoryDraft } from "./final-draft-admission.js";

function draft(content: string, type: FinalMemoryDraft["type"] = "instruction"): FinalMemoryDraft {
  return { candidateIndex: 0, recordId: "r1", action: "store", targetIds: [], content, type,
    priority: 80, sceneName: "test", sourceMessageIds: ["m1"], metadata: {} };
}

describe("tiered deterministic admission", () => {
  it("activates only an explicitly durable, grounded user rule", () => {
    const [decision] = applyTieredDeterministicAdmission({
      drafts: [draft("Always use ISO dates for invoices.")],
      evidenceWindow: [{ id: "m1", role: "user", content: "Going forward, always use ISO dates for invoices." }],
    });
    expect(decision).toMatchObject({ storageDisposition: "retain", activation: "active_behavior_rule",
      validity: "supported", semanticEscalation: false });
  });

  it("does not turn a task-only instruction into an active rule", () => {
    const [decision] = applyTieredDeterministicAdmission({
      drafts: [draft("Always use ISO dates for invoices.")],
      evidenceWindow: [{ id: "m1", role: "user", content: "For this task only, use ISO dates for invoices." }],
    });
    expect(decision).toMatchObject({ storageDisposition: "quarantine", activation: "inactive",
      validity: "refuted", semanticEscalation: false });
  });

  it("retains an exact event as retrievable evidence without activating it", () => {
    const [decision] = applyTieredDeterministicAdmission({
      drafts: [draft("Deployment 42 completed at 14:00.", "episodic")],
      evidenceWindow: [{ id: "m1", role: "user", content: "Deployment 42 completed at 14:00." }],
    });
    expect(decision).toMatchObject({ storageDisposition: "retain", activation: "retrievable_fact",
      validity: "supported", semanticEscalation: false });
  });

  it("quarantines an unsupported event claim", () => {
    const [decision] = applyTieredDeterministicAdmission({
      drafts: [draft("Deployment 42 failed at 14:00.", "episodic")],
      evidenceWindow: [{ id: "m1", role: "user", content: "Deployment 42 completed at 14:00." }],
    });
    expect(decision).toMatchObject({ storageDisposition: "quarantine", activation: "inactive", validity: "refuted" });
  });

  it("lets a later task-only correction override an earlier durable rule", () => {
    const [decision] = applyTieredDeterministicAdmission({
      drafts: [draft("Always use JSON for audits.")],
      evidenceWindow: [
        { id: "m1", role: "user", content: "Always use JSON for audits." },
        { id: "m2", role: "user", content: "Correction: use it only for this audit." },
      ],
    });
    expect(decision).toMatchObject({ storageDisposition: "quarantine", validity: "refuted", semanticEscalation: false });
  });

  it("does not activate a third-party recommendation that the user has not adopted", () => {
    const [decision] = applyTieredDeterministicAdmission({
      drafts: [draft("Always use CSV.")],
      evidenceWindow: [{ id: "m1", role: "user", content: "Bob recommends that we always use CSV, but I have not decided." }],
    });
    expect(decision).toMatchObject({ storageDisposition: "quarantine", activation: "inactive",
      validity: "unknown", semanticEscalation: true });
  });
});
