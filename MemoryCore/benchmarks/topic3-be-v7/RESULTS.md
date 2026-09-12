# B v7: reviewed examples raise alarms without a ranking gain

2026-09-12. This round implements controlled feedback-example adaptation on
immutable native memory targets. It does not establish a useful learned B policy.
Labels recover real changes, but also increase unsupported alarms; reversing the
same examples changes 74/144 decisions. At the same alarm budget, the original
labeled configuration does not outperform the no-example baseline under either
independent silver review. Do not enable it as a default or train E from its output.

## Protocol and evidence

PROTOCOL.md predates primary outputs. The cohort contains all remaining 30
knowledge-update tasks after rank40 in the established v2 hash order/exclusions,
plus 30 single-session-user controls at the same ranks: 60 tasks, 54 usable source
pairs, 144 original spans, zero omitted spans. Six missing pairs remain in results.
All 500 LongMemEval oracle questions were historically used: this is development
reuse, not unseen-question generalization. Source pairs are supplied using offline
support annotations; B has not demonstrated autonomous candidate discovery.

Dataset: `longmemeval_s_cleaned.json`, upstream revision
`98d7416c24c778c2fee6e6f3006e7a073259d48f`. The existing v2 exclusions and hash seed
`topic3-be-v2:` are unchanged. Selection uses no new outcome-dependent replacement.
The original old sources were written to 54 native MemoryCore L1 databases and
read back; all 144 target offsets match the stored original content. This is the
v6 known-record integration, not a Gateway hook or full-history retrieval test.

Four examples come from prior v6 source-only consensus silver: two changed
targets and two targets in unchanged pairs, selected by hash, one per pair,
independent of v6 model correctness. No evaluation labels reach the model.
The labeled and unlabeled arms differ only in the relation field. All arms share
the same current evidence, target, prompt instruction, local Qwen3-4B model and
8-token limit. Examples are capped at four; model weights remain fixed.
The 54 source pairs are distinct, with no individual old/later text overlap with
examples. Hash order happened to produce B,B,A,A; it was not chosen using outputs.

Two assistant source-only reviews agree on 49/54 pair relations. Review 1 has
20 changed / 30 same / 4 unknown; review 2 has 17 / 30 / 7. Disagreements remain
unchanged and both references are reported. These are fallible silver labels,
not human gold, official QA grading, or calibrated confidence estimates.

## Primary controlled comparison

Numbers separated by `/` below refer to review 1 and review 2, respectively.
Agreement is over 54 pairs. Changed-target denominators are 20 and 17.

| Arm | Pair agreement | Marked changed targets found | All target alarms | Alarms in same pairs | Unknown targets |
| --- | ---: | ---: | ---: | ---: | ---: |
| No examples | 31 / 33 | 8 / 8 | 11 | 1 | 45 |
| Same examples, no labels | 36 / 35 | 12 / 11 | 33 | 8 | 14 |
| Same examples, reviewed labels | 29 / 26 | 19 / 16 | 89 | 28 | 12 |

Labeled versus unlabeled has 6 wins / 13 losses under review 1 and 4 / 13 under
review 2, with other pairs tied. All 432 outputs satisfy the A/B/C contract.
Thus format validity and correct example labels do not establish good feedback.

An independent post-output source audit checked the first five newly flagged
targets in silver-same pairs and first three newly matched changes, sorted by ID.
Real repairs include yoga frequency, Fitbit usage duration and egg inventory.
New errors include an ongoing battery problem, advice requests, an evaluative
sentence and compatible dinner plans. Two negative examples already demonstrate
continued requests/detail additions, so absence of negative examples is not a
sufficient explanation. The audit does not infer hidden model reasoning.
Unmarked targets in changed/unknown pairs are not automatically counted as false.
Even a matched change can share a span with still-valid facts; no whole-span
deletion is justified by this experiment. Full audit: local FEEDBACK_DIAGNOSIS.md.

## v7.1: identical examples, reversed order

ORDER_PROTOCOL.md was written after primary results and before this diagnostic.
All 144 targets were rerun with the four examples reversed, preserving every
example-label association and the same token count. Alarms fall from 89 to 27;
74/144 labels change. Pair agreement is 36 / 35 and marked target hits 13 / 11.
All outputs remain valid. Do not select this order as a new default: it reuses the
same development cohort. This demonstrates order sensitivity, not a causal proof
that the final example label alone caused it.

## v7.2: equal-alarm-budget ranking diagnostic

RANK_PROTOCOL.md predates logit acquisition. For each of the four original prompt
configurations, collect A/B/C next-token logits and rank all 144 targets by
`logit(A) - logsumexp(logit(B), logit(C))`. This is not calibrated confidence.
K=11,33,89 were fixed from already observed alarm counts before scoring against
silver. All K are reported; no favorable K is selected for deployment.

| Arm | K=11 marked hits | K=33 marked hits | K=89 marked hits | Same-pair selections at K=11 / 33 / 89 |
| --- | ---: | ---: | ---: | ---: |
| No examples | 8 / 8 | 16 / 13 | 19 / 16 | 1 / 5 / 24 |
| Unlabeled | 8 / 8 | 13 / 12 | 18 / 15 | 2 / 8 / 31 |
| Labeled | 4 / 4 | 13 / 11 | 19 / 16 | 3 / 8 / 28 |
| Reversed labeled | 8 / 6 | 15 / 12 | 19 / 16 | 1 / 5 / 31 |

At K=11, reviewed labels recover half as many marked changes as no examples.
At K=89, both find the same number, with more same-pair selections for labeled.
Within this protocol, the coverage increase from hard labels is therefore not
evidence of improved discrimination. Unknown-pair selections remain separately
available in `results/rank-summary.json`; they consume budget, not false labels.

This is an offline global-pool diagnostic: it uses future-task scores and does
not implement an online scheduler. Batched bfloat16 forward argmax matches the
original generations on 136/144, 136/144, 134/144 and 134/144 targets. All global
argmax tokens are A/B/C. These numerical discrepancies are disclosed; the original
hard-label results are preserved, not replaced by the forward results.

## Cost and validation

| Arm | Calls | Input / output tokens | Generation service seconds |
| --- | ---: | ---: | ---: |
| No examples | 144 | 68720 / 288 | 17.837 |
| Unlabeled | 144 | 203936 / 288 | 37.875 |
| Labeled | 144 | 207392 / 288 | 38.392 |
| Reversed labeled | 144 | 207392 / 288 | 38.279 |

Total: 576 generation calls, 687440 input / 1152 output tokens, 132.383 service
seconds. Separately, 576 forward prompts in batches of four cost 140.489 service
seconds. Loading, native writes and assistant audits are additional costs; these
numbers are neither deployment p95 nor full-system latency. Auditing/selecting
the four example labels is not free, and no online amortization claim is made.
Runtime: PyTorch 2.5.1+cu121, Transformers 4.57.6, bfloat16, SDPA, local
Qwen3-4B-Instruct-2507. No generation retries or format failures occurred.

176 repository tests, the example-isolation contract test and plugin build pass.
The contract checks that removing labels produces the same examples, source IDs
are not sent, and source objects remain unchanged. Native content/offset checks
also passed. This round does not rerun the full older off/failure matrix and does
not change its runtime implementation. Owned generation/forward processes have
exited; other GPU processes were untouched. No production-memory operations.

## Research reassessment and bounded next hypothesis

[Min et al.](https://arxiv.org/abs/2202.12837) show that example distribution,
format and label space can explain substantial in-context gains in their studied
tasks. [Wei et al.](https://arxiv.org/abs/2303.03846) find that learning example
mappings versus following semantic priors depends on model scale and instruction
tuning. [Zhao et al.](https://proceedings.mlr.press/v139/zhao21c.html) demonstrate
prompt/example/order biases and contextual calibration on their tested models.
None proves the mechanism in our model or guarantees that calibration will fix it.
Our controlled comparison and ranking diagnostic are consistent with a changed
alarm tendency, and do not establish better feedback discrimination.

The actionable distinction is **feedback validity versus feedback utilization**:
checking a few labels is not enough if their use shifts every target's decision
tendency. B should be assessed by which candidates earn scarce verification,
and whether verified outcomes improve later selection at the same cost. That is
a research hypothesis, not a novel or already successful algorithm claim.

Retain immutable target identity and bounded independent judgment. Do not add
more handpicked examples, tune this cohort's threshold, or expand E based on these
alarms. A subsequent protocol should compare a frozen no-example score with a
bounded feedback-calibrated decision rule on a separate calibration/evaluation
source split; include order controls, target-level error cost and acquisition
cost. Equal-budget static selection must remain a strong baseline. Calibration
may repair decision bias without improving ranking; either outcome must be
reported. Only after this distinction holds should verified outcomes drive
persistent E changes. This next hypothesis has not been implemented or tested.

LME knowledge-update rows in the current selection are exhausted and all oracle
questions remain historically exposed. A new confirmation needs a source audit
and a different public cohort, not a claimed held-out split of these questions.

## Reproduction, artifacts and delivery limits

`prepare.py DATA EXCLUSIONS V6_EVIDENCE OUTPUT` rebuilds the cohort and examples
using public inputs and the frozen prior silver. Reuse v6 `native.ts` to write and
read back `OUTPUT/pairs.json`. `detect.py RECORDS EXAMPLES OUT --endpoint URL`
uses the existing local provider contract; `order.py` takes the same arguments.
`score.py EVIDENCE_ROOT` and `score_order.py EVIDENCE_ROOT` recompute summaries.
`logits.py EVIDENCE_ROOT --model LOCAL_MODEL` and `score_rank.py EVIDENCE_ROOT`
reproduce the separate diagnostic. Fresh output directories prevent accidental
replacement of generation receipts. See the three frozen protocols for timing.

Committed `results/` contains structured aggregate outputs and a compact replay
bundle: both sets of current/prior silver decisions, exclusions, per-target
predictions/token receipts and logits. Public source text is reconstructed from
the pinned download, rather than copied into this bundle. From MemoryCore run:

```sh
python3 benchmarks/topic3-be-v7/replay.py /path/to/longmemeval_s_cleaned.json /tmp/fresh-v7-replay
```

This rebuilds source selection and the four examples, recomputes all three
summaries, and checks equality with recorded aggregates. It is a metric replay,
not a new model run or native integration check. Fresh generation still requires
the model/provider and native setup described above. Full native DBs,
model requests, source-review rationales, examples, logits and the target audit remain in
`/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-v7/`; prior example inputs
are in the adjacent v6 evidence directory. This is a local research increment.
PR #2 is unchanged, and this round does not
claim the original Topic3 acceptance criteria or commercial delivery are complete.
