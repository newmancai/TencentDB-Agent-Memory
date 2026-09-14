# Controlled B+E evaluation protocol for sequential coding agents

This document freezes the original four-arm product protocol and its runner. It
measures the incremental effect of MemoryCore inside each coding backend; it is
not a raw leaderboard for Codex and Claude Code. The final project direction and
accepted evidence are summarized in the [submission report](../B_E_FINAL_SUBMISSION_REPORT_2026-09-14.md).
Any later comparison should receive a new protocol version instead of changing
these criteria after results are known.

## Evaluation question

Given the same repository state, backend configuration and task, does persistent
project memory improve a later coding decision without causing a regression on a
closely related control task?

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
- mode, backend, model, task and whether memory context was injected;
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

## Persistent repository sequences (schema 2)

`sequence_runner.py` accepts clusters, each with four marked independent
workspaces at one declared initial commit and ordered `steps`. Each step carries
raw user `history`, a task prompt, task paths and an external checker. Within a
cluster/arm, both working-tree edits and MemoryCore state persist to the next step.
This deliberately differs from schema 1's fresh workspace for every task.

Clean arms record the same user history without model compilation and read it
verbatim. Memory arms run the existing constraint compiler and read the scoped
state. No prepared memory-context file is accepted as a substitute. Compiler
receipts and costs are separate from coding, and total step time includes both.
Project clusters may run concurrently, but each individual arm remains sequential.

`prepare_real_projects.py` prepares boltons, more-itertools, packaging and
itsdangerous at fixed upstream commits. Each receives three authored maintenance
scenarios grounded in its existing API: a changed new helper policy, a similar
helper whose prior behavior must be retained, and a later policy change plus
follow-up API. These are controlled tasks on real repositories, not real user
issues or an official benchmark. Twelve tasks are a pilot, not a held-out proof.

Checkers are outside the agent workspaces. Before running, each checks that
existing APIs pass and the absent new feature fails. Later checks cover current
features cumulatively: failures can propagate along a sequence and are not twelve
independent observations. Compatibility exit code 2 marks a tested old-API
regression; it is not a complete repository test suite or complete severity oracle.

All four workspaces are prepared even if a service is unavailable. Missing arms
remain missing, and partial-backend summaries cannot pass the full protocol.
The compiler and task prompts are not tuned on these pilot outcomes.

Any future manifest should alternate `arm_order_offset` across clusters as well
as step order. The first recorded pilot had no offset field (equivalent to 0 in
every cluster), so its first and third steps always ran raw first. Reproduction
must use that recorded manifest and report that its latency/cache comparison was
not fully counterbalanced.
