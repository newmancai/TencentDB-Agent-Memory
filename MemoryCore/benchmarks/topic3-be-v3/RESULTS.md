# B current-applicability instruction ablation — 2026-09-12

Implemented and ran the narrow B qualification in PROTOCOL.md. This is a prompt
ablation with the same model, schema and supplied evidence, not a new verified
grounding architecture. No policy fitting, persistence or end-to-end QA experiment.

16 next hash-ranked development-reuse tasks, 13 eligible pairs, 3 missing retained.
All LongMemEval oracle targets were previously exposed; neither new question
generalization nor autonomous candidate discovery is claimed. The pairs are
selected using offline support annotations. B sees only source content and dates.

Two separate assistants reviewed sources without questions, official answers or
current predictions. They agree on 12/13 relations. Both identify four changes;
one marks Silver eligibility versus Gold status unknown, the other same. This
disagreement remains intact. Both label sets yield the same agreement totals
below, because all three model arms incorrectly call that pair changed.

| Arm | Raw agreement with silver /13 | Valid-contract agreement /13 | Contract failures | Changed matched / predicted | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Direct structured judgment | 6 | 5 | 2 | 3/7 | 4649 / 1386 |
| Historical/current role prompt | 8 | 7 | 1 | 4/9 | 5026 / 1367 |
| Explicit fact/scope decomposition | 9 | 5 | 6 | 4/6 | 5871 / 1360 |

Raw paired decomposition vs direct: 3 wins, 0 losses, 10 ties; vs roles: 1 win,
0 losses, 12 ties. Both enhanced prompts cover all four silver changes; this is
conditional on supplied pairs, not global recall. With 13 pairs and assistant
silver, these are development signals, not calibrated precision or stable gains.
Decomposition's input is 26.3% higher than direct. Generation service seconds:
direct42.666, roles45.266, decomposition43.557. Total39 calls, 15546 input/4113 output
tokens, 131.489 seconds generation service. No output truncation. Loading and
source-audit effort are additional costs, not included in generation service.

## What improved and what still fails

Decomposition recovers a current collection-count change missed by direct and
avoids some false replacements on compatible information. It does not establish
a useful advantage over the stronger role baseline: only one extra correct
relation, and valid evidence output is worse.

The same structured output still permits a model to invent the old state: being
eligible for Silver membership is not an assertion of currently holding Silver.
All arms treat later Gold status as a replacement. New fields do not enforce
that old_fact is actually supported by old_quote. This is a semantic failure,
independent of whether a quote is copied correctly.

Six decomposition contract failures include empty quotes, omission of words,
punctuation normalization and turning an anaphoric source into a standalone
paraphrase. For example a source has "they've been staying..." but the proposed
quote starts "my parents have been staying...". That can be a reasonable fact
paraphrase, but is not a verbatim citation. Exact validator failures must not all
be called semantic errors, nor silently fixed and credited as current success.
No format repair, retries or after-output prompt adjustment was performed.

## Concrete continuation decision

Keep the B focus. Do not deploy decomposition or start a feedback learner from
these fallible outputs. The next implementation candidate is a source-preserving
interface: host supplies lossless clause/span IDs, B selects evidence IDs while
placing paraphrased facts in separate fields. This prevents copying errors from
being confused with semantic failure; it does NOT validate entailment. Apply
the same interface to direct and decomposition baselines in a new protocol and
new development cohort. Earlier telecom experiments already found interface
benefits, so source IDs alone cannot be presented as a new B contribution.

The substantive hypothesis remains whether explicitly checking that each proposed
old/new fact is supported reduces false current-state transitions. Test that
against ordinary review at the same evidence/call budget. If it does not improve,
do not keep adding prompt fields or learn its predictions as verified labels.
Verified-example learning is deferred, not abandoned. E remains unchanged.

## Artifacts and validation

Local evidence: `/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-v3/`.
`adapted/pairs.json` is runtime evidence; `offline.json` is not consumed by B.
`model/results.jsonl` preserves every raw decision and contract failure;
`model-calls.jsonl` records actual requests and generation cost.
`source-review.json` / `source-review-second.json` preserve independent silver.
`summary.json` is reproducible using score.py. No official gold was modified.

Two boundary tests, 176 repository tests and plugin build passed. Owned model
PID2315237 stopped after all39 calls; other GPU processes were not touched.
Code/results are local, not uploaded to PR #2. No production-memory operations.
