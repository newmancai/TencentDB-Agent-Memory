# STALE dependency bridge results

## Outcome

The registered two-stage bridge **failed**. Direct and bridge arms were both
13/16 overall and 5/8 on positives. Bridge changed T2 from 1/4 to 2/4 but changed
T1 from 4/4 to 3/4; both retained 8/8 negatives and had zero invalid exact-span
citations. Paired bridge vs direct was 1 win, 1 loss and 14 ties.

The bridge therefore did not turn additional reasoning into net decision value.
It fixed a credit-collection dependency but overruled a correct direct update
for newly enabled location sharing. It missed the registered 14/16 overall,
7/8 positive and 3/4 T2 thresholds.

## Stage diagnosis

After the registered failure was known, the intermediate proposals were examined
as a diagnostic. A `necessary` or `possible` path appeared for 7/8 positives,
including 3/4 T2, and no active path appeared for 8/8 negatives. This was not a
registered success metric and is not counted as this experiment passing. It
motivated the fresh candidate-only experiment rather than a post-hoc relabel of
this run.

## Cost

All 48 calls completed. The direct arm used 226,783 input tokens and 1,380 output
tokens over 148.568 summed seconds. The proposer-plus-judge bridge used 455,788
input tokens and 3,400 output tokens over 303.180 summed seconds. Its per-call
p50/p95 were 8.784/13.960 seconds. The extra stage roughly doubled calls and
input without improving overall correctness.

This result closes the proposer-plus-final-judge configuration. It authorizes no
memory invalidation or persistent update. See `results/summary.json` and
[the frozen protocol](PROTOCOL.md).
