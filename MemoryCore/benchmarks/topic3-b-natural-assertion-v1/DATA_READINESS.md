# Data readiness for causal memory attribution

2026-09-13. Read-only audit after the natural candidate gate passed. No model,
production hook, memory mutation, or GPU action was performed.

## What is available

The public WildChat/LMSYS adapter supplies conversation text and feedback-behaviour
labels. The new v2 run can bind the follow-up to the preceding answer and create a
current-interaction correction candidate. It does not contain the MemoryCore
candidate set or action that generated that historical answer, a logged action
propensity, exact prompt memory spans, or an objective downstream outcome.

A filesystem scan found `decision_trace`/`feedback_claim` JSONL only in the newly
created Phase 0, synthetic component, oracle, end-to-end, and natural-candidate
evidence directories. No older natural host log already contains the four-part causal
contract.

The older `anchor-recovery-r3` evidence is still useful and should not be discarded.
It has real isolated SQLite/tool execution, board-file readback, 16 paired synthetic
business tasks, and native recall/search audits. Its final ordinary versus adjusted
result was 15/16 versus 14/16 complete, with one adjusted win, two losses, and thirteen
ties. Thus “recover more raw source after uncertain memory” was not a quality win and
caused one confirmed unsupported write. This is a strong negative baseline for any
future gate.

But `anchor-recovery-r3` is not the missing natural attribution source:

- conversations and business facts were constructed for that experiment;
- the arm policy was deterministic and no per-action propensity was logged;
- no later natural user feedback claim was linked to the original memory action;
- its contemporaneous native recall shadow had missing `taskRunId` and did not record
  the exact prompt-span contract now required;
- the paired outcome compares ordinary L1 to deterministic isolation plus L0 recovery,
  not a learned include/omit target binder.

Retrospectively inventing any of these missing fields would turn provenance repair
into false causal evidence. The old task result remains a negative paired experiment,
not training data for the new learned gate.

## Decision at audit time

The current repository is ready to **collect** valid trajectories but does not yet
contain enough valid trajectories to train or fairly evaluate a learned durable
target/promotion gate. The deterministic exact-scope rule also has no headroom on its
structured set. Therefore:

1. keep natural proposals current-interaction and `candidate` only;
2. keep the learned gate off;
3. do not backfill propensity, memory cause, or objective reward into public logs;
4. preserve `anchor-recovery-r3` as the same-information negative baseline;
5. next collect an isolated instrumented development batch whose answer-time trace
   has candidate IDs, selected action, exact prompt spans, policy version/propensity,
   output/tool IDs, later feedback, and an objective result.

This is a data-availability stop for learned promotion, not a claim that all B methods
fail. The persistent task can continue by designing that new instrumented batch; it
must not silently treat synthetic oracle labels or public feedback categories as the
missing causal ground truth.

## Subsequent instrumented batch

That bounded next action is now complete; see
[the instrumented loop result](../topic3-b-instrumented-loop-v1/RESULTS.md). Four new
synthetic projects used actual SQLite stale recall and actual Codex answers, then
paired temporary candidate include/omit against an objective local file. Include was
4/4, omit 0/4, and all twelve decisions replayed with numeric outcomes. This closes
the engineering/data-contract gap for a scripted oracle development source.

It does not change the natural-data finding above. The batch deliberately supplies
correct feedback and exact scope, so the deterministic rule is already perfect and
there is no fair learned-gate headroom. Natural causal attribution and durable
promotion remain unsupported by existing evidence.
