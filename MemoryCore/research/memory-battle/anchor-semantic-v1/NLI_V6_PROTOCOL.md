# Independent relation signal, development first

Model: [cross-encoder/nli-deberta-v3-base](https://huggingface.co/cross-encoder/nli-deberta-v3-base),
official revision `6c749ce3425cd33b46d187e45b92bbf96ee12ec7`, Apache-2.0, English,
trained on SNLI/MultiNLI. This is a borrowed baseline, not our innovation or a
multilingual guarantee. Labels follow the official card: contradiction, entailment,
neutral. Weights are unchanged; no fine-tuning or gold inputs.

Two predeclared lanes use the same development candidates:

- `nli`: new raw observation as premise, each prior raw candidate as hypothesis.
  Select the highest contradiction candidate only if contradiction beats its
  entailment and neutral scores; otherwise abstain. Score is uncalibrated.
- `assertion_nli`: existing v4 generation proposes a target and assertion pair.
  Check source alignment with only quote/whitespace equivalence; unaligned output
  remains error. NLI tests the proposed new assertion against the old assertion.
  A neutral/entailing result withholds invalidation. Include **all** upstream v4
  generation tokens/time, including abstentions/errors, plus NLI cost.

No semantic gold, topic-specific filtering, heldout changes or classifier training.
Both lanes preserve probability vectors, targets, errors and cost. Pairs above
512 tokens are errors, never silently truncated. NLI contradiction does not prove
temporal supersession, valid scope, causal blame or commercial precision. Those
claims require separate calibration and lifecycle evaluation.

V5 generation scouting was stopped after three completed calls all exhausted
4096 tokens without a final answer. A fourth request was already in flight when
the client was cancelled; preserve its eventual service receipt and cost. This
is an explicit budget incompatibility finding, not a full 16-case method score.
The shared server remains running and is not restarted during the in-flight call.

Calibration is the already selected 16-case split; no outputs from it were examined
before fixing these lanes. Generate unchanged direct and assertion prompts with
the v3/v4 greedy, non-thinking settings, explicitly overriding all shared-server
sampling defaults. NLI uses the unchanged classifier. The original calibration
grid {0,.5,.7,.8,.9,.95,1}, at least five accepted cases and 90% target agreement,
applies to direct, nli, assertion_nli. No eligible threshold means no enabled
policy. This does not authorize semantic invalidation regardless of eligibility.
Only after saving the policy may heldout outputs be scored. Failure will not be
repaired using heldout wording or threshold changes.
