# Project-memory runtime optimization results

Date: 2026-09-14. Protocol: `PROJECT_MEMORY_RUNTIME_PROTOCOL.md`. Machine-readable summary:
`project-memory-runtime-optimization-results.json`. Raw evidence SHA-256:
`4c15b6d028c681e8a627ad14920d0bf945f0ba4845823c8da85793d3e8828c7f`.

## Outcome

Promote the final local runtime path and stop further infra expansion:

1. The installed CLI uses the package's precompiled `project-agent-store.mjs`; a source checkout falls
   back to `tsx` when no build exists.
2. Normal `run` uses one `prepareRun` bridge process to load the exact pre-task snapshot and selection,
   assign the next task order, and call the existing durable `ProjectMemory.ingest`.

| 20 rotating matched triplets | Processes | Mean | p50 | p95 |
| --- | ---: | ---: | ---: | ---: |
| Source `tsx`, two calls | 2 | 0.454 s | 0.457 s | 0.472 s |
| Precompiled, two calls | 2 | 0.323 s | 0.329 s | 0.336 s |
| Precompiled, one-shot | **1** | **0.245 s** | **0.245 s** | **0.253 s** |

Precompilation reduced the paired mean by **28.8%** and p95 by **28.9%**. One-shot then reduced the
precompiled paired mean by **24.4%** and p95 by **24.7%**. Directly within the same matched triplets, the
final path reduced mean by **46.1%** and p95 by **46.5%** relative to the prior source/`tsx` two-call path.
Every rendered context and final SQLite snapshot was byte-equivalent. Together with the earlier four-to-two
consolidation, the normal model-preparation path has structurally moved from four processes to one, a
**75% process-count reduction**. The older and current timing runs are not combined into a cross-run SLO.

## Architecture and failure behavior

`prepareRun` is bridge orchestration only: it invokes the existing `loadContext` and `ProjectMemory.ingest`;
selection, lineage, capacity, validation, and persistence remain in MemoryCore. The post-model tool receipt
remains a separate durable write.

The first one-shot run correctly failed exact equivalence: spreading the pending task object appended
`order` after `role` and `text`. Although the objects were semantically equal, raw fallback JSON is
prompt-visible, so key order is part of the byte contract. The failed evidence was retained. The bridge now
constructs `id → order → role → text` explicitly; the consolidated 20-triplet protocol then passed.

Task-write failure behavior is retained: once context loading succeeds, `prepareRun` returns that context
together with the ingest error. The agent may continue from the loaded context while
`task_persisted=false`; no failed write is reported as successful.

## Boundary and stop decision

The benchmark makes zero model calls and measures local Python-to-Node startup plus SQLite context/task
work on this machine. It does not measure token cost, model/network latency, checker time, or production
p95. B+E quality scores are unchanged. Further worker lifecycle or database redesign is stopped because
the high-yield process-launch reductions are complete and added complexity is no longer justified by the
current evidence.
