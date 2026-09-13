# Sequential coding-agent B+E product protocol v1

This protocol compares MemoryCore augmentation inside each coding product. It is
not a raw model leaderboard.

## Tasks

Use at least twelve previously unused, independently checkable repository tasks
from at least four project clusters. Every cluster has an earlier task, explicit
user correction or changed project constraint, and a later task where that state
may or may not apply. Include both:

- necessary-update tasks where using the correction should improve the checker;
- hard same-topic controls where carrying the correction forward would regress.

Each manifest task supplies a separate workspace for every arm; all four are
fresh disposable worktrees at the same base commit and dependency setup. A
`.agent-benchmark-worktree` marker is mandatory in every workspace. Hidden
checker commands and expected outputs never enter the agent prompt. The runner
rejects tracked pre-run changes and records the base commit plus the agent's
post-run porcelain status for every arm.

## Arms

Run all four arms in rotated order:

- `codex_clean`: ephemeral Codex, user config ignored, automatic project-document
  injection and native memory use/generation explicitly disabled;
- `codex_memory`: same configuration plus the bounded MemoryCore context;
- `claude_clean`: Claude Code fresh session, no session persistence, auto memory
  and CLAUDE.md discovery disabled, empty setting sources and explicit empty MCP configuration;
- `claude_memory`: same configuration plus the identical MemoryCore context.

The clean and memory arms for one backend must use the same model and effort.
`--ignore-rules` alone does not disable AGENTS.md, and ephemeral sessions alone
do not establish native-memory isolation. Checked-in instruction files remain
ordinary readable files; this protocol disables automatic discovery, not file access.
These are controlled configurations, not an evaluation of either complete native product.
Use `baseline_context` to supply the same raw prior observations to the clean arm;
label omission of history as an additional ablation rather than the strongest baseline.
Cross-backend comparisons are secondary because products and models differ.
Memory context contains source IDs, valid/superseded times, exact evidence and
scope. It must not contain hidden checks or final patches.

## Execution and scoring

`agent_product_runner.py` runs one task per disposable workspace. It never uses a
dangerous permission-bypass flag. Default arm order rotates by task to reduce
sequence bias. After the agent exits or its process group is stopped on timeout, it runs the manifest's
argv-form checker and records:

- agent/checker completion and return codes;
- checker pass/fail and severe-regression flag;
- input, cached-input, output and reasoning tokens when exposed;
- reported cost when exposed;
- agent and checker wall time;
- mode, backend, model, task and whether memory context was injected.
- base commit and agent-created workspace changes.

Checker timeouts are explicit failures. Receipts are replaced atomically after
every arm so interruption cannot leave a partially written JSONL file.

Primary metric is paired checker utility: memory-arm wins minus losses inside
each backend. Report success rate, severe regressions, p50/p95 latency and added
tokens/cost separately. Missing usage is `null`, never estimated.

Pass requires, on the fixed held-out set:

- positive paired utility for both Codex and Claude Code;
- no increase in severe regressions for either backend;
- at least one necessary-update win and no net loss on same-topic controls for
  each backend;
- all disabled/absent-memory runs remain valid clean baselines.

No result authorizes production until the task source, base revisions, cluster
split, prompts, MemoryCore record alignment and checker provenance are published.

Manifest tasks require `id`, `kind` (`necessary_update` or
`same_topic_control`), `prompt`, argv-form `checker`, a `workspaces` object with
all four arm paths, and `memory_context` for the memory arms. The runner writes
per-call stdout/stderr, `receipts.jsonl`, and an aggregate `summary.json`.

Every task also needs `cluster_id` for a passing summary. The summary checks the
exact expected four-arm matrix, duplicates, task metadata, twelve tasks, four
clusters and both task kinds inside every cluster. `evaluation_mode` defaults to
`diagnostic`; diagnostic and pilot runs cannot set `pass=true`. Meeting these
minimum observed conditions is not statistical proof or product parity.

`agent_product_runner.py` still consumes supplied context files; it alone does
not establish how context was learned. The new `scripts/project-agent/` host
implements actual persistent observation → scoped context → coding → checker
execution. `sequence_smoke.py` exercises that host with three paired tasks and
independent state/workspaces. Its single synthetic fixture is an integration
smoke only; it does not satisfy the real-project held-out protocol above.
