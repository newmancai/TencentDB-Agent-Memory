# STALE candidate-only dependency expansion v1

Frozen on 2026-09-13 after `topic3-b-stale-bridge-v1` failed its registered
end-to-end thresholds. In that run, the unregistered stage diagnostic found a
non-`none` proposal for 7/8 positives (3/4 T2) and no active proposal for 8/8
negatives, while the final judge erased one useful proposal and one T1 update.
This protocol tests that candidate-recall observation on a fresh holdout; the
old result is motivation, not evidence for this result.

## Data and isolation

Use `STALEproj/STALE` revision
`617c51dc200b5ab09970834144c7e51c77959af0`, converted parquet SHA256
`b432e28f13505096f87ad1cad0e5725fb8ea18297b125a4ca78d4b6f34160d53`.
Exclude all sixteen positive UIDs used by the binder and bridge experiments.
Within T1 and T2, select four rows each by ascending
`SHA256("topic3-b-stale-candidate-v1:" + uid)`.

Create eight cross-attribute negatives before inference using the same fixed
pairing rule as the earlier experiments. The pairs are:

- clean-up planning vs political identification;
- political identification vs online-forum responsibility;
- forum responsibility vs residential moves;
- residential stability vs newborn care;
- weekly socializing vs residential moves;
- student status vs online-forum responsibility;
- hand-tool use vs political identification;
- vehicle ownership vs newborn care.

Each negative was read before calls and labelled unaffected because both
observations can remain true. Inference receives only `M_old` and `M_new`.
STALE explanation, T1/T2 type, probes, haystack and evaluator labels stay
private.

## Method

One isolated `gpt-5.6-sol`, medium-reasoning call per pair, no retry. The model
does not decide deletion. It emits zero or more bounded dependency paths from
the later change to an exact basis in the old observation, with relation
`necessary`, `possible`, or `none` and an exact later-observation quote.

Prediction is `affected` when at least one valid path is `necessary` or
`possible`; otherwise it is `unaffected`. An active path with a missing or
non-exact quote invalidates the prediction. This output may only nominate old
memory for later retrieval or verification. It cannot mutate, invalidate or
promote memory.

## Metrics and frozen exit

Report overall accuracy, positive candidate recall, T1 and T2 recall, negative
retention, exact-span failures, prediction counts, an always-affected baseline,
an always-unaffected baseline, surface-overlap baseline, tokens, and wall-time
p50/p95.

Pass requires all of:

- overall at least 14/16;
- positive recall at least 7/8;
- T2 recall at least 3/4;
- negative retention at least 7/8;
- zero invalid active-path quotes.

Pass supports only a bounded candidate-expansion interface. It does not show
correct final invalidation, downstream answer quality, persistence safety or
business benefit. Failure stops this candidate-only configuration.
