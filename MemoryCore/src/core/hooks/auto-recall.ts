/**
 * auto-recall hook (v3): injects relevant memories + persona into agent context
 * before the agent starts processing.
 *
 * - Searches L1 memories using configurable strategy (keyword / embedding / hybrid)
 *   - keyword: FTS5 BM25 (requires FTS5; returns empty if unavailable)
 *   - embedding: VectorStore cosine similarity
 *   - hybrid: keyword + embedding merged with RRF
 * - L3 persona injection
 * - L2 scene navigation (full injection, LLM decides relevance)
 */

import type { MemoryTdaiConfig } from "../../config.js";
import { readSceneIndex } from "../scene/scene-index.js";
import { generateSceneNavigation, stripSceneNavigation } from "../scene/scene-navigation.js";
import { RecallErrors, toRecallFailure, type RecallError } from "./recall-errors.js";
import type { IMemoryStore, L1SearchResult } from "../store/types.js";
import { buildFtsQuery } from "../store/sqlite.js";
import type { EmbeddingService, EmbeddingCallOptions } from "../store/embedding.js";
import { sanitizeText } from "../../utils/sanitize.js";
import path from "node:path";
import { createScopedStorageAdapter, type StorageAdapter } from "../storage/adapter.js";
import { StoragePaths } from "../storage/types.js";
import {
  DEFAULT_PROFILE_SCOPE,
  buildProfileIsolationScope,
  type ProfileIsolation,
} from "../profile/profile-sync.js";
import type { Logger } from "../types.js";
import {
  applyStructuredRecallBudget,
  createRecallShadowDraft,
  type BudgetedRecallCandidate,
  type RecallSearchFacts,
  type RecallShadowDraft,
  type StructuredRecallCandidate,
} from "../self-supervision/recall-shadow-adapter.js";

const TAG = "[memory-tdai] [recall]";
const RECALL_LINE_SEPARATOR = "\n";

/**
 * Optional, default-off handoff into the shadow observation plane. The hook
 * emits only an in-memory draft; a host-level prompt acknowledgement must
 * finalize it before any candidate can be called exposed.
 */
export interface AutoRecallShadowTap {
  traceId: string;
  capturedAt?: string;
  sessionId?: string | null;
  taskRunId?: string | null;
  onDraft: (draft: RecallShadowDraft) => void | Promise<void>;
}

/**
 * Shadow-only retrieval intervention used by value replay. The listed records
 * are removed before ranking so the normal TDAI retrieval/budget path is run
 * again over the remaining Memory set.
 */
export interface AutoRecallIntervention {
  excludedRecordIds?: readonly string[];
}

/**
 * Memory tools usage guide — injected at the end of memory context so the
 * main agent knows how to actively retrieve deeper information.
 */
const MEMORY_TOOLS_GUIDE = `<memory-tools-guide>
## 记忆工具调用指南

当上方注入的记忆片段不足以回答用户问题时，可主动调用以下工具获取更多信息：

- **tdai_memory_search**：搜索结构化记忆（L1），适用于回忆用户偏好、历史事件节点、规则等关键信息。
- **tdai_conversation_search**：搜索原始对话（L0），适用于查找具体消息原文、时间线、上下文细节；也可用于补充或校验 memory_search 的结果。
- **read_file**（Scene Navigation 中的路径）：当已定位到相关情境，且需要该场景的完整画像、事件经过或阶段结论时使用。

### ⚠️ 调用次数限制
每轮对话中，tdai_memory_search 和 tdai_conversation_search **合计最多调用 3 次**。
- 首次搜索无结果时，可换关键词或换工具重试，但总调用次数不要超过 3 次。
- 若 3 次搜索后仍无结果，说明该信息不在记忆中，请直接根据已有信息回复用户，不要继续搜索。
</memory-tools-guide>`

/** A single recalled L1 memory with its search score and type. */
export interface RecalledMemory {
  content: string;
  score: number;
  type: string;
}

export interface RecallResult {
  /** L1 relevant memories — prepended to user prompt text (dynamic, per-turn) */
  prependContext?: string;
  /** Stable recall context appended to system prompt (persona, scene nav, tools guide — cacheable) */
  appendSystemContext?: string;

  // ── Metric payload (for pendingRecallCache in index.ts) ──
  /** L1 memories that were recalled (with scores), for metric reporting */
  recalledL1Memories?: RecalledMemory[];
  /** L3 Persona raw content loaded during recall (null if none) */
  recalledL3Persona?: string | null;
  /** Effective search strategy used */
  recallStrategy?: string;

  // ── H-15: structured failure signal ──
  /**
   * When recall fails, this is populated with a RecallError; success path leaves it undefined.
   * Callers (gateway handlers) should check `result.error` and surface it in the response envelope.
   * The other fields are still populated with safe defaults (empty strings / arrays) so that
   * downstream code that ignores `error` does not NPE.
   */
  error?: RecallError;
  /**
   * Partial success indicator: true when some recall steps succeeded but others failed
   * (e.g. L1 search OK but persona read failed). When true, `error` reflects the failed step.
   */
  partial?: boolean;
}

export async function performAutoRecall(params: {
  userText: string;
  actorId: string;
  sessionKey: string;
  cfg: MemoryTdaiConfig;
  pluginDataDir: string;
  logger?: Logger;
  vectorStore?: IMemoryStore;
  embeddingService?: EmbeddingService;
  /** StorageAdapter for file operations (COS/local). Falls back to fs when absent. */
  storage?: StorageAdapter;
  /** L2/L3 profile scope. Defaults to the standalone default team and agent. */
  profileIsolation?: ProfileIsolation;
  /** Default-off, fail-open shadow recall tap. It cannot mutate Memory. */
  shadowTap?: AutoRecallShadowTap;
  /** Optional pre-retrieval exclusion for isolated counterfactual replay. */
  intervention?: AutoRecallIntervention;
}): Promise<RecallResult | undefined> {
  const { cfg, logger } = params;
  const timeoutMs = cfg.recall.timeoutMs ?? 5000;

  let timer: ReturnType<typeof setTimeout> | undefined;

  return Promise.race([
    performAutoRecallInner(params).finally(() => {
      if (timer) clearTimeout(timer);
    }),
    // H-15: timeout returns a structured RecallResult.error instead of undefined
    // so the gateway layer can distinguish "no recall results" (undefined) from
    // "recall timed out" (result.error.code === 20001) in the response envelope.
    new Promise<RecallResult>((resolve) => {
      timer = setTimeout(() => {
        logger?.warn?.(
          `${TAG} ⚠️ Recall timed out after ${timeoutMs}ms — surfacing as RecallResult.error`,
        );
        resolve({
          prependContext: "",
          appendSystemContext: "",
          recalledL1Memories: [],
          recalledL3Persona: null,
          error: RecallErrors.dependencyTimeout("recall").recallError,
          partial: false,
        });
      }, timeoutMs);
    }),
  ]);
}

/**
 * Core recall logic — may throw RecallFailure (or any unhandled error) when
 * a fatal failure occurs. Wrapped by `performAutoRecallInner` which catches
 * and translates failures into structured `RecallResult.error`.
 *
 * Returns:
 *   - RecallResult — when recall succeeded and there is content to inject
 *   - undefined    — when recall succeeded but there is nothing to inject
 *                    (empty memory + no persona + no scene navigation)
 *
 * Never returns a RecallResult with `error` populated; that is the wrapper's job.
 */
async function performAutoRecallCore(params: {
  userText: string;
  actorId: string;
  sessionKey: string;
  cfg: MemoryTdaiConfig;
  pluginDataDir: string;
  logger?: Logger;
  vectorStore?: IMemoryStore;
  embeddingService?: EmbeddingService;
  storage?: StorageAdapter;
  profileIsolation?: ProfileIsolation;
  shadowTap?: AutoRecallShadowTap;
  intervention?: AutoRecallIntervention;
}): Promise<RecallResult | undefined> {
  const { userText, cfg, pluginDataDir, logger, vectorStore, embeddingService, storage } = params;
  const tRecallStart = performance.now();

  // L2/L3 writers scope profile files by team+agent. Recall resolves the same
  // scope and never falls back to the unscoped data root, preventing cross-scope
  // profile reads.
  const profileIsolation = params.profileIsolation ?? { teamId: "default", agentId: "default" };
  const profileScope = buildProfileIsolationScope(profileIsolation);
  const isScopedProfile = profileScope !== DEFAULT_PROFILE_SCOPE;
  const profileDataDir = isScopedProfile
    ? path.join(pluginDataDir, "profiles", encodeURIComponent(profileScope))
    : pluginDataDir;
  const profileStorage = storage && isScopedProfile
    ? createScopedStorageAdapter(storage, `profiles/${encodeURIComponent(profileScope)}/`)
    : storage;

  // Search relevant memories (L1 layer) — skip only when userText is empty/undefined
  const tSearchStart = performance.now();
  let memoryLines: string[] = [];
  let budgetedCandidates: BudgetedRecallCandidate[] = [];
  let effectiveStrategy = "skipped";
  let recalledL1Memories: RecalledMemory[] = [];
  let searchFacts: RecallSearchFacts = {
    strategy: "skipped",
    status: "skipped",
    failureCode: null,
    queryEligible: false,
    configuredMaxResults: cfg.recall.maxResults ?? 5,
    configuredScoreThreshold: cfg.recall.scoreThreshold ?? 0.3,
    rawCandidateCount: 0,
    scoreFilteredCount: 0,
    rankPrunedCount: 0,
    selectedCandidateCount: 0,
    smallCorpusThresholdBypass: false,
  };
  let searchTiming: SearchTiming = { ftsMs: 0, embeddingMs: 0, ftsHits: 0, embeddingHits: 0 };
  if (!userText || userText.length === 0) {
    logger?.debug?.(`${TAG} User text empty/undefined, skipping memory search (persona/scene still injected)`);
  } else {
    effectiveStrategy = cfg.recall.strategy ?? "hybrid";
    const searchResult = await searchMemories(
      userText,
      pluginDataDir,
      cfg,
      logger,
      effectiveStrategy as "keyword" | "embedding" | "hybrid",
      vectorStore,
      embeddingService,
      params.intervention?.excludedRecordIds,
    );
    searchTiming = searchResult.timing;
    searchFacts = searchResult.facts;
    budgetedCandidates = applyStructuredRecallBudget(searchResult.candidates, cfg.recall);
    memoryLines = budgetedCandidates.flatMap((candidate) =>
      candidate.budgetedText === null ? [] : [candidate.budgetedText]);
    recalledL1Memories = budgetedCandidates.flatMap((candidate) => candidate.budgetedText === null
      ? []
      : [{
        content: candidate.row.content,
        // Preserve the public metric payload's legacy behavior: only the
        // native-hybrid path previously surfaced scores. The shadow tuple
        // still retains the real score for every strategy.
        score: searchResult.exposeScoresToMetrics ? candidate.score : 0,
        type: candidate.row.type,
      }]);

    const truncatedCount = budgetedCandidates.filter((candidate) => candidate.truncated).length;
    const droppedCount = budgetedCandidates.filter((candidate) => candidate.notExposedReason === "budget_pruned").length;
    if (truncatedCount > 0 || droppedCount > 0) {
      logger?.debug?.(
        `${TAG} Recall budget applied: input=${budgetedCandidates.length}, output=${memoryLines.length}, ` +
        `truncated=${truncatedCount}, dropped=${droppedCount}, ` +
        `maxCharsPerMemory=${cfg.recall.maxCharsPerMemory}, maxTotalRecallChars=${cfg.recall.maxTotalRecallChars}`,
      );
    }
  }
  const tSearchEnd = performance.now();

  // Read persona (L3 layer)
  const tPersonaStart = performance.now();
  let personaContent: string | undefined;
  try {
    let raw: string | null = null;
    if (profileStorage) {
      raw = await profileStorage.readFile(StoragePaths.persona);
    } else {
      const fs = await import("node:fs/promises");
      raw = await fs.default.readFile(path.join(profileDataDir, "persona.md"), "utf-8");
    }
    if (raw) {
      personaContent = stripSceneNavigation(raw).trim();
      if (!personaContent) personaContent = undefined;
    }
    logger?.debug?.(`${TAG} Persona loaded: ${personaContent ? `${personaContent.length} chars` : "empty"}`);
  } catch {
    logger?.debug?.(`${TAG} No persona file found (expected for new users)`);
  }
  const tPersonaEnd = performance.now();

  // Load full scene navigation (L2 layer)
  const tSceneStart = performance.now();
  let sceneNavigation: string | undefined;
  try {
    const sceneIndex = await readSceneIndex(profileDataDir, profileStorage);
    if (sceneIndex.length > 0) {
      const useCos = profileStorage?.type === "cos";
      sceneNavigation = generateSceneNavigation(sceneIndex, profileDataDir, useCos);
      logger?.debug?.(
        `${TAG} Scene navigation generated: ${sceneIndex.length} scenes ` +
        `(scope=${profileScope}, useCos=${useCos})`,
      );
    }
  } catch {
    logger?.debug?.(`${TAG} No scene index found`);
  }
  const tSceneEnd = performance.now();

  if (memoryLines.length === 0 && !personaContent && !sceneNavigation) {
    const totalMs = performance.now() - tRecallStart;
    logger?.info(
      `${TAG} ⏱ Recall timing: total=${totalMs.toFixed(0)}ms, ` +
      `search=${(tSearchEnd - tSearchStart).toFixed(0)}ms(strategy=${effectiveStrategy},hits=${memoryLines.length},` +
      `fts=${searchTiming.ftsMs.toFixed(0)}ms/${searchTiming.ftsHits}hits,` +
      `vec=${searchTiming.embeddingMs.toFixed(0)}ms/${searchTiming.embeddingHits}hits), ` +
      `persona=${(tPersonaEnd - tPersonaStart).toFixed(0)}ms, ` +
      `scene=${(tSceneEnd - tSceneStart).toFixed(0)}ms — no context to inject`,
    );
    logger?.debug?.(`${TAG} No memories/persona/scenes to inject`);
    emitShadowRecallDraft(params, searchFacts, budgetedCandidates, undefined);
    return undefined;
  }

  // Split recall context into stable and dynamic parts to optimize prompt caching.
  //
  // appendSystemContext (system prompt end — stable, cacheable):
  //   persona, scene navigation, memory tools guide
  //   These change infrequently; when content is identical across turns,
  //   providers with prompt caching (Anthropic/OpenAI) can cache this region.
  //
  // prependContext (user prompt prefix — dynamic, per-turn):
  //   L1 relevant memories — different every turn, moved out of system prompt
  //   so it doesn't bust the system prompt cache.
  const stableParts: string[] = [];
  if (personaContent) {
    stableParts.push(`<user-persona>\n${personaContent}\n</user-persona>`);
  }
  if (sceneNavigation) {
    stableParts.push(`<scene-navigation>\n${sceneNavigation}\n</scene-navigation>`);
  }

  // Dynamic part: L1 relevant memories (changes every turn) → prependContext (user prompt)
  let prependContext: string | undefined;
  if (memoryLines.length > 0) {
    prependContext =
      `<relevant-memories>\n以下是当前对话召回的相关记忆，不代表当前任务进程，仅作为参考：\n\n${memoryLines.join(RECALL_LINE_SEPARATOR)}\n</relevant-memories>`;
  }

  // Append memory tools usage guide to the stable part so the agent knows
  // how to actively retrieve deeper context when the injected snippets
  // are not enough. This is static content and benefits from caching.
  if (stableParts.length > 0 || prependContext) {
    stableParts.push(MEMORY_TOOLS_GUIDE);
  }

  const appendSystemContext = stableParts.length > 0 ? stableParts.join("\n\n") : undefined;

  const totalMs = performance.now() - tRecallStart;
  logger?.info(
    `${TAG} ⏱ Recall timing: total=${totalMs.toFixed(0)}ms, ` +
    `search=${(tSearchEnd - tSearchStart).toFixed(0)}ms(strategy=${effectiveStrategy},hits=${memoryLines.length},` +
    `fts=${searchTiming.ftsMs.toFixed(0)}ms/${searchTiming.ftsHits}hits,` +
    `vec=${searchTiming.embeddingMs.toFixed(0)}ms/${searchTiming.embeddingHits}hits), ` +
    `persona=${(tPersonaEnd - tPersonaStart).toFixed(0)}ms(${personaContent ? `${personaContent.length}chars` : "none"}), ` +
    `scene=${(tSceneEnd - tSceneStart).toFixed(0)}ms(${sceneNavigation ? "loaded" : "none"})`,
  );

  if (!appendSystemContext && !prependContext) {
    return undefined;
  }

  const result: RecallResult = {
    prependContext,
    appendSystemContext,
    recalledL1Memories,
    recalledL3Persona: personaContent ?? null,
    recallStrategy: effectiveStrategy,
  };
  emitShadowRecallDraft(params, searchFacts, budgetedCandidates, prependContext);
  return result;
}

function emitShadowRecallDraft(
  params: {
    userText: string;
    actorId: string;
    sessionKey: string;
    cfg: MemoryTdaiConfig;
    logger?: Logger;
    shadowTap?: AutoRecallShadowTap;
  },
  search: RecallSearchFacts,
  candidates: BudgetedRecallCandidate[],
  expectedPrependContext: string | undefined,
): void {
  const tap = params.shadowTap;
  if (!tap) return;

  let draft: RecallShadowDraft;
  try {
    draft = createRecallShadowDraft({
      traceId: tap.traceId,
      capturedAt: tap.capturedAt ?? new Date().toISOString(),
      sessionKey: params.sessionKey,
      sessionId: tap.sessionId,
      taskRunId: tap.taskRunId,
      actorId: params.actorId,
      query: params.userText,
      expectedPrependContext,
      search,
      limits: params.cfg.recall,
      candidates,
    });
  } catch (error) {
    params.logger?.warn?.(
      `${TAG} shadow recall draft capture failed (ignored): ${error instanceof Error ? error.message : String(error)}`,
    );
    return;
  }

  // The observation sidecar is deliberately outside the recall critical
  // path. Both a synchronous throw and an asynchronously rejected observer
  // promise are contained and can never change the user-visible result.
  queueMicrotask(() => {
    try {
      void Promise.resolve(tap.onDraft(draft)).catch((error: unknown) => {
        params.logger?.warn?.(
          `${TAG} shadow recall draft capture failed (ignored): ${error instanceof Error ? error.message : String(error)}`,
        );
      });
    } catch (error) {
      params.logger?.warn?.(
        `${TAG} shadow recall draft capture failed (ignored): ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  });
}

/**
 * H-15 wrapper: catches errors from performAutoRecallCore and translates them
 * into a structured RecallResult with `error` populated.
 *
 * Contract: this function never throws. Callers can rely on:
 *   - returns RecallResult (possibly with `error` field) — failure with structured info
 *   - returns RecallResult (without `error` field)        — success with content
 *   - returns undefined                                   — success with nothing to inject
 *
 * The hook layer (performAutoRecall) further normalizes timeout into RecallResult.error.
 */
async function performAutoRecallInner(params: {
  userText: string;
  actorId: string;
  sessionKey: string;
  cfg: MemoryTdaiConfig;
  pluginDataDir: string;
  logger?: Logger;
  vectorStore?: IMemoryStore;
  embeddingService?: EmbeddingService;
  storage?: StorageAdapter;
  profileIsolation?: ProfileIsolation;
  shadowTap?: AutoRecallShadowTap;
  intervention?: AutoRecallIntervention;
}): Promise<RecallResult | undefined> {
  try {
    return await performAutoRecallCore(params);
  } catch (err) {
    const fail = toRecallFailure(err);
    const re = fail.recallError;
    // Always log at warn; for internal errors, also dump the cause at error level
    // to make root-cause investigation possible.
    params.logger?.warn?.(
      `${TAG} recall failed: code=${re.code} category=${re.category} msg="${re.message}"`,
    );
    if (re.category === "internal" && fail.cause) {
      const causeStr = fail.cause instanceof Error
        ? (fail.cause.stack ?? fail.cause.message)
        : String(fail.cause);
      params.logger?.error?.(`${TAG} unexpected recall error cause: ${causeStr}`);
    }
    return {
      prependContext: "",
      appendSystemContext: "",
      recalledL1Memories: [],
      recalledL3Persona: null,
      recallStrategy: undefined,
      error: re,
      partial: false,
    };
  }
}

// ============================
// Multi-strategy search dispatcher
// ============================

/** Timing breakdown from memory search */
interface SearchTiming {
  ftsMs: number;
  embeddingMs: number;
  ftsHits: number;
  embeddingHits: number;
}

interface SearchResult {
  candidates: StructuredRecallCandidate[];
  timing: SearchTiming;
  facts: RecallSearchFacts;
  /** Backward compatibility for the existing public metric-only payload. */
  exposeScoresToMetrics?: true;
}

/**
 * Search memories using the configured strategy.
 *
 * - "keyword": JSONL keyword-based (Jaccard similarity) — no embedding needed
 * - "embedding": VectorStore cosine similarity — requires vectorStore + embeddingService
 * - "hybrid": merge both keyword and embedding results with RRF (Reciprocal Rank Fusion)
 *
 * Falls back to keyword if embedding resources are unavailable.
 */
async function searchMemories(
  userText: string,
  pluginDataDir: string,
  cfg: MemoryTdaiConfig,
  logger: Logger | undefined,
  strategy: "keyword" | "embedding" | "hybrid",
  vectorStore?: IMemoryStore,
  embeddingService?: EmbeddingService,
  excludedRecordIds?: readonly string[],
): Promise<SearchResult> {
  const maxResults = cfg.recall.maxResults ?? 5;
  const threshold = cfg.recall.scoreThreshold ?? 0.3;
  const excludedIds = new Set(
    (excludedRecordIds ?? []).filter((recordId) => typeof recordId === "string" && recordId.trim().length > 0),
  );
  const emptyResult: SearchResult = {
    candidates: [],
    timing: { ftsMs: 0, embeddingMs: 0, ftsHits: 0, embeddingHits: 0 },
    facts: {
      strategy,
      status: "skipped",
      failureCode: null,
      queryEligible: false,
      configuredMaxResults: maxResults,
      configuredScoreThreshold: threshold,
      rawCandidateCount: 0,
      scoreFilteredCount: 0,
      rankPrunedCount: 0,
      selectedCandidateCount: 0,
      smallCorpusThresholdBypass: false,
    },
  };
  // Strip gateway-injected inbound metadata (Sender, timestamps, media markers,
  // base64 image data, etc.) so FTS / embedding queries are based on pure user intent.
  const cleanText = sanitizeText(userText);

  if (cleanText.length < 2) {
    logger?.debug?.(`${TAG} Query too short for memory search (raw=${userText.length}, clean=${cleanText.length})`);
    return emptyResult;
  }

  if (cleanText.length !== userText.length) {
    logger?.debug?.(
      `${TAG} userText sanitized: ${userText.length} → ${cleanText.length} chars`,
    );
  }

  emptyResult.facts.queryEligible = true;
  emptyResult.facts.status = "completed";

  const embeddingAvailable = !!vectorStore && !!embeddingService;

  logger?.debug?.(
    `${TAG} [searchMemories] strategy=${strategy}, embeddingAvailable=${embeddingAvailable}, ` +
    `vectorStore=${vectorStore ? "available" : "UNAVAILABLE"}, ` +
    `embeddingService=${embeddingService ? "available" : "UNAVAILABLE"}, ` +
    `maxResults=${maxResults}, threshold=${threshold}`,
  );

  // Determine effective strategy — no degradation: if embedding is configured but unavailable, fail
  let effectiveStrategy = strategy;
  if ((strategy === "embedding" || strategy === "hybrid") && !embeddingAvailable) {
    // H-15: throw structured RecallFailure so the top-level catch in
    // performAutoRecallInner can translate it into RecallResult.error
    // (preserves fast-fail semantics + observability while keeping the
    // hook contract "always resolves, never rejects").
    throw RecallErrors.configMissingEmbedding(strategy);
  }

  logger?.debug?.(`${TAG} Search strategy: ${effectiveStrategy} (configured: ${strategy})`);

  // Resolve per-call embedding timeout for recall path.
  // Falls back to global embedding.timeoutMs when recallTimeoutMs is not configured.
  const recallEmbeddingTimeoutMs = cfg.embedding?.recallTimeoutMs ?? cfg.embedding?.timeoutMs;
  const embeddingCallOpts: EmbeddingCallOptions = { timeoutMs: recallEmbeddingTimeoutMs };

  try {
    if (effectiveStrategy === "keyword") {
      const tFts = performance.now();
      const result = await searchByKeyword(
        cleanText,
        pluginDataDir,
        maxResults,
        threshold,
        logger,
        vectorStore,
        excludedIds,
      );
      const candidates = toStructuredCandidates(result.rows, "l1_keyword");
      return {
        candidates,
        timing: { ftsMs: performance.now() - tFts, embeddingMs: 0, ftsHits: candidates.length, embeddingHits: 0 },
        facts: {
          ...emptyResult.facts,
          rawCandidateCount: result.rawCandidateCount,
          scoreFilteredCount: result.scoreFilteredCount,
          rankPrunedCount: result.rankPrunedCount,
          selectedCandidateCount: candidates.length,
          smallCorpusThresholdBypass: result.smallCorpusThresholdBypass,
        },
      };
    }

    if (effectiveStrategy === "embedding") {
      const tEmb = performance.now();
      const result = await searchByEmbedding(
        cleanText,
        maxResults,
        threshold,
        vectorStore!,
        embeddingService!,
        logger,
        embeddingCallOpts,
        excludedIds,
      );
      const candidates = toStructuredCandidates(result.rows, "l1_embedding");
      return {
        candidates,
        timing: { ftsMs: 0, embeddingMs: performance.now() - tEmb, ftsHits: 0, embeddingHits: candidates.length },
        facts: {
          ...emptyResult.facts,
          rawCandidateCount: result.rawCandidateCount,
          scoreFilteredCount: result.scoreFilteredCount,
          rankPrunedCount: result.rankPrunedCount,
          selectedCandidateCount: candidates.length,
        },
      };
    }

    // Hybrid: if the store natively supports hybrid search (e.g. TCVDB does
    // server-side dense + sparse + RRF in a single API call), short-circuit
    // to avoid a redundant second HTTP request and a wasted local embed().
    if (vectorStore?.getCapabilities().nativeHybridSearch && vectorStore.searchL1Hybrid) {
      const tNative = performance.now();
      const rawResults = await vectorStore.searchL1Hybrid({
        query: cleanText,
        topK: maxResults + excludedIds.size,
      });
      const availableResults = rawResults.filter((row) => !excludedIds.has(row.record_id));
      const results = availableResults.slice(0, maxResults);
      const nativeMs = performance.now() - tNative;
      logger?.debug?.(`${TAG} [hybrid-native] Single-call hybrid: ${results.length} results in ${nativeMs.toFixed(0)}ms`);
      const candidates = toStructuredCandidates(results, "l1_hybrid");
      return {
        candidates,
        timing: { ftsMs: 0, embeddingMs: nativeMs, ftsHits: 0, embeddingHits: results.length },
        exposeScoresToMetrics: true,
        facts: {
          ...emptyResult.facts,
          rawCandidateCount: availableResults.length,
          rankPrunedCount: Math.max(0, availableResults.length - results.length),
          selectedCandidateCount: candidates.length,
        },
      };
    }

    // Fallback: run keyword + embedding in parallel, merge with client-side RRF (SQLite path)
    return await searchHybrid(
      cleanText,
      pluginDataDir,
      maxResults,
      threshold,
      vectorStore!,
      embeddingService!,
      logger,
      embeddingCallOpts,
      excludedIds,
    );
  } catch (err) {
    logger?.warn?.(`${TAG} Memory search failed (strategy=${effectiveStrategy}): ${err instanceof Error ? err.message : String(err)}`);
    emptyResult.facts.status = "failed";
    emptyResult.facts.failureCode = err instanceof Error && err.name ? err.name : "unknown_error";
    return emptyResult;
  }
}

// ============================
// Strategy: Keyword (FTS5 BM25, no in-memory fallback)
// ============================

async function searchByKeyword(
  userText: string,
  _pluginDataDir: string,
  maxResults: number,
  threshold: number,
  logger?: Logger,
  vectorStore?: IMemoryStore,
  excludedIds: ReadonlySet<string> = new Set(),
): Promise<{
  rows: L1SearchResult[];
  rawCandidateCount: number;
  scoreFilteredCount: number;
  rankPrunedCount: number;
  smallCorpusThresholdBypass: boolean;
}> {
  // Prefer FTS5 if available
  if (vectorStore?.isFtsAvailable()) {
    const ftsQuery = buildFtsQuery(userText);
    if (ftsQuery) {
      logger?.debug?.(`${TAG} [keyword-fts] Using FTS5 BM25 search: query="${ftsQuery}"`);
      const rawFtsResults = await vectorStore.searchL1Fts(
        ftsQuery,
        maxResults * 2 + excludedIds.size,
      );
      const ftsResults = rawFtsResults.filter((row) => !excludedIds.has(row.record_id));
      if (ftsResults.length > 0) {
        logger?.debug?.(
          `${TAG} [keyword-fts] FTS5 raw results (${ftsResults.length}): ` +
          ftsResults.map((r) => `id=${r.record_id} score=${r.score.toFixed(6)}`).join(", "),
        );
        const aboveThreshold = ftsResults.filter((r) => r.score >= threshold);
        const filtered = aboveThreshold.slice(0, maxResults);

        if (filtered.length > 0) {
          logger?.debug?.(`${TAG} [keyword-fts] FTS5 found ${filtered.length} results (from ${ftsResults.length} raw, threshold=${threshold})`);
          return {
            rows: filtered,
            rawCandidateCount: ftsResults.length,
            scoreFilteredCount: ftsResults.length - aboveThreshold.length,
            rankPrunedCount: aboveThreshold.length - filtered.length,
            smallCorpusThresholdBypass: false,
          };
        }

        // BM25 absolute scores are unreliable when the document set is very
        // small (e.g. 1–3 records) because IDF approaches 0.  In that case,
        // trust FTS5's MATCH + rank ordering and return the top results anyway.
        if (ftsResults.length <= maxResults) {
          logger?.debug?.(
            `${TAG} [keyword-fts] All ${ftsResults.length} results below threshold=${threshold} ` +
            `but document set is small — returning all matched results`,
          );
          return {
            rows: ftsResults.slice(0, maxResults),
            rawCandidateCount: ftsResults.length,
            scoreFilteredCount: 0,
            rankPrunedCount: Math.max(0, ftsResults.length - maxResults),
            smallCorpusThresholdBypass: true,
          };
        }
        logger?.debug?.(`${TAG} [keyword-fts] FTS5 returned 0 results above threshold (from ${ftsResults.length} raw)`);
        return {
          rows: [],
          rawCandidateCount: ftsResults.length,
          scoreFilteredCount: ftsResults.length,
          rankPrunedCount: 0,
          smallCorpusThresholdBypass: false,
        };
      }
    }
  }

  // FTS5 not available or returned no results — skip in-memory fallback to avoid O(N) full scan
  logger?.debug?.(`${TAG} [keyword] FTS5 unavailable or no results, skipping keyword search`);
  return {
    rows: [],
    rawCandidateCount: 0,
    scoreFilteredCount: 0,
    rankPrunedCount: 0,
    smallCorpusThresholdBypass: false,
  };
}

// ============================
// Strategy: Embedding (VectorStore cosine)
// ============================

async function searchByEmbedding(
  userText: string,
  maxResults: number,
  threshold: number,
  vectorStore: IMemoryStore,
  embeddingService: EmbeddingService,
  logger?: Logger,
  embeddingCallOpts?: EmbeddingCallOptions,
  excludedIds: ReadonlySet<string> = new Set(),
): Promise<{
  rows: L1SearchResult[];
  rawCandidateCount: number;
  scoreFilteredCount: number;
  rankPrunedCount: number;
}> {
  logger?.debug?.(
    `${TAG} [embedding-search] START query="${userText.slice(0, 80)}...", maxResults=${maxResults}, threshold=${threshold}`,
  );
  const queryEmbedding = await embeddingService.embed(userText, embeddingCallOpts);
  logger?.debug?.(
    `${TAG} [embedding-search] Query embedding OK: dims=${queryEmbedding.length}, ` +
    `norm=${Math.sqrt(Array.from(queryEmbedding).reduce((s, v) => s + v * v, 0)).toFixed(4)}, ` +
    `searching top-${maxResults * 2}...`,
  );
  // Retrieve more candidates for subsequent filtering
  const rawVecResults: L1SearchResult[] = await vectorStore.searchL1Vector(
    queryEmbedding,
    maxResults * 2 + excludedIds.size,
  );
  const vecResults = rawVecResults.filter((row) => !excludedIds.has(row.record_id));

  if (vecResults.length === 0) {
    logger?.debug?.(`${TAG} [embedding-search] Returned 0 results`);
    return { rows: [], rawCandidateCount: 0, scoreFilteredCount: 0, rankPrunedCount: 0 };
  }

  logger?.debug?.(`${TAG} [embedding-search] Got ${vecResults.length} candidates, filtering by threshold=${threshold}`);
  for (const r of vecResults) {
    logger?.debug?.(
      `${TAG} [embedding-search] candidate id=${r.record_id}, score=${r.score.toFixed(4)}, ` +
      `type=${r.type}, content="${r.content.slice(0, 60)}..."`,
    );
  }

  const aboveThreshold = vecResults.filter((r) => r.score >= threshold);
  const filtered = aboveThreshold.slice(0, maxResults);

  if (filtered.length > 0) {
    logger?.debug?.(`${TAG} [embedding-search] Found ${filtered.length} relevant memories above threshold (from ${vecResults.length} candidates)`);
    return {
      rows: filtered,
      rawCandidateCount: vecResults.length,
      scoreFilteredCount: vecResults.length - aboveThreshold.length,
      rankPrunedCount: aboveThreshold.length - filtered.length,
    };
  }

  logger?.debug?.(`${TAG} [embedding-search] No results above threshold ${threshold}`);
  return {
    rows: [],
    rawCandidateCount: vecResults.length,
    scoreFilteredCount: vecResults.length,
    rankPrunedCount: 0,
  };
}

// ============================
// Strategy: Hybrid (Keyword + Embedding + RRF)
// ============================

/**
 * Hybrid search: run keyword (FTS5) and embedding in parallel, merge with
 * Reciprocal Rank Fusion (RRF) to combine rank lists.
 *
 * RRF score for a record at rank r = 1 / (k + r), where k=60 is a constant.
 * If a record appears in both lists, its RRF scores are summed.
 *
 * If FTS5 is unavailable, the keyword side returns empty and RRF uses
 * embedding results only.
 */
async function searchHybrid(
  userText: string,
  _pluginDataDir: string,
  maxResults: number,
  _threshold: number,
  vectorStore: IMemoryStore,
  embeddingService: EmbeddingService,
  logger?: Logger,
  embeddingCallOpts?: EmbeddingCallOptions,
  excludedIds: ReadonlySet<string> = new Set(),
): Promise<SearchResult> {
  // Run keyword and embedding searches in parallel
  const candidateK = maxResults * 3 + excludedIds.size; // retrieve more for merging

  const [keywordResult, embeddingResult] = await Promise.all([
    // Keyword search: FTS5 only (no in-memory fallback)
    (async () => {
      const tStart = performance.now();
      try {
        // Try FTS5 first
        if (vectorStore.isFtsAvailable()) {
          const ftsQuery = buildFtsQuery(userText);
          if (ftsQuery) {
            const rawFtsResults = await vectorStore.searchL1Fts(ftsQuery, candidateK);
            const ftsResults = rawFtsResults.filter((row) => !excludedIds.has(row.record_id));
            if (ftsResults.length > 0) {
              logger?.debug?.(`${TAG} [hybrid-keyword-fts] FTS5 found ${ftsResults.length} candidates`);
              return { rows: ftsResults as L1SearchResult[], ms: performance.now() - tStart };
            }
          }
        }
        // FTS5 not available or returned no results — skip in-memory fallback
        logger?.debug?.(`${TAG} [hybrid-keyword] FTS5 unavailable or no results, skipping keyword part`);
        return { rows: [] as L1SearchResult[], ms: performance.now() - tStart };
      } catch (err) {
        logger?.warn?.(`${TAG} Hybrid: keyword part failed: ${err instanceof Error ? err.message : String(err)}`);
        return { rows: [] as L1SearchResult[], ms: performance.now() - tStart };
      }
    })(),
    // Embedding search
    (async () => {
      const tStart = performance.now();
      try {
        logger?.debug?.(`${TAG} [hybrid-embedding] Generating query embedding...`);
        const queryEmbedding = await embeddingService.embed(userText, embeddingCallOpts);
        logger?.debug?.(
          `${TAG} [hybrid-embedding] Embedding OK, dims=${queryEmbedding.length}, searching top-${candidateK}...`,
        );
        const rawResults = await vectorStore.searchL1Vector(queryEmbedding, candidateK, userText);
        const results = rawResults.filter((row) => !excludedIds.has(row.record_id));
        logger?.debug?.(`${TAG} [hybrid-embedding] Got ${results.length} candidates`);
        return { results, ms: performance.now() - tStart };
      } catch (err) {
        logger?.warn?.(`${TAG} Hybrid: embedding part failed: ${err instanceof Error ? err.message : String(err)}`);
        return { results: [] as L1SearchResult[], ms: performance.now() - tStart };
      }
    })(),
  ]);

  const keywordResults = keywordResult.rows;
  const embeddingResults = embeddingResult.results;
  const timing: SearchTiming = {
    ftsMs: keywordResult.ms,
    embeddingMs: embeddingResult.ms,
    ftsHits: keywordResults.length,
    embeddingHits: embeddingResults.length,
  };

  if (keywordResults.length === 0 && embeddingResults.length === 0) {
    logger?.debug?.(`${TAG} Hybrid search: both strategies returned 0 results`);
    return {
      candidates: [],
      timing,
      facts: {
        strategy: "hybrid",
        status: "completed",
        failureCode: null,
        queryEligible: true,
        configuredMaxResults: maxResults,
        configuredScoreThreshold: _threshold,
        rawCandidateCount: 0,
        scoreFilteredCount: 0,
        rankPrunedCount: 0,
        selectedCandidateCount: 0,
        smallCorpusThresholdBypass: false,
      },
    };
  }

  // RRF merge: k=60 is a standard constant from the RRF paper
  const RRF_K = 60;

  // Map: record_id → { rrfScore, row }. Keep the full persisted identity
  // instead of reducing records to formatted text during fusion.
  const mergedMap = new Map<string, { rrfScore: number; row: L1SearchResult }>();

  // Process keyword results
  for (let rank = 0; rank < keywordResults.length; rank++) {
    const r = keywordResults[rank];
    const id = r.record_id;
    const rrfScore = 1 / (RRF_K + rank + 1);
    const existing = mergedMap.get(id);
    if (existing) {
      existing.rrfScore += rrfScore;
    } else {
      mergedMap.set(id, { rrfScore, row: r });
    }
  }

  // Process embedding results
  for (let rank = 0; rank < embeddingResults.length; rank++) {
    const r = embeddingResults[rank];
    const id = r.record_id;
    const rrfScore = 1 / (RRF_K + rank + 1);
    const existing = mergedMap.get(id);
    if (existing) {
      existing.rrfScore += rrfScore;
    } else {
      mergedMap.set(id, { rrfScore, row: r });
    }
  }

  // Sort by combined RRF score and take top results
  const sorted = [...mergedMap.entries()]
    .sort((a, b) => b[1].rrfScore - a[1].rrfScore)
    .slice(0, maxResults);

  if (sorted.length > 0) {
    logger?.debug?.(
      `${TAG} Hybrid search found ${sorted.length} results ` +
      `(keyword=${keywordResults.length}, embedding=${embeddingResults.length})`,
    );
    const candidates = sorted.map(([, { row, rrfScore }], index): StructuredRecallCandidate => ({
      row,
      retrievalRank: index + 1,
      score: rrfScore,
      stage: "l1_hybrid",
      renderedText: formatMemoryLine(vectorResultToFormatable(row)),
    }));
    return {
      candidates,
      timing,
      facts: {
        strategy: "hybrid",
        status: "completed",
        failureCode: null,
        queryEligible: true,
        configuredMaxResults: maxResults,
        configuredScoreThreshold: _threshold,
        rawCandidateCount: mergedMap.size,
        scoreFilteredCount: 0,
        rankPrunedCount: Math.max(0, mergedMap.size - candidates.length),
        selectedCandidateCount: candidates.length,
        smallCorpusThresholdBypass: false,
      },
    };
  }

  logger?.debug?.(`${TAG} Hybrid search: no results after merge`);
  return {
    candidates: [],
    timing,
    facts: {
      strategy: "hybrid",
      status: "completed",
      failureCode: null,
      queryEligible: true,
      configuredMaxResults: maxResults,
      configuredScoreThreshold: _threshold,
      rawCandidateCount: mergedMap.size,
      scoreFilteredCount: 0,
      rankPrunedCount: mergedMap.size,
      selectedCandidateCount: 0,
      smallCorpusThresholdBypass: false,
    },
  };
}

// ============================
// Unified memory line formatter
// ============================

/**
 * Format a single memory record into a rich natural-language line for prompt injection.
 *
 * Time semantics:
 *   - timestamp (点时间): when the activity/event happened, e.g. "2025-03-01 mentioned something"
 *   - activity_start_time / activity_end_time (段时间): activity time range, e.g. "trip from 2025-05-01 to 2025-05-10"
 *   - All three time fields may be empty/undefined — handled gracefully.
 *
 * Output examples:
 *   - [persona] 用户叫王小明，30岁，是一名软件工程师。
 *   - [episodic|旅行计划] 用户计划五月去日本旅行。(活动时间: 2025-05-01 ~ 2025-05-10)
 *   - [episodic] 用户今天加班到很晚。(活动时间: 2025-03-01)
 *   - [instruction] 用户要求回答时使用中文，保持简洁。
 */
interface FormatableMemory {
  type: string;
  content: string;
  scene_name?: string;
  /** Activity time range start (段时间 start), may be empty */
  activity_start_time?: string;
  /** Activity time range end (段时间 end), may be empty */
  activity_end_time?: string;
  /** Activity point-in-time (点时间: when it happened), may be empty */
  timestamp?: string;
}

function toStructuredCandidates(
  rows: L1SearchResult[],
  stage: StructuredRecallCandidate["stage"],
): StructuredRecallCandidate[] {
  return rows.map((row, index) => ({
    row,
    retrievalRank: index + 1,
    score: row.score,
    stage,
    renderedText: formatMemoryLine(vectorResultToFormatable(row)),
  }));
}

function formatMemoryLine(m: FormatableMemory): string {
  // 1. Type tag + optional scene name
  const tag = m.scene_name ? `${m.type}|${m.scene_name}` : m.type;

  // 2. Content (core)
  let line = `- [${tag}] ${m.content}`;

  // 3. Time info — prefer activity_start/end range; fall back to timestamp as point-in-time
  const start = formatTimestamp(m.activity_start_time);
  const end = formatTimestamp(m.activity_end_time);
  const point = formatTimestamp(m.timestamp);

  if (start && end) {
    // 段时间: both start and end
    line += ` (活动时间: ${start} ~ ${end})`;
  } else if (start) {
    // 段时间: only start
    line += ` (活动时间: ${start}起)`;
  } else if (end) {
    // 段时间: only end
    line += ` (活动时间: 至${end})`;
  } else if (point) {
    // 点时间: single timestamp
    line += ` (活动时间: ${point})`;
  }
  // If all three are empty → no time info appended (graceful)

  return line;
}

/**
 * Format an ISO 8601 timestamp to a concise date or datetime string.
 * - If the time part is 00:00:00 → show date only (e.g. "2025-03-01")
 * - Otherwise → show date + time (e.g. "2025-03-01 14:30")
 * - Returns undefined for empty/invalid inputs.
 */
function formatTimestamp(ts: string | undefined): string | undefined {
  if (!ts) return undefined;
  // Try to parse ISO format: "2025-03-01T14:30:00.000Z" or "2025-03-01"
  const match = ts.match(/^(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2})(?::\d{2})?)?/);
  if (!match) return undefined;
  const datePart = match[1];
  const timePart = match[2];
  if (!timePart || timePart === "00:00") {
    return datePart;
  }
  return `${datePart} ${timePart}`;
}

/**
 * Build a FormatableMemory from a VectorSearchResult (embedding search path).
 * Handles empty/invalid metadata_json, empty timestamp_str gracefully.
 */
function vectorResultToFormatable(r: L1SearchResult): FormatableMemory {
  let activityStart: string | undefined;
  let activityEnd: string | undefined;
  if (r.metadata_json && r.metadata_json !== "{}") {
    try {
      const meta = typeof r.metadata_json === "string" ? JSON.parse(r.metadata_json) : r.metadata_json;
      activityStart = meta?.activity_start_time || undefined;
      activityEnd = meta?.activity_end_time || undefined;
    } catch { /* ignore parse errors — treat as no metadata */ }
  }
  return {
    type: r.type,
    content: r.content,
    scene_name: r.scene_name || undefined,
    activity_start_time: activityStart,
    activity_end_time: activityEnd,
    timestamp: r.timestamp_str || undefined,
  };
}
