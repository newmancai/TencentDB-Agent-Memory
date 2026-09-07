import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  assertShadowCaptureEvent,
  captureEventIdentity,
  captureEventIntegrityDigest,
  type ShadowCaptureEvent,
} from "./capture-contracts.js";

export interface ShadowCaptureSidecarStore {
  append(event: ShadowCaptureEvent): Promise<void>;
  appendBatch(events: ShadowCaptureEvent[]): Promise<void>;
}

function frozenClone<T>(value: T): T {
  const clone = structuredClone(value);
  const freeze = (entry: unknown): void => {
    if (!entry || typeof entry !== "object" || Object.isFrozen(entry)) return;
    for (const child of Object.values(entry as Record<string, unknown>)) freeze(child);
    Object.freeze(entry);
  };
  freeze(clone);
  return clone;
}

function validateBatch(
  events: ShadowCaptureEvent[],
  known: ReadonlyMap<string, string>,
): Map<string, string> {
  if (events.length === 0) throw new Error("Capture sidecar batch must not be empty");
  const pending = new Map<string, string>();
  for (const event of events) {
    assertShadowCaptureEvent(event);
    const identity = captureEventIdentity(event);
    const integrityDigest = captureEventIntegrityDigest(event);
    const existing = pending.get(identity) ?? known.get(identity);
    if (existing === integrityDigest) throw new Error(`Duplicate capture event ${identity}`);
    if (existing !== undefined) throw new Error(`Immutable capture identity conflict ${identity}`);
    pending.set(identity, integrityDigest);
  }
  return pending;
}

/** In-memory test/prototype store. It has no production Memory write surface. */
export class InMemoryShadowCaptureSidecarStore implements ShadowCaptureSidecarStore {
  readonly events: ShadowCaptureEvent[] = [];
  private readonly identities = new Map<string, string>();

  async append(event: ShadowCaptureEvent): Promise<void> {
    await this.appendBatch([event]);
  }

  async appendBatch(events: ShadowCaptureEvent[]): Promise<void> {
    const pending = validateBatch(events, this.identities);
    this.events.push(...events.map(frozenClone));
    for (const [identity, eventHash] of pending) this.identities.set(identity, eventHash);
  }
}

/**
 * Append-only JSONL sidecar. A batch is validated in full and emitted through a
 * single append call. This is deliberately separate from every IMemoryStore and
 * cannot update L0/L1/Profile state.
 */
export class JsonlShadowCaptureSidecarStore implements ShadowCaptureSidecarStore {
  readonly filePath: string;
  private readonly identities = new Map<string, string>();

  constructor(rootDirectory: string, fileName = "capture-events.v1.jsonl") {
    if (!rootDirectory.trim()) throw new Error("Capture sidecar root directory is required");
    if (!/^[a-zA-Z0-9._-]+\.jsonl$/.test(fileName)) {
      throw new Error("Capture sidecar filename must be a plain .jsonl basename");
    }
    mkdirSync(rootDirectory, { recursive: true, mode: 0o700 });
    this.filePath = resolve(rootDirectory, fileName);
    this.load().forEach((event) => {
      const identity = captureEventIdentity(event);
      const integrityDigest = captureEventIntegrityDigest(event);
      const existing = this.identities.get(identity);
      if (existing === integrityDigest) throw new Error(`Duplicate capture event ${identity}`);
      if (existing !== undefined) throw new Error(`Immutable capture identity conflict ${identity}`);
      this.identities.set(identity, integrityDigest);
    });
  }

  async append(event: ShadowCaptureEvent): Promise<void> {
    await this.appendBatch([event]);
  }

  async appendBatch(events: ShadowCaptureEvent[]): Promise<void> {
    const pending = validateBatch(events, this.identities);
    const payload = events.map((event) => JSON.stringify(event)).join("\n") + "\n";
    appendFileSync(this.filePath, payload, { encoding: "utf8", mode: 0o600 });
    for (const [identity, eventHash] of pending) this.identities.set(identity, eventHash);
  }

  readAll(): ShadowCaptureEvent[] {
    return this.load().map(frozenClone);
  }

  private load(): ShadowCaptureEvent[] {
    let raw: string;
    try {
      raw = readFileSync(this.filePath, "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
    return raw.split("\n").filter(Boolean).map((line, index) => {
      try {
        const event = JSON.parse(line) as ShadowCaptureEvent;
        assertShadowCaptureEvent(event);
        return event;
      } catch (error) {
        throw new Error(`Malformed capture sidecar row ${index + 1}: ${(error as Error).message}`);
      }
    });
  }
}
