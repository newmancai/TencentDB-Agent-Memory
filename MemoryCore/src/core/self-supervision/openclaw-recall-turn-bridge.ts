import { randomUUID } from "node:crypto";

import type { AutoRecallShadowTap } from "../hooks/auto-recall.js";
import {
  dispatchRecallShadowObservation,
  finalizeRecallShadowObservation,
  type RecallShadowDraft,
  type RecallShadowLogger,
  type RecallShadowObservation,
  type RecallShadowObserver,
} from "./recall-shadow-adapter.js";

export interface OpenClawRecallTurnBridgeOptions {
  observer?: RecallShadowObserver;
  logger?: RecallShadowLogger;
  taskRunIdFactory?: (sessionKey: string) => string;
  clock?: () => Date;
}

export interface OpenClawRecallTurnHandle {
  taskRunId: string;
  shadowTap: AutoRecallShadowTap;
}

export interface OpenClawRecallTurnResult {
  sessionKey: string;
  sessionId: string | null;
  taskRunId: string;
  observation: RecallShadowObservation | null;
  assistantText: string | null;
}

interface PendingRecallTurn {
  sessionId: string | null;
  taskRunId: string;
  traceId: string;
  draft: RecallShadowDraft | null;
  hookReturnRecorded: boolean;
  prependContext: string | null;
  observation: RecallShadowObservation | null;
}

const IN_MEMORY_ONLY_OBSERVER: RecallShadowObserver = { append: () => undefined };

function asIso(clock: () => Date): string {
  const value = clock();
  if (!(value instanceof Date) || !Number.isFinite(value.getTime())) {
    throw new Error("OpenClaw recall turn bridge clock must return a valid Date");
  }
  return value.toISOString();
}

function containsExactUtf8Bytes(value: string, expected: string): boolean {
  if (!expected) return false;
  return Buffer.from(value, "utf8").includes(Buffer.from(expected, "utf8"));
}

function assistantText(message: unknown): string | null {
  if (!message || typeof message !== "object") return null;
  const outer = message as Record<string, unknown>;
  const nested = outer.type === "message" && outer.message && typeof outer.message === "object"
    ? outer.message as Record<string, unknown>
    : outer;
  if (nested.role !== "assistant") return null;

  const content = nested.content;
  if (typeof content === "string") return content.trim() || null;
  if (!Array.isArray(content)) return null;

  const parts = content.flatMap((part) => {
    if (!part || typeof part !== "object") return [];
    const row = part as Record<string, unknown>;
    return (row.type === "text" || row.type === "output_text") && typeof row.text === "string"
      ? [row.text]
      : [];
  });
  const joined = parts.join("\n").trim();
  return joined || null;
}

function lastAssistantText(messages: readonly unknown[]): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const text = assistantText(messages[index]);
    if (text !== null) return text;
  }
  return null;
}

/**
 * Narrow in-memory bridge between one OpenClaw turn and the existing recall
 * shadow adapter. It owns no production Memory read or write capability.
 */
export class OpenClawRecallTurnBridge {
  private readonly turns = new Map<string, PendingRecallTurn>();
  private readonly observer: RecallShadowObserver;
  private readonly logger?: RecallShadowLogger;
  private readonly taskRunIdFactory: (sessionKey: string) => string;
  private readonly clock: () => Date;

  constructor(options: OpenClawRecallTurnBridgeOptions = {}) {
    this.observer = options.observer ?? IN_MEMORY_ONLY_OBSERVER;
    this.logger = options.logger;
    this.taskRunIdFactory = options.taskRunIdFactory
      ?? (() => `openclaw-recall-turn-${randomUUID()}`);
    this.clock = options.clock ?? (() => new Date());
  }

  beginTurn(input: { sessionKey: string; sessionId?: string | null }): OpenClawRecallTurnHandle {
    const sessionKey = input.sessionKey.trim();
    if (!sessionKey) throw new Error("OpenClaw recall turn bridge requires sessionKey");
    const taskRunId = this.taskRunIdFactory(sessionKey).trim();
    if (!taskRunId) throw new Error("OpenClaw recall turn bridge requires a non-empty taskRunId");
    const traceId = `${taskRunId}:recall`;
    const capturedAt = asIso(this.clock);
    const state: PendingRecallTurn = {
      sessionId: input.sessionId?.trim() || null,
      taskRunId,
      traceId,
      draft: null,
      hookReturnRecorded: false,
      prependContext: null,
      observation: null,
    };
    this.turns.set(sessionKey, state);

    return {
      taskRunId,
      shadowTap: {
        traceId,
        capturedAt,
        sessionId: state.sessionId,
        taskRunId,
        onDraft: (draft) => this.acceptDraft(sessionKey, taskRunId, draft),
      },
    };
  }

  recordHookReturn(input: {
    sessionKey: string;
    taskRunId: string;
    prependContext?: string;
  }): boolean {
    const state = this.turns.get(input.sessionKey);
    if (!state || state.taskRunId !== input.taskRunId || state.observation !== null) return false;
    state.hookReturnRecorded = true;
    state.prependContext = input.prependContext && input.prependContext.length > 0
      ? input.prependContext
      : null;
    return true;
  }

  onLlmInput(input: { sessionKey: string; prompt: unknown }): RecallShadowObservation | null {
    const state = this.turns.get(input.sessionKey);
    if (!state || state.observation !== null || !state.draft || !state.hookReturnRecorded) {
      return state?.observation ?? null;
    }

    const prompt = typeof input.prompt === "string" ? input.prompt : undefined;
    const acknowledged = prompt !== undefined
      && state.prependContext !== null
      && containsExactUtf8Bytes(prompt, state.prependContext);
    const actualContext = acknowledged
      ? state.prependContext ?? undefined
      : prompt;
    const observation = finalizeRecallShadowObservation(
      state.draft,
      asIso(this.clock),
      actualContext,
    );
    state.observation = observation;
    dispatchRecallShadowObservation(this.observer, observation, this.logger);
    return observation;
  }

  endTurn(input: {
    sessionKey: string;
    messages?: readonly unknown[];
  }): OpenClawRecallTurnResult | null {
    const state = this.turns.get(input.sessionKey);
    if (!state) return null;
    const result: OpenClawRecallTurnResult = Object.freeze({
      sessionKey: input.sessionKey,
      sessionId: state.sessionId,
      taskRunId: state.taskRunId,
      observation: state.observation,
      assistantText: lastAssistantText(input.messages ?? []),
    });
    this.turns.delete(input.sessionKey);
    return result;
  }

  private acceptDraft(sessionKey: string, taskRunId: string, draft: RecallShadowDraft): void {
    const state = this.turns.get(sessionKey);
    if (!state || state.taskRunId !== taskRunId || state.observation !== null) return;
    if (
      draft.sessionKey !== sessionKey
      || draft.taskRunId !== taskRunId
      || draft.traceId !== state.traceId
    ) {
      this.logger?.warn?.("[memory-tdai] [shadow-recall] ignored draft with mismatched turn identity");
      return;
    }
    state.draft = draft;
  }
}
