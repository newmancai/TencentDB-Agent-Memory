# Shadow capture contracts and integration audit

Status: opt-in prototype only. `l0-recorder.ts` and `l1-writer.ts` expose passive
write-result observers, but no production hook constructs or registers those
capture adapters and they are not exported from `src/core/index.ts`. The recall
exposure adapter is the one exception: OpenClaw can construct it when
`shadowFeedback.enabled=true`, join `before_prompt_build` to `llm_input`, and
append exact-context observations to an isolated sidecar. Initialization and
delivery are fail-open for the user task; none of these adapters has an
`IMemoryStore`/`StorageAdapter` write reference.

`l2-staged-shadow-adapter.ts` now provides a default-off three-phase contract for
one structured L2 create/update. It is exported only from the internal
`self-supervision/index.ts`, has no production writer reference, and is not wired
to `SceneExtractor` or profile sync. A public receipt digest is never sufficient:
an enabled run also requires a configured storage authority to verify the exact
committed row and its run/stage/baseline/commit-revision binding.

## What the prototype captures

`capture-contracts.ts` adds four append-only event contracts:

1. `VersionedMemoryRecord` materializes one exact positive L1/L2 version,
   including logical identity, content, metadata, scope, entity bindings, L0
   source refs, predecessor refs, and a persistence receipt. A second payload
   for the same `(layer, record_id, version)` must have the same immutable
   `recordDigest`.
2. `MaterializedL0Authority` stores the persisted L0 text and exact UTF-16
   source spans. The implementation derives authority from the persisted role:
   `user -> user_assertion`, while `assistant -> assistant_generated_output` and
   is never eligible as user-fact authority.
3. `AggregationManifest` embeds an input set frozen before generation and maps
   every materialized L2 claim to exact L1 versions and independently versioned
   L1-to-L2 edges. It records declared provenance, not semantic correctness.
4. `MemoryUseTrace` records a retrieval access first, then an optional exposure,
   then optional use. Use requires an explicit citation, tool-argument dependency,
   or deterministic data-flow observation. Injection or task outcome alone never
   becomes `used`.

All events are content-addressed, deeply frozen by their builders, JSON-only,
and fixed to:

```text
feedbackDepth=0
memoryIngestionAllowed=false
mayWriteProductionMemory=false
mayEnqueueFeedback=false
feedbackReingestionEnabled=false
optimizationReady=false
```

Only `production_capture` and `benchmark_fixture` are legal roots. Replay or
self-supervision output is rejected at runtime. `capture-sidecar.ts` provides an
in-memory store and an isolated append-only JSONL store; neither implements or
imports a production Memory write surface.

`auditCaptureCompleteness()` checks whether a packet has enough addressable
evidence for a later, separately generated canary localization label. A passing
audit does **not** assert that Memory content is true and does not itself create
gold.

## Current path audit

| Path | Existing observable facts | Exact-capture blocker | Passive tap point for a future integration |
|---|---|---|---|
| L0 recorder/store | Stable message ID, persisted role/text/time and isolation dimensions; successful JSONL append now yields an application receipt labelled `append_resolved` | L1 source spans are not persisted or checked against role/text at commit time; the v1 auto-capture vector ID may differ from the JSONL message ID | The opt-in passive observer materializes only an acknowledged JSONL payload and derives authority from its persisted role; missing receipts become unresolved audits |
| L1 extraction/writer | Extractor emits `source_message_ids`; JSONL `MemoryRecord` retains them; new `store` writes start at version `1`; each sink result is now observed separately | Stable logical ID and exact predecessor versions are absent; update/merge stays at version `0` when any target version cannot be resolved; JSONL/vector writes remain non-transactional | The opt-in adapter requires an acknowledged JSONL receipt, positive version and explicit logical ID. Missing fields produce no invented version/identity; missing source spans or predecessor versions stay `captured_unresolved` |
| L1 SQLite/TCVDB reader | Exact record ID, numeric version, scope and metadata | SQLite reader reconstructs `source_message_ids: []`; store schemas persist only `metadata`, and `_tdai_provenance` is not required | Restore versioned provenance from an immutable sidecar or persist it in `_tdai_provenance`; never infer missing source IDs semantically |
| L2 scene extraction | Prompt input includes L1 content, creation time and ID; pre/post scene contents are already diffed; an isolated staged contract now exists | Input versions are omitted; the LLM writes scene files directly; scene META has no stable claim IDs, lineage or edge versions; the staged contract is not hooked up | Freeze exact L1 record snapshots immediately before prompt construction; move one eligible output through the staged protocol and capture the authority-confirmed L2 version |
| Profile sync | Stable profile ID and remote optimistic version increment exist; EXP-015 now provides isolated in-memory and SQLite exact-contract references | Local/StorageAdapter enumeration sets `version: 0`; `syncProfiles()` returns `void`; TCVDB performs client query/compare then ordinary upsert and swallows conflicts/errors; rows expose no immutable operation/revision journal | Add a separate optional single-record atomic CAS+journal capability and independently read the exact committed revision. Legacy sync, `contentMd5`, mtime or a predicted version can never mint a receipt |
| L1 auto-recall | Search/fusion carries record ID, optional logical ID metadata, version, rank, score and rendered text through the prompt budget; budget-pruned rows remain retrieved-only. The default-off OpenClaw bridge supplies a per-turn task-run ID and byte-exact `llm_input` acknowledgement to an isolated sidecar | Legacy version `0`/missing logical IDs remain unresolved; ordinary chat has no objective validator or durable `(task_run, exposure, outcome)` join, so exposure cannot become utility credit | Keep host capture observation-only; objective Full/Mask credit runs in an isolated executable-task harness until a trustworthy outcome source exists |
| L2 navigation | Scene index summary/path is injected into the system context | Index entries have filename but no stable profile ID/version; navigation summary is not exposure to full L2 content | Join filename to an exact profile snapshot. Record navigation as `l2_navigation_summary`; do not label full L2 content exposed |
| L2 file read | `tdai_read_cos` reports requested path, success and size | Report lacks exact L2 ID/version/content hash and downstream use evidence | After successful read, resolve path against the same profile snapshot and record `l2_full_content` exposure. If identity resolution fails, retain tool telemetry and abstain |
| Task/use | Tool calls and task-end metrics exist | No stable `(task_run, exposure, record, version, outcome)` join; ordinary model prose does not prove use | Join by `taskRunId` and `exposureId`; mark `used` only from an allowed evidence basis. Everything else remains merely exposed |

Concrete code facts behind the blockers:

- `record/l1-writer.ts` starts new records at version `1`; update/merge uses
  `max(target versions) + 1` only after every requested target resolves, and
  otherwise persists version `0` for explicit downstream abstention.
- `record/l1-reader.ts` explicitly reconstructs `source_message_ids: []`.
- `store/sqlite.ts` defaults the L1 version column to `0` and serializes only
  `record.metadata`, not the top-level source ID field.
- `profile/profile-sync.ts::listLocalProfiles()` sets local L2 versions to `0`.
- `scene/scene-format.ts::SceneBlockMeta` contains only created, updated,
  summary and heat.
- `scene/scene-extractor.ts` freezes only a content/summary diff for its own
  metrics; its prompt omits L1 versions and has no committed claim mapping.
- `hooks/auto-recall.ts` has a default-off structured shadow draft tap. When
  explicitly enabled, the OpenClaw root now binds it to a stable per-turn ID and
  calls a row exposed only after byte-exact acknowledgement at `llm_input`.
  This still does not establish use or an objectively scored outcome.

## Proposed shadow-only integration order

1. Add receipts and positive version/logical-ID allocation to the producer
   interfaces, without changing Memory behavior. Backfill is a separate migration;
   legacy version `0` must remain explicitly unresolved.
2. Materialize role-correct L0 rows and L1 write snapshots to the sidecar. Verify
   source spans and preserve assistant-origin evidence as assistant-origin.
3. Stage L2 generation: freeze exact L1 inputs before the model call, require
   claim spans and declared source refs in structured output, allocate stable
   edge versions, then sidecar-commit manifest and acknowledged L2 snapshot as
   one validated batch.
4. Preserve structured identities through recall fusion and budgeting. Capture
   retrieved-only records separately from prompt exposures.
5. Resolve L2 navigation/read paths against exact profile versions, then add
   conservative use evidence and task-outcome joins.
6. Only after coverage auditing, construct clean canary graphs. Keep the mutation
   manifest/gold physically separate, mutate one exact node or edge, and qualify
   it with clean/corrupt/repair/unrelated-control replay.

## Still unresolved before a production shadow tap

- EXP-015 proves only an isolated contract and a transactional/close-reopen
  SQLite reference. It does not establish live TCVDB CAS, COS/profile atomicity,
  kill/power-loss durability or production integration.
- JSONL batch append is a prototype, not a cross-process transaction or lock.
- The global completeness auditor still needs causal-subgraph/origin partitioning;
  local L2/derivation readiness must not be promoted to whole-example readiness.
- Current L1 JSONL/vector dual-write and L2 file/profile sync cannot atomically
  commit content plus capture sidecar; receipts and recovery semantics are needed.
- The new L0/L1 application receipts bind exact payload bytes to a resolved append
  or truthy store return, but are not native database transaction IDs/ETags. The
  L1 adapter deliberately requires the JSONL append receipt because the current
  retrieval-store row drops top-level `source_message_ids`.
- Current L1 `store` writes start at version `1` but carry no declared logical
  ID, so the passive adapter still records an unresolved audit and emits no
  versioned L1 event unless identity is supplied explicitly. Update/merge also
  remains unresolved when the writer cannot retrieve every target version.
- Scene extraction must move from unrestricted file editing to a staged,
  manifest-aware output protocol before claim lineage is trustworthy.
- A retention, access-control and encryption policy is required because L0 and
  Memory content are materialized rather than hash-only.
- TDAI L0 currently persists only user/assistant roles; tool/system authority
  would require a separately defined source contract.
- Model-output dependence is usually latent. When citation/data-flow evidence is
  absent, the correct state is `exposed`, never guessed `used`.
- The recall hook must remain default-off and observation-only until legacy/
  unresolved version-zero prevalence, capture overhead and retention have been
  measured. It must not feed optimization without a separately validated
  objective outcome join.

## Validation

```bash
./node_modules/.bin/vitest run src/core/self-supervision/capture-contracts.test.ts
./node_modules/.bin/vitest run \
  src/core/self-supervision/profile-commit-conformance.test.ts \
  src/core/self-supervision/profile-commit-sqlite-reference.test.ts
./node_modules/.bin/vitest run src/core/self-supervision
./node_modules/.bin/tsc -p benchmarks/pivot-memory-stale/tsconfig.json --noEmit
```
