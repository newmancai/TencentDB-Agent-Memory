# Frozen four-project held-out protocol

Date: 2026-09-14. This protocol was frozen before any held-out model call. It tests the only repeated
development signal: whether exact raw BM25 top-8 keeps task quality while reducing the cost of full
raw project history. It does not test a compiler, learned selector, or open-source memory framework.

## Isolation and sources

The manifest SHA-256 is
`9bc6f2033be1f3e7baaee80cbf5b577d2e18f07ce1ff1059336323df744ffe67` at
`.local-evidence/project-agent-route-v2-heldout/manifest.json`. It contains four project families not
used in the two valid development matrices:

- [Click PR #3451](https://github.com/pallets/click/pull/3451): accepted type-alias visibility name;
- [HTTP Core PR #1030](https://github.com/encode/httpcore/pull/1030): explicit 3.13 versus floating 3.x;
- [attrs PR #1530](https://github.com/python-attrs/attrs/pull/1530): Python 3.15 pre-release message scope;
- [MarkupSafe PR #507](https://github.com/pallets/markupsafe/pull/507): free-threading maturity classifier.

Each cluster has one necessary update grounded in the real review and one explicitly authored later
override. The override tests that earlier same-topic history does not beat the current request. All 12
workspaces have one reachable base commit, no remote, and cannot resolve their named post-review
commit. External checkers pass on each post-review revision and fail the requested behavior while
passing compatibility on each held-out base. Checker stage 2 was also validated with an explicit
local transformation before freezing.

## Fixed execution

Use Codex `gpt-5.6-sol`, medium effort, controlled instruction discovery, a 300-second call timeout,
the same persistent two-step order, and the route-v2 runner's rotating arm order. The three arms are:

- `no_history`: ordinary repository and current request;
- `raw_full`: every exact recorded user observation;
- `raw_top8`: deterministic BM25 top-8 over exact user observations, with recency only breaking ties.

The runner stores raw agent/checker output, usage, context selections, diffs, and wall time. No hidden
checker, expected patch, post-review object, project instructions, native auto-memory, or prepared
answer is available to the coding agent.

## Pre-registered reading

Quality is primary. Report all eight paired task outcomes, necessary-update and override outcomes,
severe regressions, execution failures, and retrieval misses. Do not report a score from only the
tasks where memory wins. A top-8 loss against full raw blocks adoption regardless of aggregate cost.

If top-8 has no quality loss or severe regression, compare its total and uncached input, output,
reasoning output, context bytes, and wall time with full raw. A consistent aggregate saving keeps
top-8 as the simplest product candidate; a negligible or reversed saving closes it. The no-history
comparison measures whether prior decisions reduce work, but it is secondary to the paired
top-8-versus-full decision.

This one held-out matrix can justify a product pilot, not a stable universal claim. Promotion to a
default still requires a fresh replication and at least one second backend or materially different
task family. No threshold will be tuned after seeing the held-out rows.
