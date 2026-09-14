# Replacement behavior-oriented held-out protocol

Date: 2026-09-14. Frozen before any v2 held-out model call. This attempted to replace the invalid
first matrix, but was itself invalidated when a later arm read earlier-arm artifacts. See
[the v2 invalidation review](HELDOUT_V2_INVALID_REVIEW.md). No result from this protocol is retained
as held-out evidence.

## Frozen inputs

Manifest SHA-256:
`dbd6f338d238d242300386f4e4373312becc802e3f7d30c753f2151ffaef9d32` at
`.local-evidence/project-agent-route-v2-heldout-v2/manifest.json`.

Four new project families are used:

- [urllib3 PR #5161](https://github.com/urllib3/urllib3/pull/5161): discard HTTP 303 body-framing state;
- [Starlette PR #3544](https://github.com/Kludex/starlette/pull/3544): preserve existing URL query serialization when appending;
- [AnyIO PR #1318](https://github.com/agronholm/anyio/pull/1318): deliver pending cancellation after shielded file close;
- [Trio PR #3456](https://github.com/python-trio/trio/pull/3456): final Python 3.15 test configuration.

Each has a necessary review update and a same-topic scope control. Every one of the 12 workspaces has
one reachable base commit, no remote, and no resolvable post-review commit. Each checker fails the
requested behavior on the base while compatibility passes.

Unlike the invalid first attempt, checkers execute public behavior or parse configuration rather
than demand an incidental patch spelling. They pass both stages on the real post-review revisions.
For urllib3, Starlette, and AnyIO they also pass manually constructed equivalent implementations:
separate header discard, intermediate query-composition variables, and an aliased cancellation
checkpoint. Trio's target is an exact dependency/configuration decision, so alternate source spelling
does not change the selected value.

## Fixed arms and reading

Run the unchanged route-v2 runner with Codex `gpt-5.6-sol`, medium effort, controlled instruction
discovery, rotating arm order, and a 300-second timeout. Compare `no_history`, `raw_full`, and exact
raw BM25 `raw_top8`; do not compile, summarize, tune retrieval, or expose external checkers.

The eight raw-top8-versus-full-raw task outcomes are primary. Any top-8 quality loss, retrieval miss,
or severe regression blocks adoption. If quality is tied, compare total and uncached input, output,
reasoning output, context bytes, and wall time. A consistent saving keeps top-8 as the simplest pilot;
a negligible or reversed saving closes it. No-history is a secondary measure of whether prior review
history reduces agent work.

Report the whole matrix, including execution failures and controls. This single replacement held-out
can justify a pilot, not a stable default; a fresh replication or second backend remains required.
