# Web-disabled, filesystem-isolated held-out v4 protocol

Date: 2026-09-14. Frozen before any v4 matrix model call. Earlier held-out attempts remain excluded:
v1 used a source-spelling checker, v2 allowed cross-arm filesystem reads, and v3 allowed model-side
web search.

## Frozen inputs and isolation

- Manifest SHA-256: `7038fc0ee481c7ffcb22261d0eebd5ac31cd0c08c72f7c2b162a0d48c08d34c9`
  at `.local-evidence/project-agent-route-v2-heldout-v4/manifest.json`.
- Checker SHA-256: `205122a5525089f22d63cd068622f886b98251a99f882020d1c8906387e466c3`.
- Backend: Codex `gpt-5.6-sol`, medium effort, ephemeral, controlled instruction discovery, explicit
  `web_search="disabled"`, 300-second per-call timeout.
- Arms: `no_history`, lossless `raw_full`, and exact raw BM25 `raw_top8`; rotating order, two
  sequential tasks per project.

Every call must run inside the outer `bwrap` view. The research checkout, benchmark sources,
evidence, and sibling clones are hidden; only the current independent clone is writable and visible.
The temporary Codex home contains the authentication file but not user configuration. Each receipt
must say `filesystem_isolated=true`. Raw events are scanned for forbidden paths and any `web_search`
event; either condition stops and invalidates the full matrix.

A real negative preflight in an already exposed h11 clone explicitly demanded web lookup and returned
`SEARCH_DISABLED` without a web event. Twenty project-agent and two route-runner tests pass. These are
infrastructure checks, not result rows.

All 12 v4 workspaces contain one reachable declared base commit, no remote, and no change other than
the ownership marker. None can resolve a declared reviewed fix commit. Packaging and Flask use new
clones of the v3 bases; no v3 model call reached either family. pytest and h11 are not reused.

## Project families

- [packaging PR #1392](https://github.com/pypa/packaging/pull/1392): canonicalize unbounded range
  ends while preserving bounded inclusive ordering.
- [Flask PR #6096](https://github.com/pallets/flask/pull/6096): parse bracketed IPv6 authorities for
  development-server defaults and session cookie hosts, with hostname and port-zero controls.
- [tqdm PR #1830](https://github.com/tqdm/tqdm/pull/1830): concurrent maps accept inputs whose length
  is entirely unknown, without consuming generators; a sized companion remains the control.
- [Uvicorn PR #3107](https://github.com/Kludex/uvicorn/pull/3107): h11 clears an armed keep-alive timer
  before a buffered WebSocket upgrade; ordinary pipelined HTTP timing is the control.

## Checker and retrieval preflight

For all four projects, stage one passes compatibility and fails requested behavior on the base. Both
stages pass on the reviewed head and on a separately authored implementation: conditional range
normalization, intermediate URL parsing, an explicit known-length list and fallback, and inline h11
timer cancellation. The checker executes behavior and accepts these forms rather than matching the
upstream diff.

Raw top-8 selected each accepted decision. Selected orders were packaging
`[1,2,3,5,7,10,11,12]`, Flask `[1,5,7,8,9,10,11,12]`, tqdm
`[1,2,6,8,9,10,11,12]`, and Uvicorn `[1,2,3,5,7,8,11,12]`. Rendered contexts were
1,363--1,408 bytes. This validates retrieval wiring only.

## Frozen reading and decision

Primary quality is `raw_top8` versus `raw_full` on all eight tasks. Any top-8 quality loss,
retrieval miss, visibility violation, or severe regression blocks adoption. If quality ties, compare
total and uncached input, output, reasoning output, context bytes, and wall time. `no_history` remains
secondary evidence about whether project history changes correctness or work.

Report all 24 calls, including timeout and missing usage. A clean no-loss efficiency result supports
only a pilot; it does not prove memory quality or set a product default. Promotion still requires a
fresh replication or second backend under the same two isolation layers. A quality loss closes this
raw-top-8 candidate without tuning on v4.
