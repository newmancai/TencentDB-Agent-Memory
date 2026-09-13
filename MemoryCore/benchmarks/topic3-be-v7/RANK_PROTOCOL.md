# v7.2 fixed-alarm-budget logit diagnosis

Written after v7/v7.1 hard-label outputs, before logit acquisition/scoring. Reverse
example order changes alarms89→27 with identical correct example associations.
Hard-label coverage alone cannot distinguish bias/threshold shift from improved
ranking. This is post-output development diagnosis, not new confirmation.

Reconstruct all original144target prompts for none/unlabeled/labeled/reversed,
with exactly the same messages, model, chat template and evidence. No new prompt,
gold or threshold fitting. Forward passes collect next-token logits for A/B/C;
score=logit(A)-logsumexp(logit(B),logit(C)). This is a ranking score, not calibrated
confidence. Confirm A/B/C are single tokens; report argmax agreement with original
generations. Batched numerical differences must not silently replace old outputs.

Predeclare K=11,33,89 for every arm (existing observed alarm capacities, not selected
using gold), report ALL K under both silver references, never select best K as
default. Equal-K ranking comparison includes marked changed-target hits, alarms
inside silver-same pairs, and unknown/ambiguous contexts separately. Secondary
rank agreement between orders is descriptive. No optimization of model weights,
gold, example choice, prompt order or score thresholds. Full acquisition overhead
recorded separately; forward-only service time not compared as an inference win.
Top-K is selected from all144targets BEFORE separating silver-unknown cases. This
global pool includes future-task scores and is an offline separability diagnostic,
not a deployable online budget policy. IDs used for score ties are deterministic.
