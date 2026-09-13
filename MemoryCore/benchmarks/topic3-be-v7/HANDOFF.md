# B v7 continuation

Closed locally 2026-09-13; experiments started 2026-09-12. Read RESULTS.md and
the three frozen protocols. Code and replay bundle are local; PR #2 is unchanged.

Implemented controlled example feedback on fixed original L1 targets, with no
examples / same unlabeled examples / reviewed labels. 60 development-reuse tasks,
54 usable pairs, 144 targets; two assistant silver references, five disagreements.
Labels raise alarms33→89 and changed-target coverage12→19 (review1), but same-pair
alarms8→28. Reversing identical examples reduces alarms89→27 and changes74labels.
At fixed K11, no examples finds8 marked changes, labeled4 under both reviews.
All K11/33/89 and both references are retained. No stable learning gain established.

576 generation calls and576 separate forward prompts completed. All generation
formats valid; forward/generation argmax differs on8/8/10/10targets across arms.
176 tests, example-isolation test, build and aggregate replay passed. Owned model
and logits processes exited; no production/E/default-policy changes.

Keep the immutable-target reader. Do not select a favorable order, threshold or
subset of this cohort. All remaining KU rows in the present selection were used,
and all LME oracle questions remain historically exposed. Future confirmation
requires a new public source audit and an explicit calibration/evaluation split.

Separate validity of feedback labels from utility of using them. A bounded
follow-up can use verified outcomes to calibrate decisions on a frozen score,
with no-example equal-budget selection as the baseline. Monotone calibration
cannot improve ranking; proving better candidate selection requires additional
evidence, not merely more alarms. Count verification/example acquisition and
false-target consequences before connecting any persistent E action. This is
the next hypothesis, not an implemented algorithm or automatic new experiment.

Exact metric replay is packaged in results/replay and replay.py; it rebuilds
sources/examples from the pinned public data and recomputes three summaries.
Native DBs, complete requests and audit rationales remain in
`/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-v7/`.
