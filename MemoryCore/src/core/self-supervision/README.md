# Multi-layer shadow observation plane

This directory is an opt-in, shadow-only boundary for zero-explicit-feedback
Memory supervision. It is intentionally not exported from `src/core/index.ts`.
The recall exposure bridge alone can be wired by the OpenClaw root when
`shadowFeedback.enabled=true`; it is default-off, writes only an isolated local
sidecar, and has no production Memory mutation surface.

## Guarantees

- Targets are versioned `L1_NODE`, `L2_NODE`, or stable `L1_L2_EDGE` identities.
- Root observations only accept production/benchmark events at `feedbackDepth=0`.
- Replay runs exactly at `feedbackDepth=1` with recall, capture, Memory writes,
  and feedback re-ingestion disabled.
- Every observation/replay/dataset row fixes `memoryIngestionAllowed=false`.
- Duplicate task/context/graph/exposure observations are not counted twice.
- Missing TDAI provenance or L2 lineage is reported, never inferred from semantic
  similarity.
- All feedback has `optimizationReady=false` in this phase.

## Data planes

```text
TDAI read-only snapshots
  -> capture-contracts.ts (opt-in prototype; no production hook)
  -> append-only shadow capture sidecar
  -> tdai-adapter.ts
  -> RootObservation
  -> LayerObservationPlane
  -> append-only shadow observation JSONL
  -> GatedCascadeLayerRouter
  -> layer-aware feedback sidecar

Frozen clean graph
  -> one declared node/edge mutation
  -> clean / corrupt / repair / unrelated negative-control replay
  -> exact structural target + causal qualification
  -> physically separate detector-view and gold-label JSONL + commit journal
```

`ground-truth.ts` calls a target "exact" only because the injector changes one
declared graph entity. It calls the target causally qualified only when an
objective oracle produces `clean pass -> corrupt fail -> repair pass` and the
negative control also passes under the same model, environment, and validator
versions. A model judge is never sufficient for qualification. The detector
view retains sanitized corrupted content for semantic localization, while clean,
repair, mutation, and target gold remain outside that view.

## Files

- `types.ts`: versioned observation, graph, target, evidence, and feedback types.
- `capture-contracts.ts`: immutable L1/L2 version snapshots, role-derived L0
  authority, pre-generation-frozen claim/edge manifests, conservative
  retrieved/exposed/used traces, and capture-completeness audit.
- `capture-sidecar.ts`: isolated append-only prototype store that rejects
  duplicate/conflicting immutable identities and has no Memory write surface.
- `recall-shadow-adapter.ts`: structured pre/post-budget L1 identities, a
  two-phase prompt exposure acknowledgement, no-match abstention facts, and a
  fail-open observer boundary. `openclaw-recall-turn-bridge.ts` binds the
  optional draft to `before_prompt_build` and acknowledges exact context at
  `llm_input` when explicitly enabled. It records exposure, not task utility.
- `l0-l1-shadow-adapter.ts`: disabled-by-default passive bridge for acknowledged
  L0/L1 JSONL writes. It preserves persisted roles/source IDs and records explicit
  unresolved audits for version-zero, missing logical ID/receipt/span/lineage;
  producer observer failures never affect the user task.
- `l2-staged-shadow-adapter.ts`: disabled-by-default three-phase single-output
  L2 protocol. It freezes exact L1 inputs, validates complete claim lineage and
  accepts a snapshot/manifest only after a configured backend-bound authority
  verifies the committed positive version.
- `profile-commit-conformance.ts`: isolated in-memory executable specification
  for typed CAS/idempotency/fault/receipt behavior; it is explicitly non-durable.
- `profile-commit-sqlite-reference.ts`: isolated transactional SQLite reference
  with immutable operation/version/read journals and close/reopen readback. It
  is not a TCVDB adapter or a production Memory store.
- `CAPTURE_INTEGRATION.md`: current L0/L1/L2/recall path audit, missing
  associations, and passive integration points. Only the default-off recall
  exposure tap has root wiring.
- `observation-plane.ts`: graph validation, dedupe, append-only stores, and the
  non-recursive replay guard.
- `tdai-adapter.ts`: read-only conversion from current L0/L1/Profile records.
- `ground-truth.ts`: deterministic single-fault injection and split view/label
dataset writer.
- `layer-router.ts`: structure -> local ranker -> optional strong judge -> replay
  -> calibrated emit/abstain cascade.
- `layer-signal.ts` and `sidecar-store.ts`: fail-closed feedback construction and
  storage.
- `shadow-replay.ts`: Full/Mask-all/Mask-i/Replace-i/negative-control execution
  under one immutable safety-bound snapshot.

## Validation

From the `MemoryCore` root:

```bash
./node_modules/.bin/vitest run src/core/self-supervision
./node_modules/.bin/tsc -p benchmarks/pivot-memory-stale/tsconfig.json
npm run build:plugin
```
