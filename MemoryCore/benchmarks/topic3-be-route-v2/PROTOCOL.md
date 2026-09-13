# B+E route validation protocol v2

This protocol follows [the 2026-09-14 route handoff](../B_E_ROUTE_HANDOFF_2026-09-14.md).
Its first stage finds real failures; it does not award a product pass or preselect a complex fix.

## Stage 1: failure discovery

Use previously unused repositories at commits before a reviewable GitHub issue, pull request, or
reproducible repository failure. An authored follow-up is allowed, but its relationship to the real
source must be stated. Each persistent sequence includes both a later task where a correction should
apply and a same-topic task where it must not apply. Checkers remain outside agent workspaces and
separate requested behavior from old-API compatibility (exit 0 pass, 1 requested behavior failure,
2 compatibility regression).

Run the same model, effort, instruction-discovery setting, task order and base revision in three
independent marked worktrees. The development manifest disables automatic project-document and native
memory discovery in every arm so only the declared repository and B+E context differ:

- `no_history`: code from the current request and repository only;
- `raw_full`: current product behavior when observations were recorded without compilation;
- `raw_top8`: exact raw observations selected by deterministic BM25, with recency only breaking ties.

All task prompts and tool receipts naturally accumulate in the two raw states. The retrieval query is
the current request, action and declared paths; hidden checks and expected patches never enter it.
No constraint compiler, summary model, prepared answer, or candidate fix runs in this stage.

Development cases locate and explain failures. They are never reused as held-out evidence. A useful
failure report must distinguish missing information, retrieval miss, stale update, scope misuse,
ordinary coding failure and checker defect. If every arm passes, the task has no observed
discrimination and cannot support a memory claim.

## Stage 2: one local repair

Only after Stage 1 establishes a repeated mechanism, implement the smallest repair that directly
addresses it. Freeze the repair before constructing the held-out split. Keep `raw_full` and
`raw_top8`; add the repair as a fourth arm under the same execution conditions. Compilation or learned
rules require evidence that lossless raw approaches leave a repeated gap.

## Stage 3: isolated held-out validation

Use new project or scenario families, not more variants of development tasks. Include necessary
updates, exceptions or another directory, explicit replacement, and a same-topic no-update control.
Report every task, paired wins/losses, repeated-error rate, severe regressions, input/cached/output
tokens, reported cost, latency, context bytes and integration cost. The decision is adopt, keep
experimental, close, or change route; there is no score threshold chosen after seeing results.

An open-source comparison is optional until a local repair survives held-out validation. If used, bind
one or two directly relevant implementations to their version and license, and run them on the same
tasks and execution model. Paper numbers and previously used tasks are not comparison results.

## Runner

`failure_discovery_runner.py` implements Stage 1 and always summarizes its decision as diagnosis only.
It requires three independent clean workspaces at one declared base commit and saves prompts, raw CLI
events, checker output, workspace diffs, per-call usage and an aggregate summary. It intentionally does
not reinterpret the historical v1 four-arm protocol or its old results.
