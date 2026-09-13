# Held-out v9 invalid evaluation review

Date: 2026-09-14. v9 completed 16/16 executions but is formally invalid because the frozen typeguard
checker accepted a behaviorally incomplete no-history patch. It provides diagnostics, not a Phase A
replication or product score.

## Frozen execution results

All 16 cells completed with checker and usage receipts. Filesystem isolation was true throughout;
visibility violations, unexpected paths, severe regressions, and missing usage were all zero. The raw
summary recorded raw-full 8/8 and no-history 5/8, mechanically three wins and five ties.

At the independent family level, the frozen first-task checks showed one apparent split and three ties:

- jmespath: raw-full implemented insertion-order FIFO, capacity 512, hit-without-refresh, and the
  concurrent-removal boundary; no-history instead added a lock around the old random half-eviction at
  capacity 128. Frozen first task: raw pass, no-history fail.
- pluggy: both arms selected `stacklevel=3`; both stages passed.
- zipp: both first tasks changed a file listing to `NotADirectoryError` and passed. On the cumulative
  control, no-history read stale repository expectations and reverted to `ValueError`, while raw-full
  retained the accepted decision; this is one family-internal mechanism observation, not a second
  independent win.
- typeguard: both first tasks passed the frozen bool/int examples. Raw-full checked exact runtime type
  before equality. No-history wrote the conditions in the opposite order.

## Checker defect

The protocol explicitly required exact runtime-type equality **before** value equality, but the frozen
checker tested only ordinary bool/int outcomes. A post-run read-only probe used a legal Enum literal
whose cross-type `__eq__` raises. The no-history patch raised that runtime error; raw-full, the reviewed
head, and the independent equivalent all returned the expected `TypeCheckError`. Probe evidence is
`.local-evidence/project-agent-route-v2-heldout-v9/postrun-typeguard-order-probe.json`, SHA-256
`de141c9199a4424e0cec68bb26142442835fefff2af12380c1f8fbc022947721`.

The probe cannot repair or rescore the frozen matrix. It proves the checker admitted an implementation
that violated a declared semantic clause, triggering v9's pre-registered invalidation rule. The hidden
typeguard difference is diagnostic evidence in the same direction as jmespath, not an additional score.

## Evidence and cost boundary

- Results: `.local-evidence/project-agent-route-v2-heldout-v9/results-v1`.
- Receipts SHA-256: `5f163d337931b1d43a75417b7c1441cff9a94b88881fdae4559e3178f914237b`.
- Summary SHA-256: `9dad1a39581784f143c79063c2adfaa92f801f642cbd25f9051ced934336607d`.
- No-history: 870,841 total input, 154,809 non-cached input, 16,239 output, 6,974 reasoning-output
  tokens, 676.860 seconds.
- Raw-full: 575,231 total input, 108,415 non-cached input, 10,973 output, 3,887 reasoning-output tokens,
  17,354 injected context bytes, 529.119 seconds.

The raw-full totals are 33.95% lower for total input, 29.97% lower for non-cached input, 32.43% lower for
output, 44.26% lower for reasoning output, and 21.83% lower for wall time in this single run. Because the
quality matrix is invalid and each cell ran once, these are retained accounting facts, not stable savings
or a product claim.

## Prospective recovery

v9 will not be rerun, and jmespath, pluggy, zipp, and typeguard are now exposed. Future matrices must use
new families and comply with [checker authoring standard](CHECKER_AUTHORING_STANDARD.md): in addition to
base fail, reviewed pass, and independent-equivalent pass, every critical clause needs a plausible
near-miss implementation that the checker rejects. Only a fully clean new matrix can open Phase B.
