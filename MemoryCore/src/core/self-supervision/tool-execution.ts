/** Host tool observations. API contracts describe observable fields, never task answers. */
import { createHash } from "node:crypto";
import type { ValidatorObservation } from "./types.js";

type ObjectValue = Record<string, unknown>;
const object = (x: unknown): x is ObjectValue => !!x && typeof x === "object" && !Array.isArray(x);
const hash = (x: unknown) => createHash("sha256").update(JSON.stringify(x)).digest("hex");

export interface ToolResultContract {
  id: string;
  /** A returned record whose fields can corroborate requested changes. */
  recordPath?: string[];
  identityField?: string;
  changedFields?: string[];
  success?: { field: string; value: unknown };
  errorField?: string;
}

export interface ToolExecutionObservation {
  id: string;
  sessionId: string;
  /** Null on legacy callers; task-level feedback must require an exact binding. */
  taskRunId: string | null;
  callId: string;
  tool: string;
  arguments: unknown;
  result: unknown;
  resultMessageIndex: number | null;
  validator: ValidatorObservation;
  fieldChecks: Array<{ field: string; requested: unknown; observed: unknown;
    validity: "supported" | "refuted" | "unverifiable" }>;
  /** No tool contract proves that the whole user task succeeded. */
  taskStatus: "unknown";
}

export interface ToolExecutionContext {
  sessionId: string;
  taskRunId: string;
}

function decode(x: unknown): unknown {
  if (typeof x !== "string") return x ?? null;
  try { return JSON.parse(x); } catch { return x; }
}

export function observeToolExecutions(messages: unknown[], context: string | ToolExecutionContext,
  contracts: Record<string, ToolResultContract> = {}): ToolExecutionObservation[] {
  const sessionId = typeof context === "string" ? context : context.sessionId;
  const taskRunId = typeof context === "string" ? null : context.taskRunId;
  const calls = new Map<string, Array<{ index: number; tool: string; args: unknown }>>();
  const results = new Map<string, Array<{ index: number; result: unknown }>>();
  messages.forEach((m, index) => {
    if (!object(m)) return;
    if (m.role === "assistant" && Array.isArray(m.tool_calls)) {
      for (const c of m.tool_calls) {
        if (!object(c) || typeof c.id !== "string" || !object(c.function)
          || typeof c.function.name !== "string") continue;
        const entries = calls.get(c.id) ?? [];
        entries.push({ index, tool: c.function.name, args: decode(c.function.arguments) });
        calls.set(c.id, entries);
      }
    }
    if (m.role === "tool" && typeof m.tool_call_id === "string") {
      const entries = results.get(m.tool_call_id) ?? [];
      entries.push({ index, result: decode(m.content) });
      results.set(m.tool_call_id, entries);
    }
  });
  return [...calls].map(([callId, entries]) => {
    const call = entries[0];
    const replies = results.get(callId) ?? [];
    const linked = entries.length === 1 && replies.length === 1 && replies[0].index > call.index;
    const result = linked ? replies[0].result : null;
    const contract = contracts[call.tool];
    let status: ValidatorObservation["status"] = "unverifiable";
    if (linked && object(result) && contract) {
      const err = contract.errorField ? result[contract.errorField] : undefined;
      if (err !== undefined && err !== null && err !== false && err !== "") status = "fail";
      else if (contract.success && result[contract.success.field] === contract.success.value) status = "pass";
    }
    let record: unknown = result;
    for (const key of contract?.recordPath ?? []) record = object(record) ? record[key] : undefined;
    const identity = contract?.identityField;
    const identityMatches = linked && object(record) && object(call.args) && !!identity
      && call.args[identity] !== undefined && record[identity] === call.args[identity];
    const fieldChecks: ToolExecutionObservation["fieldChecks"] = [];
    if (object(call.args)) {
      for (const field of contract?.changedFields ?? []) {
        if (!(field in call.args)) continue;
        const observed = object(record) && field in record ? record[field] : null;
        const checkable = status === "pass" && identityMatches && object(record) && field in record;
        fieldChecks.push({ field, requested: call.args[field], observed,
          validity: !checkable ? "unverifiable" : JSON.stringify(observed) === JSON.stringify(call.args[field])
            ? "supported" : "refuted" });
      }
    }
    const evidenceHash = hash({ sessionId, taskRunId, callId, entries, replies });
    return { id: `tool_${hash([sessionId, taskRunId, callId]).slice(0, 24)}`, sessionId, taskRunId, callId,
      tool: call.tool, arguments: call.args, result, resultMessageIndex: linked ? replies[0].index : null,
      validator: { validatorId: contract?.id ?? "uninterpreted_tool_result", validatorVersion: "1",
        oracleKind: "schema", status, score: null, evidenceHash }, fieldChecks, taskStatus: "unknown" };
  });
}

/** Explicit opt-in capture: raw host tool messages are not automatically ingested. */
export function executionCaptureMessages(observations: ToolExecutionObservation[], start: number) {
  return observations.map((o, index) => ({ id: o.id, role: "tool" as const,
    tdaiExecutionEvidence: true, timestamp: start + index,
    content: JSON.stringify({ source: "tool_execution", ...o }) }));
}
