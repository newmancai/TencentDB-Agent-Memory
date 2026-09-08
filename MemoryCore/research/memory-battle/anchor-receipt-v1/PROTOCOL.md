# Executable receipt feedback v1

Implementation repair after evaluation: capacity exhaustion now rejects an entire event without
changing active/history/seen, rather than committing its first fields. The protocol and field
mapping are unchanged. All three public splits and subsequent-read scoring were rerun; semantic
counts were unchanged. A focused test verifies unchanged state and retry after capacity rejection.
Committed aggregate JSON results are in `results/`; source events remain reproducible upstream.

Development revision v1.1: initial development mapping incorrectly treated supplemental
refund amount as the original refund field (5 false repairs). Upstream process_refund explicitly
defines operation modes; v1.1 uses those modes and total_goodwill_credit, and does not map payout
route `split` to stored refund_method. All development arms rerun. Calibration/external outputs
were not inspected before this change. This is API-contract correction, not task-keyword tuning.

Scoring correction v1.2 (no runtime changes): upstream mutable snapshots omit derived getter
fields (e.g. a booking's joined flight departure time). Missing oracle fields are unverified,
not demonstrated false invalidations. Report verified/ALL accepted as well as precision on
labeled accepted, with unverified count explicit. Both development/calibration scoring rerun;
external-domain output not inspected before this correction. No new runtime confidence claim.

Comparison completion: PreviewAsCompletion promotes preview/rejected results to completion,
holding field mapping fixed. It is an explicit ablation, not a claim to represent the strongest
memory baseline. All three splits are scored with it; no change to the verified policy. Shopping
has no preview events, so equality there provides no evidence of preview discrimination.
Native fallback uses a separate base store, not a filtered evolved store. A synthetic integration
test is supplemented by 600 native checks on all 100 held-out-domain replay tasks.

This is a bounded B subclass with E consumption, not a substitute for general natural-language
feedback or real coding-agent business validation. STALE remains the semantic challenge source.

Official STATE-Bench revision 5644b1838d96bc4483da29642d058ecaa6f80f7f; only its 300 TRAIN
trajectories are used. Customer support = development, travel = calibration, shopping = held-out
domain evaluation. Schema/API documentation informs all domain adapters before evaluation;
this is transfer of a common feedback engine across configured APIs, not zero-shot API learning.
No held-out task outcomes may alter the adapter. Official 150 TEST tasks are not used for learning.

Reexecute each public tool action in the original task environment at its original clock.
Runtime receives only tool name, arguments, actual result, task scope and chronological order.
Offline oracle receives independent full environment snapshots. Snapshot deltas and expected
task outcomes are never available to B. Disclose divergence from originally recorded results.
Do not silently score new executions as exact reproduction of original trajectories.

Memory is initialized only from actual observable read results, never oracle snapshots. Completed
write receipts may establish a new value, identify an obsolete remembered value, or be insufficient
to determine a value. Preview/rejection/exception should not be treated as proof of a changed field.
Whether the environment actually changed is checked offline, including possible partial writes.
Record missing old memories, unsupported tools/fields and action-only status separately.

Compare frozen memory, naive receipt/argument application, and verified B→E. Measure exact
record/version targeting, accepted precision, stale-target coverage, false invalidation, unknown,
per-event CPU/time/bytes, and later public read consistency. The latter is a component metric,
not success of a newly acting agent. Confidence bounds use independent task units where possible;
many fields changed by one tool event are correlated, not independent confidence evidence.

E must preserve original versions and use native MemoryCore persistence/read identities. Off,
read failure, timeout, corrupt state and scope/version mismatch must recover the base path.
The sidecar and candidate pool have explicit bounds. Zero explicit memory feedback does not mean
zero environmental evidence, and validity repair is not causal blame for task failure.
