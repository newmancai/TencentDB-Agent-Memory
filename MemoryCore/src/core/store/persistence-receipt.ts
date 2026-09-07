import { createHash } from "node:crypto";

import type { MemoryPersistenceReceipt } from "./types.js";

export interface MemoryPersistenceReceiptInput {
  layer: "L0" | "L1";
  sink: MemoryPersistenceReceipt["sink"];
  acknowledgementBasis: MemoryPersistenceReceipt["acknowledgementBasis"];
  target: string;
  records: Array<{ id: string; version: number }>;
  payload: string;
  acknowledgedAt?: string;
}

/** Build an application receipt only after the caller has observed write success. */
export function createMemoryPersistenceReceipt(
  input: MemoryPersistenceReceiptInput,
): MemoryPersistenceReceipt {
  const payloadSha256 = sha256(input.payload);
  const recordIds = input.records.map((record) => record.id);
  const versions = input.records.map((record) => record.version);
  const identity = JSON.stringify({
    schemaVersion: "tdai-memory-persistence-receipt.v1",
    layer: input.layer,
    sink: input.sink,
    acknowledgementBasis: input.acknowledgementBasis,
    target: input.target,
    recordIds,
    versions,
    payloadSha256,
  });
  return {
    schemaVersion: "tdai-memory-persistence-receipt.v1",
    receiptId: `persist:${input.layer.toLowerCase()}:${sha256(identity).slice(0, 32)}`,
    layer: input.layer,
    sink: input.sink,
    acknowledgementBasis: input.acknowledgementBasis,
    target: input.target,
    recordIds,
    versions,
    payloadSha256,
    acknowledgedAt: input.acknowledgedAt ?? new Date().toISOString(),
  };
}

/** Validate both the payload commitment and the deterministic receipt identity. */
export function matchesMemoryPersistenceReceipt(
  receipt: MemoryPersistenceReceipt,
  expected: Omit<MemoryPersistenceReceiptInput, "acknowledgedAt">,
): boolean {
  if (!Number.isFinite(Date.parse(receipt.acknowledgedAt))) return false;
  const rebuilt = createMemoryPersistenceReceipt({ ...expected, acknowledgedAt: receipt.acknowledgedAt });
  return JSON.stringify(receipt) === JSON.stringify(rebuilt);
}

function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}
