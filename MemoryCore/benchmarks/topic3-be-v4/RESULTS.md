# v4: source IDs work; same-model support review does not improve B

2026-09-12. Next16 development-reuse tasks,14 privileged source pairs,2missing.
No autonomous candidate discovery, unseen-answer generalization, learning or
persistent memory claim. All500 LongMemEval oracle questions were historically
used. Two source-only assistant reviews were produced without QA/gold/predictions;
they agree13/14. Loan preapproval350k→400k is changed in the first, unknown in
the second. Neither was changed after predictions.

| Arm | Review1 agreement /14 | Review2 agreement /14 | Contract errors | Logical calls | Input/output tokens | Generation service seconds |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| Shared direct draft | 6 | 5 | 0 | 14 | 5507/1231 | 42.660 |
| Draft + ordinary review | 7 | 6 | 0 | 28 | 12938/2460 | 84.238 |
| Draft + proposition-support review | 6 | 5 | 0 | 28 | 14030/2461 | 85.188 |

Both silver references give support vs ordinary 0wins1loss13ties and support vs
draft 0wins0loss14ties in exact relation correctness. One wrong changed becomes
unknown but remains different from silver same. Review1 changed matches/predictions:
draft5/12, ordinary6/12, support5/11; all six labelled changes enter supplied pairs.
These are assistant-silver agreements, not true calibrated feedback precision.
The actual shared run is42calls,21461input/3690output tokens,126.766s generation.
No truncation. Logical reviewed-arm costs include the draft; source audit/model
loading are additional costs. Same output cap does not imply equal input cost.

## What the implementation fixed

Lossless host spans with old/new IDs replace model-copied quotations for every arm.
All42 outputs satisfy the common schema and source-ID contract. This demonstrates
working provenance plumbing in this run; different cohorts mean v3→v4 is not a
paired causal estimate of interface improvement. IDs do not prove fact support.

## The remaining failure is before review

Independent output diagnosis (evidence-root TARGET_DIAGNOSIS.md, first10 nonempty
pairs) identifies several concrete failures without changing labels:

* Volleyball3–2→5–2: draft/support select "confidence in athletic abilities" as
  the attribute. Ordinary changes only relation to changed, leaving the wrong
  attribute. Relation correctness therefore overstates complete B correctness.
* Coupon organization→later redemption: all arms invent old_fact="not redeemed".
  The old request did not establish a redemption status for that coupon.
* Fishing advice: all arms turn a later comparison into a claimed old live-bait
  recommendation. Old evidence did not assert that recommendation.
* Restaurant discussion→theatre audition: all arms label a topic/intent change
  as replacement of a current memory property.

The pair input has no fixed target proposition. A model jointly sees both sides,
chooses its own attribute, invents a convenient old value and then reviews its
own draft. This is an observed failure mechanism, not proof that every error is
caused by anchoring. It explains why more support instructions can preserve a
wrong target while every citation ID remains legal.

## Research reassessment and next bounded hypothesis

[FActScore](https://arxiv.org/abs/2305.14251) separates a generation into atomic
claims and asks whether each is supported; its biography-domain accuracy cannot
be transferred to current-state feedback. [ALCE](https://arxiv.org/abs/2305.14627)
evaluates factual correctness and citation quality separately, supporting our
decision not to treat source-ID validity as factual truth.
[Intrinsic self-correction research](https://arxiv.org/abs/2310.01798) finds that
review without external feedback can fail or degrade reasoning. It is a relevant
warning, not evidence that all source-grounded review is impossible.

Do not run another free-form pair prompt or train on these outputs. The next
testable change is OLD-ONLY target formation: establish bounded candidate facts
from old memory before exposing later evidence; later B must reference an existing
target ID and cannot silently change its subject/property/old value. Ordinary and
support baselines must share these targets and evidence. Count old-target omission
and hallucination separately; a wrong frozen target is still wrong. If targets
are manually supplied, call it privileged diagnosis, not autonomous success.
Do not use QA answers to select targets or add coupon/fishing-specific rules.

This is a proposed protocol/interface correction, not yet implemented or proven.
It stays within B current-applicability detection. E and feedback learning remain
unchanged; no new default. Eventually learning requires externally checked labels
and separate later evaluation, not self-confirmation by this same reviewer.

## Reproduction and handoff

Evidence root `/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-v4/` contains
adapted runtime/offline files, model/results.jsonl, model-calls.jsonl, two independent
source reviews, TARGET_DIAGNOSIS.md and summary.json. Run score.py with that root.
All raw errors and labels retained. No official gold changed.

Two boundary tests,176repository tests and plugin build passed. ModelPID2325172
stopped after42calls; other GPU users untouched. Local code only, PR#2 unchanged,
no production-memory operations. Continue from this report, not older prompt plans.
