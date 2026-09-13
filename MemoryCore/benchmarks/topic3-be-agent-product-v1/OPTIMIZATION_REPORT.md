# B+E product-slice optimization report

## Outcome

This branch is the reviewable product slice extracted from the B+E research
branch. Relative to `origin/feat/anchor-memory` at
`0ddea892f1e362b4b937b2b38d23beb2a5ac4329`, it changes 19 paths with 1,802
insertions and 20 deletions. The research branch remains intact at
`8c2876d07f719b86445d3e1683490817d97e8e24`; it currently carries 707 added
research/evidence paths relative to the same base. Thus the product review no
longer asks maintainers to traverse the research archive.

The shipped feedback runtime is 651 source lines across the explicit package
entry and four implementation files. It does not modify Gateway or the broad
`core/index.ts` barrel. Evaluation code and tests stay outside the runtime.

This is an engineering-validation pass, not evidence that B or E already has
stable product utility. No Codex or Claude Code task arm was executed while
performing this refactor; the hardened runner is the next held-out product test.

## Foundation: split before optimization

Commit `dc89284af851615a27888d2f993532ec83b76eae` retained only:

- the opt-in answer-feedback, dependency-candidate and verified-lifecycle APIs;
- the SQLite exact-record lookup needed by lifecycle validation;
- their focused tests and the coding-agent comparison runner.

All historical experiments, generated packets, evidence ledgers and route
reviews remain on `delivery/topic3-be-v1` and PR #2. The split does not delete or
rewrite those results.

## Optimization rounds

### 1. Explicit package boundary

Commit `61be8986152e8a2af1203d2da30bd5e1056b85df` added the
`./memory-feedback` package export and its own build entry. Consumers no longer
import an internal source path, while the large default barrel remains unchanged.

Verification: the plugin build emitted `dist/memory-feedback.mjs` at 20.47 kB
(6.09 kB gzip), and a self-package import resolved the four public capability
families.

### 2. Batched lifecycle validation

Commit `d218b73f1721be0c1e7142ac722fc0e215e1ed87` replaced per-entry readback
queries with deduplicated, backend-safe batches of 20 IDs. For a head with `N`
entries, validation changes from `3N` store calls to at most
`ceil(2N/20) + ceil(N/20)` calls; shared source IDs reduce it further. Publishing
a new candidate also reads its two source records in one call instead of two.

The integration test locks the common one-entry read at one base-store call and
one auxiliary-store call while preserving stale-source, corrupt-head, timeout
and exact-baseline fallback behavior.

### 3. SQLite exact-ID pushdown

Commit `1195e53a46f8b1d0f9b88357bb35bfdef6594b28` removed the local backend's
remaining hidden full scan. `recordIds` now becomes a parameterized
`record_id IN (...)` SQL predicate, with session, time and isolation predicates
included in the same query. Previously SQLite loaded the applicable table/session
rows and filtered IDs in JavaScript.

The focused test covers exact IDs, empty IDs, missing IDs, ownership and time
filters. Tencent VectorDB already uses `documentIds`; the lifecycle batch size of
20 follows that backend contract.

### 4. Reproducible coding-agent runner

Commit `aaadd6804a6f320b12172696b862627f157de117` makes the held-out product
comparison fail closed instead of silently producing ambiguous receipts. It now:

- validates safe/unique task IDs, argv-form checkers, positive timeouts and
  non-reused workspaces;
- requires each task's arms to begin clean at the same Git commit;
- rotates the default arm order and records base commit plus agent changes;
- records backend launch errors and agent/checker timeouts as structured failures;
- writes `receipts.jsonl` and `summary.json` atomically;
- prevents any execution failure from satisfying the protocol pass condition.

Six runner tests cover paired backend scoring, rotation, manifest safety, missing
backend handling and failure-to-pass behavior.

## Verification

The final branch passed:

- MemoryCore Vitest: 23 files, 201 tests;
- product-runner unittest: 6 tests;
- Python bytecode compilation for runner and tests;
- plugin build, including the dedicated memory-feedback entry;
- self-package import of `runAnswerFeedbackAdapter`,
  `selectDependencyCandidates`, `FeedbackMemory` and `processFeedback`;
- `git diff --check`.

Machine-readable status is in
[`optimization-results.json`](./optimization-results.json).

## Remaining product gate

The next claim-changing step is the fixed held-out comparison defined in
`PROTOCOL.md`: at least twelve unused tasks from four clusters, with both
necessary updates and hard same-topic controls, run as clean/memory pairs inside
Codex and Claude Code. Until those receipts exist, this branch establishes a
small, portable and testable B+E boundary, but does not claim stable net utility,
commercial readiness or parity with either coding product.
