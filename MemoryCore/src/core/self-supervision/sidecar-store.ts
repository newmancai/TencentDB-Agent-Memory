import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { assertCertificateIdentifiesTuple } from "./identifiability.js";
import type { LayerAwareFeedbackSignal, SelfSupervisionSignal } from "./types.js";

export interface FeedbackSidecarStore {
  append(signal: SelfSupervisionSignal): Promise<void>;
}

export interface LayerFeedbackSidecarStore {
  append(signal: LayerAwareFeedbackSignal): Promise<void>;
}

function assertSignal(signal: SelfSupervisionSignal): void {
  if (signal.optimizationReady !== false) {
    throw new Error("Phase-1 sidecar rejects optimizationReady=true");
  }
  if (!Number.isFinite(signal.confidence) || signal.confidence < 0 || signal.confidence > 1) {
    throw new Error("Signal confidence must be within [0,1]");
  }
  if (signal.decision === "emit" && !signal.targetMemoryId) {
    throw new Error("Emitted signal requires targetMemoryId");
  }
  if (signal.decision === "abstain" && signal.targetMemoryId !== null) {
    throw new Error("Abstained signal cannot carry targetMemoryId");
  }
}

function assertLayerSignal(signal: LayerAwareFeedbackSignal): void {
  if (signal.schemaVersion !== "tdai-layer-feedback-signal.v2") {
    throw new Error("Unsupported layer feedback signal schema");
  }
  if (signal.optimizationReady !== false) throw new Error("Shadow sidecar rejects optimizationReady=true");
  if (!Number.isFinite(signal.confidence) || signal.confidence < 0 || signal.confidence > 1) {
    throw new Error("Signal confidence must be within [0,1]");
  }
  if (!(["supported", "refuted", "expired", "unverifiable"] as unknown[]).includes(signal.validity)) {
    throw new Error("Unknown Memory validity");
  }
  if (!(["helpful", "harmful", "redundant", "untested"] as unknown[]).includes(signal.utility)) {
    throw new Error("Unknown Memory utility");
  }
  if (!("identifiabilityCertificate" in signal)) {
    throw new Error("Layer signal must explicitly carry identifiabilityCertificate");
  }
  if (!([
    "memory_content", "derivation", "retrieval", "use", "model", "tool", "environment", "unknown",
  ] as unknown[]).includes(signal.failureOwner)) {
    throw new Error("Unknown failure owner");
  }
  if (signal.decision === "emit") {
    if (!signal.target) throw new Error("Emitted signal requires a target");
    if (!signal.identifiabilityCertificate) {
      throw new Error("Emitted signal requires a complete-tuple identifiability certificate");
    }
    assertCertificateIdentifiesTuple(signal.identifiabilityCertificate, {
      target: signal.target,
      faultType: signal.faultType,
      suggestedAction: signal.suggestedAction,
    });
  }
  if (signal.decision === "abstain") {
    if (signal.target !== null) throw new Error("Abstained signal cannot carry a target");
    if (signal.supportingIds.length > 0) throw new Error("Abstained signal cannot carry supporting IDs");
    if (signal.suggestedAction !== "no_action") throw new Error("Abstained signal must use no_action");
  }
  const nonMemoryOwner = signal.failureOwner === "model"
    || signal.failureOwner === "tool"
    || signal.failureOwner === "environment";
  if ((signal.faultType === "environment_or_model_failure" || nonMemoryOwner) && signal.target !== null) {
    throw new Error("Non-Memory failure cannot carry a Memory target");
  }
  if (signal.faultType === "task_harmful" && signal.utility !== "harmful") {
    throw new Error("task_harmful requires utility=harmful");
  }
  if ((signal.faultType === "task_harmful" || signal.utility === "harmful")
    && signal.replayStatus !== "replay_verified") {
    throw new Error("Harmful utility requires replay_verified evidence");
  }
  if (signal.utility === "harmful" && !signal.evidence.some((item) => item.kind === "task_intervention")) {
    throw new Error("Harmful utility requires task_intervention evidence");
  }
}

export class InMemoryFeedbackSidecarStore implements FeedbackSidecarStore {
  readonly signals: SelfSupervisionSignal[] = [];

  async append(signal: SelfSupervisionSignal): Promise<void> {
    assertSignal(signal);
    this.signals.push(structuredClone(signal));
  }
}

export class JsonlFeedbackSidecarStore implements FeedbackSidecarStore {
  readonly filePath: string;

  constructor(rootDirectory: string, fileName = "feedback-signals.v1.jsonl") {
    if (!rootDirectory.trim()) throw new Error("Sidecar root directory is required");
    if (!/^[a-zA-Z0-9._-]+\.jsonl$/.test(fileName)) {
      throw new Error("Sidecar filename must be a plain .jsonl basename");
    }
    mkdirSync(rootDirectory, { recursive: true });
    this.filePath = resolve(rootDirectory, fileName);
  }

  async append(signal: SelfSupervisionSignal): Promise<void> {
    assertSignal(signal);
    appendFileSync(this.filePath, `${JSON.stringify(signal)}\n`, { encoding: "utf8", mode: 0o600 });
  }

  readAll(): SelfSupervisionSignal[] {
    let text: string;
    try {
      text = readFileSync(this.filePath, "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
    return text.split("\n").filter(Boolean).map((line, index) => {
      try {
        const signal = JSON.parse(line) as SelfSupervisionSignal;
        assertSignal(signal);
        return signal;
      } catch (error) {
        throw new Error(`Malformed sidecar row ${index + 1}: ${(error as Error).message}`);
      }
    });
  }
}

export class InMemoryLayerFeedbackSidecarStore implements LayerFeedbackSidecarStore {
  readonly signals: LayerAwareFeedbackSignal[] = [];

  async append(signal: LayerAwareFeedbackSignal): Promise<void> {
    assertLayerSignal(signal);
    this.signals.push(structuredClone(signal));
  }
}

export class JsonlLayerFeedbackSidecarStore implements LayerFeedbackSidecarStore {
  readonly filePath: string;

  constructor(rootDirectory: string, fileName = "layer-feedback-signals.v2.jsonl") {
    if (!rootDirectory.trim()) throw new Error("Sidecar root directory is required");
    if (!/^[a-zA-Z0-9._-]+\.jsonl$/.test(fileName)) {
      throw new Error("Sidecar filename must be a plain .jsonl basename");
    }
    mkdirSync(rootDirectory, { recursive: true, mode: 0o700 });
    this.filePath = resolve(rootDirectory, fileName);
  }

  async append(signal: LayerAwareFeedbackSignal): Promise<void> {
    assertLayerSignal(signal);
    appendFileSync(this.filePath, `${JSON.stringify(signal)}\n`, { encoding: "utf8", mode: 0o600 });
  }

  readAll(): LayerAwareFeedbackSignal[] {
    let raw: string;
    try {
      raw = readFileSync(this.filePath, "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
    return raw.split("\n").filter(Boolean).map((line, index) => {
      try {
        const signal = JSON.parse(line) as LayerAwareFeedbackSignal;
        assertLayerSignal(signal);
        return signal;
      } catch (error) {
        throw new Error(`Malformed layer sidecar row ${index + 1}: ${(error as Error).message}`);
      }
    });
  }
}
