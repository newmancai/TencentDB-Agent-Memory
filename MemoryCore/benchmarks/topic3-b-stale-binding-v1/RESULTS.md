# STALE direct binding results

## Outcome

The frozen direct binder **failed**: 13/16 overall, 5/8 positive
supersessions, T1 4/4, propagated T2 1/4, negative retention 8/8, and no
invalid exact-span citation. Always-supersede and always-retain were each 8/16;
the surface-overlap baseline was 9/16.

The result identifies a conservative component rather than a generally good
invalidation policy. It safely rejected every audited cross-attribute negative
and handled direct conflicts, but it usually would not turn a change in one
attribute into invalidation of a dependent attribute. The three missed T2 cases
were a moved household vs borrowed possession, shared-computer constraints vs
local-file storage, and house surrender/probate vs belongings insurance. The
single T2 success was an imminent move vs neighbor check-ins.

## Cost

All 16 isolated `gpt-5.6-sol`, medium-reasoning calls completed without retry:
226,825 input tokens (69,760 cached), 1,171 output tokens (267 reasoning),
138.839 seconds summed wall time, 7.985 seconds p50 and 11.591 seconds p95.

## Boundary

This is a component test on eight expert-reviewed synthetic STALE pairs plus
eight pre-call audited negatives. It does not measure STALE downstream probes,
durable state mutation, end-to-end answer quality or commercial benefit. The
failed configuration is not enabled. See `results/summary.json` for the
machine-readable result and [the protocol](PROTOCOL.md) for selection and exit
criteria.
