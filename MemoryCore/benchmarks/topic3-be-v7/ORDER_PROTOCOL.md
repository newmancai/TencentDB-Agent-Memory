# v7.1 diagnostic: reverse correctly labeled example order

Written after all v7 outputs, before new calls. Primary v7 labeled arm increased
alarms89vs33unlabeled, with worse pair agreement in both independent silver audits.
Hash order happened to yield B,B,A,A. Hypothesis: example position affects the
apparent feedback benefit. Reverse all four examples to A,A,B,B, keeping each
source/target/label intact. All144current targets and other input fields, prompt,
model, max8tokens remain identical. Run144calls, no prompt edits/retries/gold
changes. Current cohort is reused for diagnosis, not held-out confirmation.

Compare exact144target predictions and both silver summaries to original labeled.
A large shift supports order sensitivity, not a proven last-label causal mechanism
(example content order changes too). Do not choose the better order as a tuned
default; report both and retain original costs. This is not a feedback-learning
success or a new baseline replacing the completed primary experiment.
