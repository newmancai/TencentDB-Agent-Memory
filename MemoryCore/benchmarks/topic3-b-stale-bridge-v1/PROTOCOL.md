# STALE bounded dependency bridge v1

Frozen before calls on 2026-09-13 after the direct binder failed its first fixed
set, specifically 1/4 on STALE T2 propagated conflicts while retaining 8/8
cross-attribute negatives. The new hypothesis is that candidate-scope expansion
must be separated from final invalidation instead of making one conservative
classifier both discover and judge a dependency.

This design is informed by the official STALE/CUP-Mem pipeline at code commit
`ea7d391103a151927cd29d2f01d87597a782bdcb`, which separates affected-bucket
proposal, bounded candidate selection and invalidation judgment. This run is a
small independent implementation, not a CUP-Mem reproduction or transferred
paper result.

## New holdout and labels

Use the same public parquet and revision as `topic3-b-stale-binding-v1`. Exclude
its eight positive UIDs. Within T1 and T2 separately, sort remaining rows by
`SHA256("topic3-b-stale-bridge-v1:" + uid)` and take four each.

Create eight negatives before calls: T1 old observations receive the next T1
later observation cyclically; T2 old observations receive reverse-index T1 later
observations. The actual pairs were audited before inference:

- location permission vs meditation duration;
- meditation duration vs house ownership;
- house insurance vs knee-limited exercise;
- running routine vs location permission;
- altitude vs knee-limited exercise;
- relationship status vs house ownership;
- snow persistence vs meditation duration;
- credit score vs location permission.

Both observations can remain true in each negative. Original expert-reviewed
STALE pairs are `supersede`; audited negatives are `retain`. Hidden explanation,
T1/T2 type, probes and haystack remain evaluator-only.

## Three arms

For each of sixteen pairs:

1. `direct`: the unchanged v1 one-call binder.
2. `bridge_proposer`: given only the old and later observations, emit the changed
   practical basis and zero or more bounded dependency paths. A path labels the
   relation `necessary`, `possible`, or `none`; it does not decide the final action.
3. `bridge_judge`: receives the same pair plus the proposer's untrusted output and
   returns `supersede|retain|ask` with the same exact-span contract.

Thus there are 48 isolated `gpt-5.6-sol`, medium-reasoning calls, no retry. The
bridge gets no additional source evidence or gold, only an extra structured
reasoning pass. Proposal and judge costs are both charged to the bridge arm.

## Metrics and exit

Score direct and bridge actions against the same labels, T1/T2, negative retention,
exact spans, prediction counts, paired bridge-vs-direct wins/losses/ties, tokens
and wall-time p50/p95. Fixed always-update, always-retain and surface-overlap
baselines remain visible.

Bridge passes only if all hold:

- overall at least 14/16;
- positive at least 7/8;
- T2 at least 3/4;
- negatives at least 7/8;
- no invalid exact span on a predicted supersession;
- bridge T2 correct count exceeds direct T2;
- bridge negative correct count is no more than one below direct.

Pass supports a candidate-only affected-scope adapter design; failure stops this
two-stage configuration. Neither outcome authorizes durable promotion, a learned
gate, or a production hook.
