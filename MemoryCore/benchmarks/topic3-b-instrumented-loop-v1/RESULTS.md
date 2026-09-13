# Instrumented temporary-correction loop: results

2026-09-13. The fixed four-project batch completed and passed. This is the first
current route experiment combining real isolated MemoryCore SQLite recall, actual
Codex answers, a feedback assertion candidate, exact prompt-memory spans, paired
include/omit actions, objective file checking, and complete restart replay.

| Stage | Correct |
|---|---:|
| initial answer after stale L1 recall | 0/4 |
| retry with current-interaction candidate | 4/4 |
| retry with candidate omitted | 0/4 |
| paired include wins / losses / ties | 4 / 0 / 0 |
| calls completed | 12/12 |
| fixed threshold | passed |

Every initial answer reproduced its actually injected stale value. Every include arm
returned the correction, while every omit arm returned `UNKNOWN`. The exact checker
read a local authoritative JSON file that was not sent to the model. Arm order
alternated; both actions recorded the candidate set, selection, policy, propensity
0.5, output ID, and exact prompt span where applicable.

The restarted trace was valid with 12 decisions, 4 feedback claims, 4 candidate
assertions, 12 outcomes, 12 learner-ready decisions, and no pending IDs. Total cost
was 168,480 input tokens (27,648 cached), 296 output tokens, 97 reasoning tokens, and
90.356 seconds wall time.

## Decision

The causal contract and temporary intervention now work end to end in an actual local
host path. The oracle result is also replicated under real SQLite recall rather than
only prompt packets: exposing the correction changes the exact task result, and
omitting it does not.

Do **not** train a learned gate on this task domain. The deterministic rule “include
an explicit, answer-bound, exact-span correction within the same interaction” is
4/4 and leaves no measured headroom. Scope is exact and target/correction are
scripted oracle conditions; a learned model could only fit four projects without a
fair advantage over the rule.

The legitimate component decision is therefore:

- keep exact scope matching deterministic;
- keep the natural-language extractor behind the fail-closed candidate gate;
- stop learned-gate work for exact current-interaction configuration correction;
- require a different, larger instrumented source with nontrivial target/scope
  ambiguity and natural or independently verified outcomes before reopening gate
  learning or durable promotion.

This does not prove commercial B benefit, natural memory-cause attribution, or safe
durable storage. The correction text and authoritative value were scripted to agree;
the four tasks are synthetic and exact. No production memory, external service, 30B
download, or GPU process was touched.

Raw evidence: `.local-evidence/topic3-b-instrumented-loop-v1/run-v1/`.
