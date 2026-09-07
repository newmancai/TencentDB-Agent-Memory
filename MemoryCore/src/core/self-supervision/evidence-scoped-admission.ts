import type { ConversationMessage } from "../conversation/l0-recorder.js";
import type { ExtractedMemory } from "../record/l1-writer.js";

export type AdmissionValidity = "supported" | "refuted" | "unknown";
export type AdmissionDisposition = "retain" | "quarantine";

export interface MemoryAdmissionDecision {
  candidateIndex: number;
  validity: AdmissionValidity;
  disposition: AdmissionDisposition;
  reasonCodes: string[];
  sourceMessageIds: string[];
  sourceLanguage: "zh" | "en" | "mixed_or_unknown";
  candidateLanguage: "zh" | "en" | "mixed_or_unknown";
  before: ExtractedMemory;
  after: ExtractedMemory | null;
}

export interface EvidenceScopedAdmissionResult {
  admitted: ExtractedMemory[];
  decisions: MemoryAdmissionDecision[];
}

const DURABLE_SCOPE = [
  /(?:以后|今后|从现在开始|每次|一律|始终|长期|所有未来|默认规则|作为默认|永久标准)/iu,
  /\b(?:from now on|going forward|in the future|every time|always|as a default|by default|for all future|every subsequent|standing rule|permanent standard|make .{0,24} standard|whenever .{0,48}(?:requested|ask))\b/iu,
];

const TEMPORARY_SCOPE = [
  /(?:本次|这次|此次|本轮|当前任务|当前会话|仅限|临时|一次性|今天|这个工单)/iu,
  /\b(?:this time|for this task|for (?:this|the) .{0,32} only|current task|this session|session[- ]bounded|one[- ]off|temporary|only for|today(?:'s)?|until .{0,32} ends|for the next response|during .{0,32} only)\b/iu,
];

const REFUTED_DURABILITY = [
  /(?:不要.{0,20}(?:长期|永久|偏好)|不再|过去.*(?:总是|一直)|绝不要存)/iu,
  /\b(?:do not make .{0,24}(?:permanent|standing)|no longer|used to always|never store .{0,24}(?:preference|rule))\b/iu,
];

const REPORTED_NOT_ADOPTED = [
  /(?:文档|说明).{0,24}(?:说|写).{0,48}(?:尚未|没有|未).{0,16}(?:采纳|采用)/iu,
  /\b(?:[A-Z][a-z]+ said|documentation says).{0,96}(?:not adopted|have not adopted)?/iu,
];

const DURABLE_EXTENSION = [
  /(?:不是|不再).{0,12}(?:只限|仅限|本次).{0,24}(?:以后|今后|长期)/iu,
  /\b(?:not just this time|not limited to .{0,20}|this task and every future task)\b/iu,
];

const RESPONSE_DIRECTIVE = [
  /(?:请|要求|务必|必须|需要|须).{0,48}(?:回复|回答|输出|返回)/iu,
  /(?:按|以).{1,96}(?:回复|回答|输出|返回)/iu,
  /\b(?:please\s+)?(?:reply|respond|return|output|answer)\s+(?:as|with|in|using)\b/iu,
  /\b(?:ask(?:ed)?|request(?:ed|s)?|require[ds]?|instruct(?:ed)?|must|should)\b.{0,96}\b(?:repl(?:y|ies)|respond|response|return|output|answer)\b/iu,
];

function splitSentences(text: string): string[] {
  const sentences: string[] = [];
  let start = 0;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const decimalPoint = char === "." && /\d/u.test(text[index - 1] ?? "") && /\d/u.test(text[index + 1] ?? "");
    if (char !== "\n" && !"。！？!?".includes(char) && (char !== "." || decimalPoint)) continue;
    const end = char === "\n" ? index : index + 1;
    const sentence = text.slice(start, end).trim();
    if (sentence) sentences.push(sentence);
    start = index + 1;
  }
  const tail = text.slice(start).trim();
  if (tail) sentences.push(tail);
  return sentences;
}

function hasResponseDirective(text: string): boolean {
  return matchesAny(text, RESPONSE_DIRECTIVE);
}

function isBoundedResponseDirective(text: string): boolean {
  return matchesAny(text, TEMPORARY_SCOPE) && hasResponseDirective(text);
}

function projectFactsFromBoundedProtocolSources(messages: readonly ConversationMessage[]): {
  foundBoundedProtocol: boolean;
  content: string | null;
} {
  let foundBoundedProtocol = false;
  const facts: string[] = [];

  for (const message of messages) {
    const sentences = splitSentences(message.content);
    if (!sentences.some(isBoundedResponseDirective)) continue;
    foundBoundedProtocol = true;
    facts.push(...sentences.filter((sentence) => !isBoundedResponseDirective(sentence)));
  }

  return {
    foundBoundedProtocol,
    content: facts.length > 0 ? facts.join(" ") : null,
  };
}

function languageOf(text: string): MemoryAdmissionDecision["sourceLanguage"] {
  const chinese = (text.match(/[\u3400-\u9fff]/gu) ?? []).length;
  const latin = (text.match(/[A-Za-z]/gu) ?? []).length;
  if (chinese >= 2 && chinese >= latin / 2) return "zh";
  if (latin >= 4 && latin > chinese * 2) return "en";
  return "mixed_or_unknown";
}

function matchesAny(text: string, patterns: readonly RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(text));
}

function classifyUserScope(text: string): AdmissionValidity {
  if (matchesAny(text, REFUTED_DURABILITY)) return "refuted";
  if (matchesAny(text, REPORTED_NOT_ADOPTED)) return "unknown";
  if (matchesAny(text, DURABLE_EXTENSION)) return "supported";
  const temporary = matchesAny(text, TEMPORARY_SCOPE);
  const durable = matchesAny(text, DURABLE_SCOPE);
  if (temporary) return "refuted";
  if (durable) return "supported";
  return "unknown";
}

/**
 * Opt-in, evidence-scoped admission for extracted L1 candidates.
 *
 * The first policy is deliberately narrow: an LLM-produced long-term
 * instruction is active only when its cited user source explicitly establishes
 * durable scope. A bounded/one-off source refutes that promotion; missing or
 * ambiguous source keeps the candidate reviewable but quarantined. A
 * non-instruction candidate that mixes a bounded reply protocol into a fact
 * is projected back to the cited source's standalone fact sentences. If a safe
 * sentence boundary is unavailable, it stays out of active memory for review.
 */
export function applyEvidenceScopedAdmission(input: {
  candidates: readonly ExtractedMemory[];
  messages: readonly ConversationMessage[];
}): EvidenceScopedAdmissionResult {
  const byId = new Map(input.messages.map((message) => [message.id, message]));
  const admitted: ExtractedMemory[] = [];
  const decisions: MemoryAdmissionDecision[] = [];

  input.candidates.forEach((candidate, candidateIndex) => {
    const cited = candidate.source_message_ids
      .map((id) => byId.get(id))
      .filter((message): message is ConversationMessage => message !== undefined);
    const userSources = cited.filter((message) => message.role === "user");
    const sourceText = userSources.map((message) => message.content).join("\n");
    const sourceLanguage = languageOf(sourceText);
    const candidateLanguage = languageOf(candidate.content);
    const languageMismatch = sourceLanguage !== "mixed_or_unknown"
      && candidateLanguage !== "mixed_or_unknown"
      && sourceLanguage !== candidateLanguage;
    const reasonCodes: string[] = [];
    let validity: AdmissionValidity = "unknown";
    let disposition: AdmissionDisposition = "retain";
    let projectedContent: string | null = null;

    if (candidate.type !== "instruction") {
      const projection = hasResponseDirective(candidate.content)
        ? projectFactsFromBoundedProtocolSources(userSources)
        : { foundBoundedProtocol: false, content: null };
      if (projection.foundBoundedProtocol && projection.content !== null) {
        validity = "supported";
        projectedContent = projection.content;
        reasonCodes.push("bounded_response_protocol_removed", "projected_from_cited_user_source");
      } else if (projection.foundBoundedProtocol) {
        disposition = "quarantine";
        reasonCodes.push("mixed_fact_behavior_unresolved");
      } else {
        reasonCodes.push("non_instruction_not_changed");
      }
    } else if (userSources.length === 0) {
      disposition = "quarantine";
      reasonCodes.push("missing_cited_user_source");
    } else {
      // Later cited user messages may explicitly revise an earlier scope.
      // Take the most recent non-unknown statement instead of pooling words
      // across the whole conversation.
      const scopes = userSources.map((message) => classifyUserScope(message.content));
      validity = [...scopes].reverse().find((scope) => scope !== "unknown") ?? "unknown";
      if (validity === "refuted") {
        validity = "refuted";
        disposition = "quarantine";
        reasonCodes.push("source_explicitly_bounded");
      } else if (validity === "supported") {
        reasonCodes.push("source_explicitly_durable");
      } else {
        disposition = "quarantine";
        reasonCodes.push("durable_scope_not_established");
      }
    }

    if (languageMismatch) {
      reasonCodes.push("candidate_language_mismatch");
      if (candidate.type === "instruction") disposition = "quarantine";
    }
    const after = disposition === "retain" ? structuredClone(candidate) : null;
    if (after && projectedContent !== null) after.content = projectedContent;
    if (after) admitted.push(after);
    decisions.push({
      candidateIndex,
      validity,
      disposition,
      reasonCodes,
      sourceMessageIds: userSources.map((message) => message.id),
      sourceLanguage,
      candidateLanguage,
      before: structuredClone(candidate),
      after,
    });
  });

  return { admitted, decisions };
}
