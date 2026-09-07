#!/usr/bin/env node
/** PAST host adapter: normal TDAI capture/L1 extraction/recall with an owned local store.
 * Existing async Gateway prefetch drops record identity and cannot await source
 * extraction. This driver only connects those existing components to a benchmark
 * episode boundary. It has no authored Memory insertion or production endpoint.
 */
import { createHash } from "node:crypto";
import { appendFile, lstat, mkdir, readFile, realpath, writeFile } from "node:fs/promises";
import { join, resolve, sep } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { StandaloneHostAdapter } from "../../../../src/adapters/standalone/host-adapter.js";
import { parseConfig } from "../../../../src/config.js";
import { TdaiCore } from "../../../../src/core/tdai-core.js";
import type { Logger, LLMRunner } from "../../../../src/core/types.js";
import { createL1Runner } from "../../../../src/utils/pipeline-factory.js";
import { CheckpointManager } from "../../../../src/utils/checkpoint.js";
import { executionCaptureMessages, observeToolExecutions } from "../../../../src/core/self-supervision/tool-execution.js";
import { finalizeRecallShadowObservation, type RecallShadowDraft } from "../../../../src/core/self-supervision/recall-shadow-adapter.js";

export const PROFILE = {
  schemaVersion: "past-tdai-l1.v0.1", model: "Qwen3-4B-Instruct-2507-bf16",
  seed: 20260905, temperature: 0, maximumOutputTokens: 2048,
  extractionTimeoutMs: 180_000, recallTopK: 5, scoreThreshold: 0,
  layers: ["L0", "L1"], extraction: "existing createL1Runner, awaited at episode boundary",
  dedup: "existing default enabled", persistenceLocation: "<hermes_home>/.tdai",
  backgroundPipeline: false, productionAccess: false,
} as const;
const digest = (text: string) => createHash("sha256").update(text).digest("hex");
const canonical = (value: unknown) => JSON.stringify(value);
const save = async (file: string, value: unknown) => writeFile(file, JSON.stringify(value, null, 2) + "\n");

async function isolatedDirectory(value: string) {
  const path = resolve(value);
  if (!path.startsWith("/tmp/")) throw new Error("experiment directories must be under /tmp");
  await mkdir(path, { recursive: true });
  if ((await realpath(path)) !== path || !(await lstat(path)).isDirectory()) {
    throw new Error("experiment directory must not resolve through a symlink");
  }
  return path;
}

export class TdaiEpisodeSidecar {
  private core?: TdaiCore;
  private cfg = parseConfig({});
  private dataDir = "";
  private traceDir = "";
  private sessionId = "";
  private taskRunId = "";
  private context = "";
  private draft?: RecallShadowDraft;
  private query = "";
  private excludedRecordIds: string[] = [];
  private acknowledged?: ReturnType<typeof finalizeRecallShadowObservation>;
  private originalFetch?: typeof fetch;
  private modelCalls = 0;
  private pendingCapture = false;
  private closed = false;
  private recallTopK = PROFILE.recallTopK;
  private admissionPolicy?: "evidence_scoped_v1";
  private finalDraftAdmissionStrategy?: "single_structured" | "independent_behavior_verifier";
  private fakeRunner?: LLMRunner;
  private logs: string[] = [];
  private logger: Logger = {
    info: message => this.log(message), warn: message => this.log(message),
    error: message => this.log(message), debug: message => this.log(message),
  };

  /** Only tests inject a deterministic extractor; CLI always uses real Qwen. */
  constructor(testRunner?: LLMRunner) { this.fakeRunner = testRunner; }
  private log(message: string) { this.logs.push(message); process.stderr.write(message + "\n"); }
  private store() {
    const store = this.core?.getVectorStore();
    if (!store || store.isDegraded()) throw new Error("isolated SQLite store is unavailable");
    return store;
  }
  private async event(op: string, data: unknown) {
    await appendFile(join(this.traceDir, "events.jsonl"), canonical({
      schemaVersion: PROFILE.schemaVersion, taskRunId: this.taskRunId,
      sessionId: this.sessionId, at: new Date().toISOString(), op, data,
    }) + "\n");
  }
  private async snapshot() {
    const records = (await this.store().queryL1Records()).sort((a, b) => a.record_id.localeCompare(b.record_id));
    return { l0Count: await this.store().countL0(), l1Count: records.length,
      records, rowsSha256: digest(canonical(records)) };
  }

  async init(input: any) {
    if (this.core || this.closed) throw new Error("sidecar initialization is single-use");
    const home = await isolatedDirectory(input.homeDir);
    this.traceDir = await isolatedDirectory(input.traceDir);
    if (this.traceDir === home || this.traceDir.startsWith(home + sep)) {
      throw new Error("trace must be outside the cloned Memory home");
    }
    this.dataDir = await isolatedDirectory(join(home, ".tdai"));
    this.sessionId = String(input.sessionId ?? "");
    this.taskRunId = String(input.taskRunId ?? "");
    if (!this.sessionId || !this.taskRunId) throw new Error("episode/session identity required");
    const baseUrl = input.model?.baseUrl ?? "http://127.0.0.1:18767/v1";
    const endpoint = new URL(baseUrl);
    if (endpoint.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(endpoint.hostname)
      || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) {
      throw new Error("only an explicit loopback model endpoint is allowed");
    }
    const model = input.model?.model ?? input.model?.modelId ?? PROFILE.model;
    if (model !== PROFILE.model) throw new Error("model differs from frozen B1 profile");
    const requestedRecallTopK = input.recallTopK ?? PROFILE.recallTopK;
    if (!Number.isSafeInteger(requestedRecallTopK) || requestedRecallTopK < 1
      || requestedRecallTopK > PROFILE.recallTopK) {
      throw new Error(`recallTopK must be an integer in [1, ${PROFILE.recallTopK}]`);
    }
    this.recallTopK = requestedRecallTopK;
    if (input.admissionPolicy !== undefined && input.admissionPolicy !== "evidence_scoped_v1") {
      throw new Error("unsupported admissionPolicy");
    }
    this.admissionPolicy = input.admissionPolicy;
    if (input.finalDraftAdmissionStrategy !== undefined
      && !["single_structured", "independent_behavior_verifier"].includes(input.finalDraftAdmissionStrategy)) {
      throw new Error("unsupported finalDraftAdmissionStrategy");
    }
    this.finalDraftAdmissionStrategy = input.finalDraftAdmissionStrategy;
    const llmConfig = { baseUrl, model, apiKey: input.model?.apiKey ?? "local-development",
      maxTokens: PROFILE.maximumOutputTokens, timeoutMs: PROFILE.extractionTimeoutMs };
    this.cfg = parseConfig({
      capture: { enabled: true }, extraction: { enabled: false, enableDedup: true },
      recall: { enabled: true, strategy: "keyword", maxResults: this.recallTopK, scoreThreshold: 0 },
      embedding: { enabled: false, provider: "none" }, bm25: { enabled: false },
      report: { enabled: false }, skill: { enabled: false },
      llm: { enabled: true, ...llmConfig },
    });
    const host = new StandaloneHostAdapter({ dataDir: this.dataDir, llmConfig,
      logger: this.logger, defaultUserId: "default_user", platform: "hermes" });
    this.core = new TdaiCore({ hostAdapter: host, config: this.cfg });
    await this.core.initialize();
    // Public readiness gate; no source is captured until an explicit capture request.
    await this.core.handleBeforeRecall("", this.sessionId);
    const before = await this.snapshot();
    this.originalFetch = globalThis.fetch;
    const original = this.originalFetch;
    globalThis.fetch = async (request, options) => {
      const url = typeof request === "string" ? request : request instanceof URL ? request.href : request.url;
      if (url !== `${baseUrl.replace(/\/$/, "")}/chat/completions` || typeof options?.body !== "string") {
        throw new Error("unexpected sidecar model transport");
      }
      const body = JSON.parse(options.body);
      body.seed = PROFILE.seed;
      body.temperature = PROFILE.temperature;
      const sequence = ++this.modelCalls;
      const start = performance.now();
      const entry: any = { sequence, request: body };
      try {
        const response = await original(request, { ...options, body: JSON.stringify(body) });
        entry.httpStatus = response.status;
        entry.response = await response.clone().json();
        return response;
      } catch (error) {
        entry.error = error instanceof Error ? error.message : String(error);
        throw error;
      } finally {
        entry.wallTimeMs = performance.now() - start;
        await appendFile(join(this.traceDir, "extraction-model.jsonl"), canonical(entry) + "\n");
      }
    };
    await save(join(this.traceDir, "initial-memory.json"), before);
    await save(join(this.traceDir, "profile.json"), {
      ...PROFILE, recallTopK: this.recallTopK, admissionPolicy: this.admissionPolicy ?? null,
      finalDraftAdmissionStrategy: this.finalDraftAdmissionStrategy ?? null,
      baseUrl, dataDir: this.dataDir,
    });
    await this.event("init", { l0Count: before.l0Count, l1Count: before.l1Count, rowsSha256: before.rowsSha256 });
    return { profile: { ...PROFILE, recallTopK: this.recallTopK }, dataDir: this.dataDir, ...before };
  }

  async recall(input: any) {
    if (!this.core || this.closed || this.pendingCapture) throw new Error("recall requires an initialized, uncaptured episode");
    if (this.draft) throw new Error("one initial recall per episode; no result-driven reselection");
    const before = await this.snapshot();
    const treatment = input.treatment;
    const excludedRecordIds: string[] = [];
    if (treatment) {
      const exact = before.records.filter(row => row.record_id === treatment.recordId);
      if (!Number.isSafeInteger(treatment.expectedVersion) || treatment.expectedVersion < 1
        || exact.length !== 1 || exact[0].version !== treatment.expectedVersion) {
        await this.event("treatment_abstain", { reason: "stale_treatment_identity", treatment });
        throw new Error("stale_treatment_identity");
      }
      excludedRecordIds.push(treatment.recordId);
    }
    this.excludedRecordIds = excludedRecordIds;
    this.query = String(input.query ?? "");
    if (!this.query.trim()) throw new Error("nonempty target query required");
    let receive!: (draft: RecallShadowDraft) => void;
    const pending = new Promise<RecallShadowDraft>(r => { receive = r; });
    const recall = await this.core.handleBeforeRecall(this.query, this.sessionId, {
      intervention: { excludedRecordIds }, shadowTap: { traceId: `${this.taskRunId}:initial`,
        taskRunId: this.taskRunId, sessionId: this.sessionId, onDraft: receive },
    });
    let timer: ReturnType<typeof setTimeout> | undefined;
    this.draft = await Promise.race([pending, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error("missing TDAI recall draft")), 2000);
    })]).finally(() => clearTimeout(timer));
    this.context = recall.prependContext ?? "";
    const after = await this.snapshot();
    if (before.rowsSha256 !== after.rowsSha256) throw new Error("recall modified Memory rows");
    const result = { context: this.context, contextSha256: digest(this.context),
      availableRecords: before.records.map(r => ({ recordId: r.record_id, version: r.version })),
      draft: this.draft, treatment: treatment ?? null,
      treatmentBasis: "single_owner_current_row_expected_version_guard", storeUnchanged: true };
    await save(join(this.traceDir, "recall.json"), result);
    await this.event("recall", { contextSha256: result.contextSha256, available: before.l1Count,
      prepared: this.draft.candidates.filter(row => row.budgetedText !== null).length, treatment: result.treatment });
    return result;
  }

  async acknowledge(input: any) {
    if (!this.draft || this.closed) throw new Error("recall must precede acknowledgement");
    if (this.acknowledged) return this.acknowledged;
    if (!Array.isArray(input.messages)) throw new Error("actual model wire messages required");
    const texts = input.messages.flatMap((message: any) => {
      if (!["system", "user"].includes(message.role)) return [];
      if (typeof message.content === "string") return [message.content];
      if (Array.isArray(message.content)) return message.content
        .filter((part: any) => part.type === "text" && typeof part.text === "string")
        .map((part: any) => part.text);
      return [];
    });
    const hasQuery = texts.some((text: string) => text.includes(this.query));
    const actualContext = hasQuery && this.context && texts.some((text: string) => text.includes(this.context))
      ? this.context : undefined;
    this.acknowledged = finalizeRecallShadowObservation(this.draft, new Date().toISOString(), actualContext);
    await save(join(this.traceDir, "exposure.json"), this.acknowledged);
    await this.event("acknowledge", { wireMessagesSha256: digest(canonical(input.messages)),
      hasQuery, contextSha256: digest(this.context), emptyContext: !this.context,
      promptAssemblyEvidence: this.acknowledged.promptAssemblyEvidence,
      exposed: this.acknowledged.candidates.filter(row => row.exposed).map(row => ({ recordId: row.recordId, version: row.version })) });
    return this.acknowledged;
  }

  async capture(input: any) {
    if (!this.core || this.closed || this.pendingCapture) throw new Error("only one capture per episode");
    if (!Array.isArray(input.messages) || input.messages.length === 0) throw new Error("actual episode messages required");
    const start = Date.now();
    const messages = input.messages.map((message: any, index: number) => {
      if (!["user", "assistant"].includes(message.role) || typeof message.content !== "string") {
        throw new Error("capture only original role-correct user/assistant text");
      }
      if (this.context && message.role === "user" && message.content.includes(this.context)) {
        throw new Error("injected Memory must not be recaptured as user source");
      }
      return { role: message.role, content: message.content, timestamp: start + index };
    });
    const originalUser = String(input.userText ?? messages.find((message: any) => message.role === "user")?.content ?? "");
    const assistantText = String(input.assistantText ?? messages.filter((message: any) => message.role === "assistant").at(-1)?.content ?? "");
    if (Array.isArray(input.executionMessages)) {
      const observations = await this.observe(input);
      const evidence = executionCaptureMessages(observations, start + messages.length);
      // Preserve clean source text, insert observed tool results before the terminal answer.
      const terminal = messages.at(-1)?.role === "assistant" ? messages.pop() : undefined;
      messages.push(...evidence);
      if (terminal) messages.push({ ...terminal, timestamp: start + messages.length + 1 });
    }
    await save(join(this.traceDir, "source-messages.json"), { messages, timestampBasis: "host_capture_time", originalUser });
    const result = await this.core.handleTurnCommitted({ userText: originalUser, assistantText,
      messages, sessionKey: this.sessionId, sessionId: this.sessionId, startedAt: 0,
      originalUserMessageCount: 0 });
    this.pendingCapture = true;
    await this.event("capture", { l0RecordedCount: result.l0RecordedCount,
      l0VectorsWritten: result.l0VectorsWritten, ...await this.snapshot() });
    return result;
  }

  async observe(input: any) {
    if (!this.core || this.closed) throw new Error("observation requires active sidecar");
    const observations = observeToolExecutions(input.executionMessages ?? [], {
      sessionId: this.sessionId,
      taskRunId: this.taskRunId,
    },
      input.toolResultContracts ?? {})
      .filter(o => !["tdai_memory_search", "tdai_conversation_search"].includes(o.tool));
    await save(join(this.traceDir, "tool-execution-observations.json"), observations);
    return observations;
  }

  async flush() {
    if (!this.core || this.closed) throw new Error("sidecar not initialized");
    const before = await this.snapshot();
    const started = performance.now();
    const callsBefore = this.modelCalls;
    const logsBefore = this.logs.length;
    const runner = createL1Runner({ pluginDataDir: this.dataDir, cfg: this.cfg,
      openclawConfig: undefined, vectorStore: this.store(), embeddingService: this.core.getEmbeddingService(),
      logger: this.logger, admissionPolicy: this.admissionPolicy,
      finalDraftAdmissionStrategy: this.finalDraftAdmissionStrategy,
      llmRunner: this.fakeRunner ?? this.core.getLLMRunnerFactory().createRunner({ enableTools: false }) });
    const batches = [];
    for (let i = 0; i < 4; i++) {
      const batch = await runner({ sessionKey: this.sessionId });
      batches.push(batch);
      if (!batch.hasMore && !batch.hasFullBacklog) break;
      if (i === 3) throw new Error("capture backlog exceeds bounded episode flush");
    }
    const after = await this.snapshot();
    const checkpoint = new CheckpointManager(this.dataDir, this.logger);
    const cursor = checkpoint.getRunnerState(await checkpoint.read(), this.sessionId).last_l1_cursor;
    const remaining = await this.store().queryL0ForL1(this.sessionId, cursor || undefined, 1);
    // The existing extractor can catch a model/parse failure and still advance
    // its cursor. A drained cursor alone must not establish successful capture.
    const extractionErrors = this.logs.slice(logsBefore).filter(line =>
      /LLM extraction failed|No JSON array found in extraction response|Failed to parse extraction result|Extraction response is not an array/.test(line));
    const complete = remaining.length === 0 && extractionErrors.length === 0;
    const result = { complete, batches, pendingL0Rows: remaining.length, cursor,
      extractionErrors, failureOwner: extractionErrors.length ? "extraction_model_or_parser" : null,
      l0Count: after.l0Count, l1Count: after.l1Count,
      storedCount: batches.reduce((sum, batch) => sum + batch.storedCount, 0),
      records: after.records, initialRowsSha256: before.rowsSha256, finalRowsSha256: after.rowsSha256,
      modelCalls: this.modelCalls - callsBefore, wallTimeMs: performance.now() - started,
      admissionPolicy: this.admissionPolicy ?? null,
      memoryOrigin: "actual episode -> standard L0 capture -> L1 admission -> dedup/writer" };
    await save(join(this.traceDir, "materialized-memory.json"), result);
    await this.event("flush", result);
    if (!complete) throw new Error(extractionErrors.length
      ? "source_extraction_failed_despite_cursor_advance" : "source extraction did not consume all captured L0");
    return result;
  }

  async search(input: any) {
    if (!this.core || this.closed || this.pendingCapture) throw new Error("search requires active task");
    const query = String(input.query ?? "").trim();
    if (!query) throw new Error("search query required");
    const result = input.layer === "L0"
      ? await this.core.searchConversations({ query, limit: 5 })
      : await this.core.searchMemories({ query, limit: 5, excludedRecordIds: this.excludedRecordIds });
    await this.event("active_search", { layer: input.layer, query,
      excludedRecordIds: input.layer === "L1" ? this.excludedRecordIds : [], result });
    return result;
  }

  async close() {
    if (this.closed) return { closed: true };
    const result = this.core ? await this.snapshot() : null;
    if (this.originalFetch) globalThis.fetch = this.originalFetch;
    this.originalFetch = undefined;
    await this.core?.destroy();
    this.closed = true;
    if (this.traceDir) {
      await save(join(this.traceDir, "closed-memory.json"), result);
      await writeFile(join(this.traceDir, "sidecar.log"), this.logs.join("\n") + "\n");
      await this.event("close", { closed: true, modelCalls: this.modelCalls, sqliteClosed: true });
    }
    return { closed: true, modelCalls: this.modelCalls, snapshot: result };
  }
}

async function main() {
  // Existing dependency diagnostics must not contaminate the JSONL transport.
  console.log = (...values) => process.stderr.write(values.map(String).join(" ") + "\n");
  const sidecar = new TdaiEpisodeSidecar();
  const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
  try {
    for await (const line of input) {
      let request: any;
      try {
        request = JSON.parse(line);
        const op = request.op;
        if (!["init", "recall", "acknowledge", "capture", "observe", "flush", "search", "close"].includes(op)) throw new Error("unknown operation");
        const data = await (sidecar[op as keyof TdaiEpisodeSidecar] as Function).call(sidecar, request);
        process.stdout.write(canonical({ id: request.id, ok: true, data }) + "\n");
        if (op === "close") break;
      } catch (error) {
        process.stdout.write(canonical({ id: request?.id ?? null, ok: false,
          error: error instanceof Error ? error.message : String(error) }) + "\n");
      }
    }
  } finally { await sidecar.close(); }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { process.stderr.write(String(error) + "\n"); process.exitCode = 1; });
}
