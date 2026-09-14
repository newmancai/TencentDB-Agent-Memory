# Project-memory runtime optimization protocol

Date: 2026-09-14. Protocol ID: `project-memory-runtime-optimization-v2`.

## Question and arms

Can the installed CLI remove TypeScript-loader and bridge-process overhead without changing its project
memory context or state?

- `source_tsx_two_call`: source `store.ts`, with `loadContext → ingest` in two Node processes.
- `precompiled_two_call`: the same operations through the package's precompiled bridge.
- `precompiled_one_shot`: precompiled `prepareRun` in one process. It loads context first, assigns the next
  task order, then invokes the existing `ProjectMemory.ingest`; it does not duplicate selection or
  persistence policy outside MemoryCore.

All arms start from separate identical SQLite states. Twenty rotating matched triplets use the same owner,
project, paths, action, 12,000-byte budget, task IDs/text, initial observations, and compiled constraint.
No model is called.

## Adoption rule

Promote the final path only if every rendered context and final snapshot is byte-equivalent, each arm
follows its declared operation sequence, and final aggregate and p95 wall time are below the source/tsx
two-call baseline. A source checkout without a built bundle retains the `tsx` fallback. A task-write error
must be returned with the successfully loaded context rather than reported as success.

The measurement covers local Python-to-Node startup plus SQLite context/task work on one machine. It is
not an end-to-end coding latency, token-cost, network, or production-SLO result.
