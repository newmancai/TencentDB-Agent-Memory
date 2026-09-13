# B+E product readiness against coding agents

## Verdict

The current repository satisfies the requested **initial B+E research delivery**:
reviewable design, public runner and baseline, structured results, bounded
implementation, off/failure fallback, and portability notes are present. It does
not yet satisfy **effective B+E product readiness**, and it is not a peer product
to Codex or Claude Code.

| Level | Current status | Evidence still missing |
|---|---|---|
| Assignment artifacts | met | reviewer acceptance remains external |
| E verification/lifecycle mechanics | met as bounded sidecar | broad production host and distributed failure validation |
| B feedback representation | partially met | natural memory-cause attribution and durable cross-task correctness |
| B+E quality gain | not met | public CUPID feedback arm is 3W/4L/5T vs frozen |
| Temporal candidate discovery | promising component | 15/16 small STALE candidate test; no downstream answer gain yet |
| Coding-agent product | not met | real sequential repository tasks, UX, permissions, orchestration and product-level reliability |

The distinction matters: a complete negative-result research delivery can be
accepted without proving that the method improves a product. The first statement
is true today; the second is not.

## Product comparison boundary

[Official OpenAI documentation](https://developers.openai.com/codex/cloud/)
describes Codex cloud as isolated, parallel, background coding tasks with
reproducible environments, diff review and PR handoff. Claude Code documents a
coding agent across terminal/IDE/desktop/web, plus [project instructions and auto
memory](https://code.claude.com/docs/en/memory) and [hooks for deterministic
control](https://code.claude.com/docs/en/hooks-guide). A competitive product
therefore needs more than memory retrieval:

1. reliable repository reading, editing, commands and independent checks;
2. resumable and parallel task execution in isolated environments;
3. project/user memory with explicit scope and correction semantics;
4. deterministic policy/hooks for actions that must not rely on model judgment;
5. observable cost, latency, failure, diff and rollback;
6. an end-to-end held-out coding benchmark.

MemoryCore contributes primarily to item 3 and part of items 4–5. It should be a
memory subsystem usable by coding agents, not be marketed as the entire agent.

## Next product milestone

[`topic3-be-agent-product-v1`](topic3-be-agent-product-v1/PROTOCOL.md) defines the
next comparison. For both Codex and Claude Code it measures a clean isolated arm
and the same product with identical MemoryCore context. Within-product deltas are
the primary B+E result; cross-product totals are secondary. Hidden repository
checkers, severe regressions, token/cost and wall-time remain visible.

Promotion requires a positive held-out within-product utility delta for both
backends, no severe-regression increase, and bounded added context/cost. Until a
completed run reaches that threshold, the new temporal candidate adapter stays
off and has no Gateway or durable-write hook.
