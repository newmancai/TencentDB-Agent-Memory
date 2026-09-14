# Porcelain-corrected single-file full-raw replication v9 protocol

Date: 2026-09-14. Frozen before any v9 model call. v9 replaces the invalid v8 matrix; it does not
rerun hyperframe or reinterpret any earlier receipt.

## Frozen inputs and execution

- Manifest SHA-256: `8db0d078e1413213c65827891b5fd65e3aeee8600dc64bb9b18d1074f020910e`
  at `.local-evidence/project-agent-route-v2-heldout-v9/manifest.json`.
- v9 checker SHA-256: `223a4349caaf4cd7f1d8a70f12bbe8e6590be808f775c4ae85b1a90f0299151a`;
  imported v8 checker SHA-256: `dfb8fd115cb7aeeeddce3739cda8dc941c1383f1a7f2736718cf85ae6aa42cbe`.
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
smoke check. The runner rejects every changed path outside that source file. Git porcelain parsing now
preserves the first line's two-character status and is covered by a repository-backed regression test.

The outer filesystem sandbox exposes only the current opaque lane clone. All eight clones are fixed at
the declared base, contain only the ignored benchmark marker, have no remotes, and cannot resolve the
reviewed head. Event logs are retained and scanned for web search and forbidden workspaces. Execution
failures remain arm-qualified indeterminate observations.

## Families and exposure boundary

- [jmespath PR #335](https://github.com/jmespath/jmespath.py/pull/335): insertion-order FIFO parser
  cache, capacity 512, hit-without-refresh, and no insert after a concurrent removal failure.
- [pluggy PR #727](https://github.com/pytest-dev/pluggy/pull/727): missing-hook-argument warnings point
  at the external caller through ordinary and `call_extra` paths.
- [zipp PR #154](https://github.com/jaraco/zipp/pull/154): `Path.iterdir` on a file raises
  `NotADirectoryError` while directory iteration remains unchanged.
- [typeguard PR #566](https://github.com/agronholm/typeguard/pull/566): Literal matching scans every
  candidate with exact runtime-type equality before value equality, removing bool/int order dependence.

jmespath, pluggy, and zipp were present in v8's frozen manifest but received zero v8 calls. typeguard is
fresh. hyperframe is excluded after two v8 calls; hpack, PrettyTable, and importlib_metadata remain
excluded after v7.

## Checker preflight

For all four families and both stages, the declared base returns compatibility pass / behavior fail;
the exact reviewed head and a separately authored equivalent implementation return compatibility pass /
behavior pass. Alternatives use explicit FIFO deletion, an arithmetic stack level, `OSError(ENOTDIR)`,
and an `any(...)` exact-type scan. The 24-result matrix is stored at
`.local-evidence/project-agent-route-v2-heldout-v9/preflight/checker-matrix.json`, SHA-256
`7bd116612b3a6532079bce53b6b7b53cbac0e104bb9b03fb59baa8df7b238997`.

Every full-raw first task has 12 ordered user observations including the accepted decision. Second tasks
add no history and test cumulative same-topic behavior. No retrieval, compilation, local model, GPU,
production path, Gateway, or hand-authored patch enters an arm.

## Frozen interpretation

The first necessary task per family is the independent quality unit; a cumulative control is not an
additional win.

- At least one completed first-task split favoring full raw, with no completed first-task full-raw loss,
  is the minimum independent replication of v4's mechanism.
- Four first-task ties leave lossless full raw experimental and do not upgrade v4.
- A completed first-task full-raw loss blocks expansion pending mechanism review.
- Any timeout, cancellation, checker defect, isolation leak, output-scope violation, or missing audit
  receipt makes the whole v9 matrix invalid. A post-hoc checker cannot repair it.

Report every call, usage completeness, context bytes, wall time, changed path, and severe regression.
One run per cell is not a stable cost estimate. v9 alone cannot prove open-source or product superiority
and cannot authorize learned selection or production enablement.
