import type { ConversationMessage } from "../conversation/l0-recorder.js";
import type { FinalMemoryDraft } from "./final-draft-admission.js";

export type MemoryActivation = "active_behavior_rule" | "retrievable_fact" | "inactive";
export type TieredValidity = "supported" | "refuted" | "unknown";

export interface TieredAdmissionDecision {
  recordId: string;
  storageDisposition: "retain" | "quarantine";
  activation: MemoryActivation;
  validity: TieredValidity;
  semanticEscalation: boolean;
  reasonCodes: string[];
}

const DURABLE_SCOPE = [
  /(?:以后|今后|从现在开始|每次|一律|始终|长期|默认规则|作为默认|未来.*(?:都|每次))/iu,
  /\b(?:from now on|going forward|in the future|every time|always|by default|as (?:our|the) default|make this (?:our|the) default|standing rule|future cases?|whenever)\b/iu,
];
const TEMPORARY_SCOPE = [
  /(?:仅限|只在|本次|这次|此次|本轮|当前任务|当前会话|临时|一次性|今天)/iu,
  /\b(?:for this task only|this task only|only during|only (?:for|in) this|for this incident only|current (?:task|session|run)|this session|one[- ]off|temporary|today(?:'s)?|do not carry it forward|no longer (?:my|our|the) preference)\b/iu,
];
const NOT_ADOPTED = [
  /(?:尚未|没有|并未|未).{0,12}(?:采纳|采用|接受)/iu,
  /\b(?:not adopted|have not adopted|haven't adopted|did not adopt|not accepting|have not decided|haven't decided|do not apply (?:it )?yet)\b/iu,
];

const STOP_WORDS = new Set([
  "a", "always", "an", "and", "as", "at", "be", "by", "default", "do", "every", "for", "from", "future",
  "going", "handling", "in", "is", "it", "make", "method", "now", "on", "only", "our", "rule", "standing", "that",
  "the", "this", "to", "update", "use", "whenever", "with",
]);

function matchesAny(text: string, patterns: readonly RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(text));
}

function tokenise(text: string): Set<string> {
  const words = text.toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  return new Set(words.filter((word) => !STOP_WORDS.has(word)).map((word) => {
    if (/^[a-z]{5,}$/u.test(word) && word.endsWith("s") && !word.endsWith("ss")) return word.slice(0, -1);
    return word;
  }).filter((word) => !STOP_WORDS.has(word)));
}

function overlap(candidate: Set<string>, source: Set<string>): { covered: number; total: number; ratio: number } {
  const covered = [...candidate].filter((token) => source.has(token)).length;
  return { covered, total: candidate.size, ratio: candidate.size === 0 ? 0 : covered / candidate.size };
}

function scopeValidity(messages: readonly ConversationMessage[]): TieredValidity {
  let current: TieredValidity = "unknown";
  for (const message of messages) {
    if (matchesAny(message.content, NOT_ADOPTED)) current = "unknown";
    else if (matchesAny(message.content, TEMPORARY_SCOPE)) current = "refuted";
    else if (matchesAny(message.content, DURABLE_SCOPE)) current = "supported";
  }
  return current;
}

/**
 * Zero-LLM admission tier inspired by production agent memory systems:
 * preserve L0 separately, promote only mechanically supported claims, and
 * distinguish retrievable facts from rules allowed to influence behavior.
 * Unknown semantic cases are routed, not guessed.
 */
export function applyTieredDeterministicAdmission(input: {
  drafts: readonly FinalMemoryDraft[];
  evidenceWindow: readonly ConversationMessage[];
}): TieredAdmissionDecision[] {
  const byId = new Map(input.evidenceWindow.map((message) => [message.id, message]));
  const orderedUsers = input.evidenceWindow.filter((message) => message.role === "user");

  return input.drafts.map((draft) => {
    const reasons: string[] = [];
    const cited = draft.sourceMessageIds.map((id) => byId.get(id));
    if (cited.length === 0 || cited.some((message) => !message)) {
      return { recordId: draft.recordId, storageDisposition: "quarantine", activation: "inactive",
        validity: "unknown", semanticEscalation: true, reasonCodes: ["incomplete_source_binding"] };
    }
    const citedUsers = cited.filter((message): message is ConversationMessage => message?.role === "user");
    if (citedUsers.length === 0) {
      return { recordId: draft.recordId, storageDisposition: "quarantine", activation: "inactive",
        validity: "unknown", semanticEscalation: true, reasonCodes: ["no_user_authority"] };
    }

    const candidateTokens = tokenise(draft.content);
    const citedTokens = tokenise(citedUsers.map((message) => message.content).join("\n"));
    const fullUserTokens = tokenise(orderedUsers.map((message) => message.content).join("\n"));
    const citedCoverage = overlap(candidateTokens, citedTokens);
    const fullCoverage = overlap(candidateTokens, fullUserTokens);
    const mechanicallySupported = fullCoverage.total > 0 && fullCoverage.covered === fullCoverage.total;
    const behavior = draft.type === "instruction" || draft.type === "work_method";

    if (!mechanicallySupported) {
      reasons.push("claim_not_lexically_grounded");
      const obviousConflict = citedCoverage.ratio >= 0.5;
      return { recordId: draft.recordId, storageDisposition: "quarantine", activation: "inactive",
        validity: obviousConflict ? "refuted" : "unknown", semanticEscalation: !obviousConflict, reasonCodes: reasons };
    }
    reasons.push("claim_lexically_grounded");

    if (!behavior) {
      return { recordId: draft.recordId, storageDisposition: "retain", activation: "retrievable_fact",
        validity: "supported", semanticEscalation: false, reasonCodes: [...reasons, "fact_not_behaviorally_active"] };
    }

    const scope = scopeValidity(orderedUsers);
    if (scope === "supported") {
      return { recordId: draft.recordId, storageDisposition: "retain", activation: "active_behavior_rule",
        validity: "supported", semanticEscalation: false, reasonCodes: [...reasons, "explicit_cross_task_scope"] };
    }
    if (scope === "refuted") {
      return { recordId: draft.recordId, storageDisposition: "quarantine", activation: "inactive",
        validity: "refuted", semanticEscalation: false, reasonCodes: [...reasons, "explicit_bounded_scope"] };
    }
    return { recordId: draft.recordId, storageDisposition: "quarantine", activation: "inactive",
      validity: "unknown", semanticEscalation: true, reasonCodes: [...reasons, "scope_or_adoption_unknown"] };
  });
}
