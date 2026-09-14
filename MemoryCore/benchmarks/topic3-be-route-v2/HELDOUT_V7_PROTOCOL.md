# Single-source-file lossless full-raw replication v7 protocol

Date: 2026-09-14. Frozen before any v7 model call. v6 was stopped after its first no-history call
timed out while continuing nonessential test and documentation work after the target source behavior
already passed. v7 narrows the execution unit prospectively; it does not reinterpret or rerun v6.

## Frozen inputs and execution

- Manifest SHA-256: `138dee60a71021d82d9c3a534e4b97119763c6eb50c0be2c710b612b42cfdf23`
  at `.local-evidence/project-agent-route-v2-heldout-v7/manifest.json`.
- Checker SHA-256: `34a92186e5a58a1e4829c82a08536302af43fc57666439e7897d7925f2709642`.
- Runner SHA-256: `625431dafcb6fd08f98697e6d56967889125b936942a52ad75c81139e3ecd9de`.
- Backend: Codex `gpt-5.6-sol`, medium effort, ephemeral, controlled instructions,
  `web_search="disabled"`, 300-second hard limit.
- Arms: `no_history` and lossless `raw_full`, rotated order, two sequential tasks per family;
  16 scheduled calls. Top-8 remains closed.

Each request names exactly one editable source file, forbids internet and outside-workspace search,
forbids changes to tests, docs, changelog, configuration, generated files, and asks for at most one
focused smoke check followed by immediate stop/report. This bounds the coding deliverable equally in
both arms; the checker still evaluates behavior rather than patch text.

The outer `bwrap` exposes only the current opaque `lane-a` or `lane-b` clone. All eight clones contain
the declared base plus marker, have no remote, and cannot resolve the reviewed head. Event logs are
scanned for model web search and forbidden paths. The corrected summary records execution failures as
arm-qualified `indeterminate` rows rather than memory wins.

## Families and exposure boundary

- [hpack PR #287](https://github.com/python-hyper/hpack/pull/287): empty bytes remain a perfect
  static-table match; non-empty same-name values remain literals.
- [PrettyTable PR #468](https://github.com/prettytable/prettytable/pull/468): tab expansion occurs on
  the final formatted cell string, including custom formatter output.
- [importlib_metadata PR #519](https://github.com/python/importlib_metadata/pull/519): no metadata
  source returns `None`, while PKG-INFO fallback and ordinary metadata remain parsed.
- [zipp PR #154](https://github.com/jaraco/zipp/pull/154): `Path.iterdir` on a file raises
  `NotADirectoryError`, while directory iteration remains unchanged.

The first three appeared in the frozen v6 manifest but received zero model calls before v6 stopped;
their workspaces, prompts, and histories did not occur in either v6 event log. zipp is new. The exposed
platformdirs family is absent. This reuse is explicitly about uncalled inputs, not selective reuse of
completed or favorable rows.

## Behavior-checker preflight

For all four families and both stages, the declared base returns compatibility pass / behavior fail;
the exact reviewed head and a separately authored alternative return compatibility pass / behavior
pass. Alternatives use an explicit empty-bytes branch, per-line tab expansion, direct absent-text
return, and `OSError(ENOTDIR)` respectively. Their diff hashes are retained in
`.local-evidence/project-agent-route-v2-heldout-v7/PREPARATION.json`.

Generated PrettyTable version metadata and the unavailable `wcwidth` API are replaced by the same
fixed minimal stubs used across base, reviewed head, alternative, and both arms. The checker evaluates
ASCII tab alignment only and makes no Unicode-width claim. No project dependency is installed into a
clone.

Every full-raw first task has 12 user observations with the exact accepted maintenance decision.
Second tasks add no new history and test the accumulated scope. Prompts omit implementation details.
No retrieval, compilation, local model, GPU, production path, or Gateway is used.

## Frozen interpretation

The family-level first necessary task is the independent unit; a cumulative control is not an
additional win.

- At least one completed, checkable new-family first-task split in favor of full raw, and no full-raw
  family regression, is the required Phase A replication.
- Four family ties keep full raw experimental and do not upgrade v4.
- A full-raw family loss blocks expansion until classified.
- Any timeout, cancellation, checker defect, actual isolation leak, or missing audit receipt makes v7
  formally invalid. A post-hoc checker cannot repair it.

Report every call, usage completeness, context bytes, wall time, severe regression, and exact family
mechanism. One run per cell is not a stable latency estimate. No result here alone proves superiority
to an open-source product or authorizes compilation, learned selection, or production enablement.
