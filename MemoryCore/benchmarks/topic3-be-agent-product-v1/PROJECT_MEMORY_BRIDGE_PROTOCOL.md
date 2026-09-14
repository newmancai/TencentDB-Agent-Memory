# Project-memory bridge hot-path protocol

Date: 2026-09-14

This protocol records the first four-to-two consolidation. It remains reproducible, but the final
installed path is specified by `PROJECT_MEMORY_RUNTIME_PROTOCOL.md`.

## Objective

Reduce fixed local orchestration latency without changing the B+E prompt, stored observations,
constraints, scope selection, fallback behavior, model, or checker. Before this change a normal scoped
`run` with compiled constraints used four pre-model Python-to-Node bridge processes:

1. read the snapshot for rendering;
2. select scoped context;
3. read the same snapshot again to assign the next order;
4. ingest the current task.

The candidate `loadContext` bridge operation returns the pre-task snapshot and its scoped selection from
one Node process. The host reuses that exact snapshot to assign the next observation order, then performs
the existing ingest. This makes two pre-model bridge processes. Receipt persistence after the model stays
a separate durable write and is not hidden from the count.

## Frozen local benchmark

Run 20 paired iterations on two independently seeded SQLite states with identical owner, project,
observations, constraint, task IDs, task text, scope, action, and 12,000-byte budget. The legacy arm
executes `snapshot → context → snapshot → ingest`; the candidate executes `loadContext → ingest`.
Alternate which arm runs first on every iteration. Do not call a model.

The benchmark must retain every per-iteration wall time and bridge operation sequence, and must reject the
result unless every rendered context and the final snapshots are exactly equal. Promotion requires:

- exact context and final-state equality;
- four to two pre-model bridge operations;
- lower aggregate and p95 paired local wall time;
- project-agent unit tests, formatting, and the native TypeScript suite pass.

These timings measure this machine's process/SQLite bridge only. They are not an end-to-end agent SLO,
model latency, token reduction, or a claim about another deployment topology.

## Outcome

All promotion gates passed. Across 20 paired iterations, pre-model bridge calls fell from 4 to 2, mean
wall time from `0.680 s` to `0.424 s`, and p95 from `0.736 s` to `0.476 s`; every context and the final
snapshots were exactly equal. See `PROJECT_MEMORY_BRIDGE_RESULTS.md`.
