# Lossless full-raw replication v5 protocol

Date: 2026-09-14. Frozen before any v5 model call. v4 supplied the first admissible project-family
signal; v5 tests whether that signal repeats. The closed top-8 candidate is deliberately absent.

## Frozen inputs and execution

- Manifest SHA-256: `86b275635b621fb306045cba769cc075d137ec8fc01a980d741dbe8adbc3edf0`
  at `.local-evidence/project-agent-route-v2-heldout-v5/manifest.json`.
- Checker SHA-256: `56c4789ab1fd35cf9dce3db78c4a598dd930bbd5a9171bc56424d572f3dbd3b3`.
- Backend: Codex `gpt-5.6-sol`, medium effort, ephemeral, controlled instruction discovery,
  `web_search="disabled"`, 300-second timeout.
- Arms: `no_history` and lossless `raw_full`, rotating order, two sequential tasks per project;
  16 calls total.

Every call retains v4's two isolation layers. `bwrap` hides the benchmark checkout, results, checker,
and sibling arm while exposing only the current independent clone. The model tool configuration
explicitly disables web search. A missing isolation receipt, forbidden path, or web-search event stops
and invalidates the entire matrix.

All eight workspaces contain exactly the declared base and ownership marker, have no remote, and
cannot resolve the reviewed fix commit. Each full-raw history has 12 exact user observations and the
accepted decision is present; rendered contexts are 1,913--2,023 bytes. No retrieval or compilation
runs in this replication.

## New project families

- [Websockets PR #1758](https://github.com/python-websockets/websockets/pull/1758): accept valid
  obs-text in the legacy HTTP parser through surrogate escapes without relaxing raw control-byte
  validation.
- [jsonschema PR #1300](https://github.com/python-jsonschema/jsonschema/pull/1300): choose the most
  relevant error inside each separate anyOf/oneOf subschema before cross-branch descent; retain the
  parent on a true tie.
- [Scrapy PR #8113](https://github.com/scrapy/scrapy/pull/8113): updating an existing bounded-cache
  key must not evict another entry; a later new key must still evict the oldest.
- [wsproto PR #202](https://github.com/python-hyper/wsproto/pull/202): make the remote-error event hint
  required while preserving explicit hints and local errors.

Pydantic #13792 was considered before freeze and rejected because its accepted change crosses the
Rust pydantic-core build, which this environment could not check faithfully. Aiohttp #13480 was also
inspected but not selected because its complete FileResponse path requires a broader optional
dependency stack. Neither is in the manifest and no model saw either task.

## Behavior-checker preflight

All four bases pass compatibility and fail target behavior. Both stages pass on the reviewed heads
and on separately authored alternatives: indirect insecure header insertion, dictionary-based
per-subschema grouping, an early existing-key update branch, and a required constructor parameter.
The Websockets checker loads the repository parser with a minimal Headers contract because the current
host Python predates that repository's runtime floor; it still executes the parser's byte validation,
decode, and insertion behavior. It does not inspect source text.

## Frozen interpretation

Count project families, not task rows. Each first task tests the necessary decision. Each second task
checks the accumulated implementation and scope; a second failure caused by an unfixed first task is
not another independent loss or win.

- If full raw supplies the correct necessary decision in at least one new family and causes no
  family-level regression, the v4 mechanism has one independent replication and may enter broader
  public quality comparison.
- If all four families tie, retain full raw as experimental and do not upgrade the v4 single-family
  signal.
- If full raw loses a family, classify source, scope, staleness, or execution cause before any product
  expansion; do not hide the loss in task aggregation.

Report all calls, usage, context bytes, wall time, severe regressions, and exact failure mechanisms.
One call per cell is not a stable latency estimate. No outcome in v5 authorizes compilation, learned
selection, top-8 tuning, production enablement, or an open-source superiority claim.
