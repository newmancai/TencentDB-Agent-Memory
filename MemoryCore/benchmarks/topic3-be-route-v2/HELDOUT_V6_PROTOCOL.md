# Small-task lossless full-raw replication v6 protocol

Date: 2026-09-14. Frozen before any v6 model call. v5 produced useful behavioral diagnostics but
failed the Phase A execution contract when two no-history jsonschema calls timed out. v6 is a clean
replacement on four unexposed families, not a retry or timeout adjustment on exposed tasks.

## Frozen inputs and execution

- Manifest SHA-256: `3fad1cb4d83bf453bc996caea6d67acdec0f3ee6c094500aa63dd771e50f2524`
  at `.local-evidence/project-agent-route-v2-heldout-v6/manifest.json`.
- Checker SHA-256: `b8896699bed92cb4a97a9bebe9e233340b01bfd1d9ac45df8e8df6938664ac1c`.
- Runner SHA-256: `0203e517fecfc3c6b29a58ad314f2537c7df52d70b758892de888811479b95e9`.
- Backend: Codex `gpt-5.6-sol`, medium effort, ephemeral, controlled instruction discovery,
  `web_search="disabled"`, 300-second timeout.
- Arms: `no_history` and lossless `raw_full`, rotating order, two sequential tasks per project;
  16 calls total. The closed top-8 candidate remains absent.

Every current task explicitly says to work only in the current repository and not use the internet
or search outside it. The existing outer `bwrap` mount hides the product checkout, result tree,
checker, and sibling arm; Codex's inner workspace sandbox blocks model-issued network access. Each
arm uses an opaque `lane-a` or `lane-b` directory and marker rather than an arm name. All eight clones
have exactly the declared base plus their marker, have no Git remote, and cannot resolve the PR head.

The post-v5 runner reports an execution failure as `indeterminate`; it cannot create a memory win,
regression, or all-arm tie. Any execution failure, checker defect, actual isolation leak, or missing
audit receipt still invalidates the entire matrix under the long-term task contract.

## Fresh project families

- [platformdirs PR #540](https://github.com/tox-dev/platformdirs/pull/540): apply POSIX absolute-path
  semantics to XDG single and list variables, filtering invalid entries while retaining valid order
  and platform fallbacks.
- [hpack PR #287](https://github.com/python-hyper/hpack/pull/287): treat an empty byte value as a
  perfect static-table match, while preserving the same-name non-empty literal path.
- [PrettyTable PR #468](https://github.com/prettytable/prettytable/pull/468): expand tabs on the final
  formatted cell string so measurement and rendering agree, including custom formatter output.
- [importlib_metadata PR #519](https://github.com/python/importlib_metadata/pull/519): return `None`
  only when every metadata source is absent, while preserving the PKG-INFO fallback and ordinary
  metadata parsing.

All four repositories are new to the route-v2 development and held-out matrices. Hyperframe #168
and zipp #154 were inspected before freeze but not selected: the former duplicated an organization
and exposed an almost mechanical bit mask, while the latter's exception substitution offered little
decision ambiguity. Neither appears in the manifest and neither will be counted.

## Behavior-checker preflight

For all four families and both stages, the declared base returns compatibility pass / behavior fail;
the exact reviewed PR head and a separately authored alternative both return compatibility pass /
behavior pass. Alternative patches use prefix-based POSIX validation, an explicit empty-bytes branch,
per-line tab expansion, and a direct absent-text return respectively. Their diffs and hashes are
retained under `.local-evidence/project-agent-route-v2-heldout-v6/preflight`.

The platformdirs and PrettyTable source trees omit generated version modules; the checker supplies
minimal version placeholders instead of installing or modifying either clone. The PrettyTable check
uses an ASCII-only width adapter because the environment lacks its optional/newer `wcwidth` API.
The target assertions concern raw-tab removal and equal ASCII line widths, not Unicode width quality.
These substitutions are fixed and identical across bases, reviewed heads, alternatives, and arms.

Each full-raw history contains exactly 12 user observations and its accepted decision appears
verbatim. The second step receives the same prior history through persistent state but adds no new
history. Current prompts never contain the accepted implementation detail. No retrieval, compilation,
local model, GPU, production path, or Gateway is involved.

## Frozen interpretation

Count project families and the first necessary task. A following control only tests accumulated scope;
it is not another independent win when a first-task implementation remains wrong.

- At least one new family where full raw passes a completed first task and no-history completes but
  fails, with no full-raw family regression, is the required clean replication of the v4 result.
- Four family ties leave full raw experimental and do not upgrade the v4 signal.
- Any full-raw family loss blocks expansion until its source, scope, staleness, or execution mechanism
  is classified.
- Any incomplete or contaminated cell invalidates v6 as a formal replication even if the remaining
  rows look favorable. Do not use a timeout as a no-history failure.

Report every call, exact family reading, severe regressions, usage completeness, context bytes, and
wall time. One cell per arm is not a stable speed estimate. No v6 outcome by itself establishes an
open-source superiority claim or authorizes learned selection, compilation, or production enablement.
