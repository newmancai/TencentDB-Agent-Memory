# Near-miss-preflight full-raw replication v10 protocol

Date: 2026-09-14. Frozen before any v10 model call. v10 follows the prospective checker-authoring
standard introduced after v9 and uses four families that have never received a benchmark model call.

## Frozen implementation and inputs

- Manifest SHA-256: `7166795b10d6858a1e9758f41154b1522ea26bcacc4be3233ee8bad1896d32e2`
  at `.local-evidence/project-agent-route-v2-heldout-v10/manifest.json`.
- Checker SHA-256: `0c4e835bb089522d03988719bf409e787cccd0c8d5f64b4077cb9e514e8c8f5e`.
- Preparation script SHA-256: `a2b652fdebcc4f26ce72e87083e4effd0ba4a6760e53f4ae3d20fadee8f23513`.
- Failure runner SHA-256: `498efceb9b728914edefe572936e2b89ad2a6ae466ecc110c220fb0d084182a8`;
  shared agent-product runner SHA-256: `1de7b893ed48577ee1d52dbed4216703db9e556b8da91d86ff95f720143b6158`.
- Project-agent host SHA-256: `b49771840b5a16450d5279e33f64b6436c643f8ebb5fa9a1182e13c43e28ff26`;
  backend SHA-256: `62ab10f7a79e66173b5eb8089110369bbdcd132ecf64a976b329f9ec4b1023ee`.
- Backend: Codex `gpt-5.6-sol`, medium effort, ephemeral, controlled instructions,
  `web_search="disabled"`, 300-second hard limit.
- Arms: `no_history` and lossless `raw_full`, rotated order, two sequential tasks per family;
  16 scheduled calls. Retrieval/top-8 remains closed.

Each request permits edits to exactly one source file, prohibits internet, outside-workspace search,
tests, docs, changelog, configuration, generated files, and bytecode, and permits at most one focused
smoke check. The runner rejects every undeclared changed path and preserves porcelain status columns.
The filesystem sandbox exposes only the current opaque lane clone. All eight clones are at the declared
base, have no remotes, and cannot resolve the reviewed head.

## New families and decisions

- [h2 PR #1317](https://github.com/python-hyper/h2/pull/1317), base
  `1cd9ce0c1c9862df948318b12c3b75d72537abd4`: equal repeated content lengths are accepted; any
  later conflicting value is rejected even when separated by another header.
- [pycodestyle PR #1323](https://github.com/PyCQA/pycodestyle/pull/1323), base
  `16f212741b5cba7495ad45f448cbc5361ae9e5bd`: project configuration starts from the real common
  filesystem path, not a lexical prefix, while a single file still finds its local config.
- [path PR #237](https://github.com/jaraco/path/pull/237), base
  `efa71fcb34e5a9d34b34474326af67d082ad9b4a`: `TempDir.__init__` accepts positional and keyword
  arguments already consumed by `mkdtemp`, preserving cleanup behavior.
- [importlib_resources PR #331](https://github.com/python/importlib_resources/pull/331), base
  `c6773a1534416cbb0ca274de99959c04bee99277`: a `None` module spec raises a named explanatory
  `TypeError`, while an importable package, including a falsey-but-valid spec, remains usable.

No family above occurred in a prior benchmark manifest. The importlib_resources source URL is
`https://github.com/python/importlib_resources`; the link label above identifies PR #331 in that
repository.

## Semantic witness and near-miss gate

The checker preflight has 42 rows: two stages for four bases, four reviewed heads, four independent
equivalents, two near-misses per family, and one additional importlib_resources near-miss. Every base
and near-miss passes compatibility and fails target behavior; every reviewed and equivalent variant
passes both stages. Matrix SHA-256 is
`c3ef0a53c644a44535b93a0fa19504651257c2b16f00dbdf052cc71a597541c2`.

| Family | Positive witnesses | Rejected plausible near-misses |
| --- | --- | --- |
| h2 | absent, single, invalid, equal duplicates, separated conflict, triple equal | reject every duplicate; compare only adjacent duplicates |
| pycodestyle | real sibling common parent; single-file local config | anchor on first file; move one directory above the actual common path |
| path | no args, all keyword args, all positional args, context and explicit removal | accept positional only; accept keyword only |
| importlib_resources | ordinary package, named `None` spec, second module name, falsey valid spec | generic message; wrong exception type; truthiness instead of `is None` |

The h2 checker executes the extracted target method AST with local dependency stubs; it tests branch
behavior and does not inspect patch strings. All other checkers import only the isolated checkout.
Exact preflight patch hashes are retained in
`.local-evidence/project-agent-route-v2-heldout-v10/PREPARATION.json`.

Every full-raw first task receives 12 ordered user observations including the accepted decision.
Second tasks add no history and test cumulative controls. No retrieval, compilation, local model, GPU,
production path, Gateway, or future implementation enters an arm.

## Frozen interpretation

The first necessary task per family is the independent quality unit; a cumulative control is not an
additional win.

- At least one completed first-task split favoring full raw, with no completed first-task full-raw loss
  and no full-raw control regression, is the minimum independent replication of v4.
- Four first-task ties leave full raw experimental and do not upgrade v4.
- A completed first-task full-raw loss blocks expansion pending mechanism review.
- Any timeout, cancellation, checker defect, isolation leak, output-scope violation, or missing audit
  receipt invalidates the whole v10 matrix. Post-hoc probes cannot add wins.

Report every call, usage completeness, context bytes, wall time, changed path, and severe regression.
One run per cell is not a stable cost estimate. v10 alone cannot prove open-source or product superiority
and cannot authorize learned selection or production enablement.
