# v6: verbatim target localization; batch-label cost control fails

2026-09-12. Kept B on already-written native memory, removed model fact rewriting.
16 next development-reuse tasks,14 supplied source pairs,35 nonempty old spans,
0 omitted spans, no duplicate old/later texts. Source selection remains privileged
via public support annotations; all500 LME oracle questions were previously used.
No autonomous discovery, held-out generalization, policy learning or E update.

## Native implementation and independent labeling

14 complete old sources were written through native MemoryCore L1, read back by
owner/record ID, and checked for version/content equality. All35 target substrings
match their persisted originals and offsets. Same full source context is supplied
to both arms. Model outputs only A/B/C; host preserves original target identity.
No generated fact can replace the old statement. This is an isolated native
known-record integration, not an installed Gateway hook or full-history retrieval.

Two independent assistant source-only silver reviews agree14/14:5changed,9same.
They also identify the same5 changed target IDs before seeing predictions. Neither
reads questions/official answers/model outputs. This agreement is not calibrated
truth or independent human gold. `Dr.` splits across spans; full old context is
retained, but not every target is a standalone proposition.

## v6 original comparison

| Arm | Pair agreement /14 | Changed pairs matched /5 | Calls | Input/output tokens | Generation service seconds |
| --- | ---: | ---: | ---: | --- | ---: |
| Whole old record | 10 | 1 | 14 | 6266/28 | 2.244 |
| Independent original spans | 11 | 3 | 35 | 14868/70 | 4.010 |

Spans vs whole:2wins1loss11ties. Whole has2unknown, spans3unknown. Both have zero
changed predictions on silver-same PAIRS; this does not imply zero span false
alarms. Spans emits4changed target decisions,3 match the prelabelled changed
targets. Independent TARGET_AUDIT.md confirms these3 correct localizations and
one false change on a neighboring evaluative sentence about bird diversity.
Pair aggregation hides that extra false target. The two remaining changed targets
(therapy frequency and current residence within a planned visit) were present but
judged unknown, so these are not candidate misses. Whole also misses them.

This is a small localization signal with higher cost, not stable superiority.
Input rises2.37x and calls2.5x. Preserve exact qualifiers; do not repeat v5's claim
that a correct pair label automatically means a correct target. No model-format
failures or truncation occurred in the49 original calls.

## v6.1 same-cohort batch output diagnostic

BATCH_PROTOCOL.md was written after v6 results and before batch outputs. The14
development pairs are intentionally reused; old baselines remain unchanged. All
targets are placed in one prompt with an ordered A/B/C string, one call per pair.

Batch agreement8/14, correctly matched changed targets2/5 with12changed target
predictions,4unknown pairs. Against independent spans:2wins5losses7ties. Of35
target decisions,21 change labels versus the independent calls (no output-format
errors); batch is therefore not a pure lossless throughput optimization.
14calls,7171input/49output tokens,2.653s generation service. It saves input/calls
relative to independent spans but does not preserve semantic quality. Do not use
the batch prompt as default or claim its unreviewed extra target alarms are useful.

All63 actual calls:28305input/147output tokens,8.908s generation service. These
times exclude model loading and source audits; they are not deployment p95 or
full-system cost. No extra model retries or after-output label changes.

## Research interpretation and decision

[Batch Prompting](https://arxiv.org/abs/2301.08721) reports useful cost reductions
but also dependence on task complexity and batch size.
[BatchPrompt](https://arxiv.org/abs/2309.00384) documents position/order sensitivity
and adds procedures to mitigate it. Their results are not a guarantee for this
zero-example4B source-target task. Here batching changes joint decoder context and
empirically changes21/35labels. That is consistent with interference, not a causal
proof of which attention/position mechanism failed. No prompt-injection attack
was tested or needed to explain these observations.

Retain the independent immutable-target reader as the B research candidate;
reject this batch-label configuration. Do not extend E or train on these4B labels.
The next substantive question is whether independently checked feedback can repair
the remaining target-specific confusion (time scope, factual premise, neighboring
property) on later data. Compare labeled feedback with the same unlabelled examples
and a fixed no-example baseline; selection/audit costs must be included. Before
claiming learning, use a single sufficiently populated, predeclared evaluation
cohort rather than accumulating small favorable slices. Current5changes are
insufficient for a calibrated-confidence claim. This is a plan, not a completed
learning experiment. Do not tune current14cases or use their silver at runtime.

## Reproduction and handoff

`prepare.py` selects/maps public sources; `native.ts` writes/readbacks original
records; `detect.py` runs whole/spans; `batch.py` is a separate optional diagnostic.
`score.py` and `score_batch.py` use offline silver only. Evidence root:
`/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-v6/`, with native DBs,
all receipts, both silver reviews, TARGET_AUDIT.md and both structured summaries.

176repository tests,3boundary tests and plugin build passed. OwnedPID2346620
stopped after63calls; other GPU processes untouched. No production-memory actions.
Code/results local; remote PR#2 remains unchanged. Resume from this report.
