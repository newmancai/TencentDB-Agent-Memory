# Filesystem-isolated held-out v3 protocol (invalidated)

Date: 2026-09-14. This was frozen before any v3 matrix model call, then invalidated during the first
call because Codex used its native web-search tool. No receipt was written and no v3 result is
admissible. See [the v3 invalidation review](HELDOUT_V3_INVALID_REVIEW.md). The two earlier held-out
attempts also remain excluded: v1 used a source-spelling checker and v2 allowed cross-arm filesystem
reads.

## Frozen inputs and isolation

- Manifest SHA-256: `86029cf87066c659f53f818b4d27b55c0756b68701535d8ab9346b1bb7229b06`
  at `.local-evidence/project-agent-route-v2-heldout-v3/manifest.json`.
- Checker SHA-256: `11c5685d338c30822b51e27e7bf89bd44f1df5bc888af527c844657fa1eed88a`.
- Backend: Codex `gpt-5.6-sol`, medium effort, ephemeral, controlled instruction discovery, 300-second
  per-call timeout.
- Arms: `no_history`, lossless `raw_full`, and exact raw BM25 `raw_top8`; rotating order, two
  sequential tasks per project.

Every model call was intended to use the route runner's outer `bwrap` view. The whole research checkout,
benchmark code, results, and sibling clones are hidden; only the current independent clone is
writable and visible. Each receipt must say `filesystem_isolated=true`. Raw events are scanned after
every call for the main checkout, output directory, or another workspace; any hit invalidates and
stops the full matrix.

All 12 workspaces have one reachable declared base commit, no remote, no tracked or untracked change
other than the ownership marker, and none of the listed post-review commits resolves.

## New project families

- [pytest PR #14910](https://github.com/pytest-dev/pytest/pull/14910): failed `MonkeyPatch` mutations
  must not register stale undo actions; successful undo and missing-key policy are the control.
- [packaging PR #1392](https://github.com/pypa/packaging/pull/1392): unbounded range ends have one
  inclusive spelling; bounded inclusive ordering is the control.
- [Flask PR #6096](https://github.com/pallets/flask/pull/6096): bracketed IPv6 authority parsing for
  server defaults and session cookie hosts; ordinary hostname and port-zero behavior are the control.
- [h11 PR #181](https://github.com/python-hyper/h11/pull/181): reject a Content-Length over 20 digits;
  the 20-digit boundary and chunked framing are the control.

Black #5312 was considered during preparation but rejected before freezing because the available
environment could not run its current parser dependency stack. It is not part of the manifest and no
model saw it.

## Checker and retrieval preflight

For every included project, the stage-one checker passes compatibility and fails requested behavior
on the base. Both stages pass on the real reviewed head and on a separately authored equivalent
implementation: explicit `try/else` mutation commits, conditional range-state assignment,
intermediate URL parsing, and a helper-based framing limit. Checkers execute behavior rather than
requiring upstream patch text.

The raw-top-8 preflight selected the exact accepted decision in every project. Selected orders were
pytest `[1,5,7,8,9,10,11,12]`, packaging `[1,2,3,5,7,10,11,12]`, Flask
`[1,5,7,8,9,10,11,12]`, and h11 `[1,2,3,5,9,10,11,12]`; rendered contexts were 1,363--1,415
bytes. This is retrieval wiring validation, not model quality evidence.

## Frozen reading and decision

Primary quality is `raw_top8` versus `raw_full` on all eight tasks. Any top-8 quality loss, retrieval
miss, visibility violation, or severe regression blocks adoption. If quality ties, compare total and
uncached input, output, reasoning output, context bytes, and wall time. `no_history` is secondary and
tests whether project history changes completion, correctness, or work.

This decision rule was never reached. The first pytest call used model-side web search and was
stopped before a receipt; packaging and Flask were not exposed, while h11 was later consumed by a
negative search-disable preflight. Report no partial v3 score.

Had isolation held, the complete 24-call matrix would have been required, including timeouts and
missing usage. A clean no-loss efficiency
result permits a pilot only; it does not set a product default. Promotion still requires a fresh
replication or a second backend under the same filesystem isolation. A quality loss closes this
raw-top-8 candidate without post-held-out tuning.
