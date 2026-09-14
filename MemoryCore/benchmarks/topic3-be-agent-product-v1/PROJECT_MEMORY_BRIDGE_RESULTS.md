# Project-memory bridge hot-path results

Date: 2026-09-14. Protocol: `PROJECT_MEMORY_BRIDGE_PROTOCOL.md`. Compact machine-readable result:
`project-memory-bridge-results.json`. Raw 20-pair evidence SHA-256:
`67572aa14c1c8350fee09f4286617a39ca8f3af98f98aea7721368097397bdd1`.

This is the retained first-stage result. The final installed runtime path and authoritative current
numbers are in `PROJECT_MEMORY_RUNTIME_OPTIMIZATION_RESULTS.md`.

## Outcome

Promote the `loadContext` bridge consolidation. It changes no model prompt or memory selection rule. Every
paired rendered context and the final SQLite snapshots were exactly equal, while the normal scoped
pre-model path used two bridge processes instead of four.

| 20 paired local iterations | Legacy | Optimized | Optimized / legacy |
| --- | ---: | ---: | ---: |
| Pre-model bridge calls per run | 4 | 2 | **0.500x** |
| Total wall time | 13.592 s | 8.484 s | **0.624x** |
| Mean wall time | 0.680 s | 0.424 s | **0.624x** |
| p50 wall time | 0.670 s | 0.413 s | **0.617x** |
| p95 wall time | 0.736 s | 0.476 s | **0.646x** |

The mean saves about `255 ms` per local context-load-plus-task-ingest sequence; aggregate and p95 wall
time fall about `37.6%` and `35.4%`, respectively. The order of paired arms alternated each iteration.
All legacy operation sequences were `snapshot → context → snapshot → ingest`; all optimized sequences
were `loadContext → ingest`.

## Semantics retained

- The returned snapshot is the revision before the current task is written.
- Scoped selection, budget fallback, raw fallback, unresolved original observations, and exact context
  serialization are unchanged.
- The same pre-task snapshot supplies the next monotonic order; the existing `ingest` remains the durable
  write and revalidates the state.
- A successful read followed by a failed write still exposes the loaded context and reports the write
  failure separately.
- The post-model tool receipt remains another explicit durable write; it is not folded into or omitted
  from accounting.

This benchmark makes zero model calls. It measures local Python-to-Node startup plus SQLite work on this
machine, not end-to-end coding latency, model token cost, network latency, or a production p95 SLO.
