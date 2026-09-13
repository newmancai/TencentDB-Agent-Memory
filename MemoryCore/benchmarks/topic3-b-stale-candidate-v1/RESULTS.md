# STALE candidate-only dependency expansion results

## Outcome

The frozen fresh-holdout candidate test **passed**: 15/16 overall, positive
candidate recall 8/8, T1 4/4, T2 4/4, negative retention 7/8, and zero invalid
active-path quotes. Always-affected and always-unaffected were each 8/16; a
surface-overlap baseline was 10/16.

The one false positive treated increased involvement in local organizing as a
possible competing demand on attention previously devoted to a neighborhood
clean-up. It was a plausible topic association but did not make the old focus
unsafe. This is the concrete residual false-positive class for the next
independent test; it is not repaired on this set.

All 16 isolated `gpt-5.6-sol`, medium-reasoning calls completed without retry:
228,302 input tokens (127,488 cached), 2,458 output tokens (630 reasoning),
171.741 summed seconds, 10.596 seconds p50 and 14.447 seconds p95.

## What changed in the design

The direct binder and proposer-plus-judge bridge both failed at 13/16. The useful
boundary is earlier: nominate a bounded old-memory candidate when a later
observation supplies an exact direct or possible dependency, then let a later
answer or verification stage consume it. Do not collapse the proposal into an
automatic durable invalidation.

The additive runtime boundary is `selectDependencyCandidates`. It validates IDs
against a bounded caller-owned universe, exact later-observation spans, path and
`k` limits; off/failure yields no additive candidates, and its log fixes
`memoryMutationAllowed: false`. It is exported but not wired into Gateway or a
write path.

## Confidence boundary

This is a pre-registered component pass on only eight new expert-reviewed
synthetic STALE positives plus eight audited negatives. It validates method
shape, not population accuracy. It does not score STALE's downstream probes,
natural user traffic, candidate retrieval recall before the proposer, final
answer utility, persistence, or commercial benefit. The 15/16 point result has
wide small-sample uncertainty and must not be called a high-confidence business
result.

See `results/summary.json`, [the frozen protocol](PROTOCOL.md), and the parent
[research synthesis](../B_STALE_RESEARCH_REVIEW_2026-09-13.md).
