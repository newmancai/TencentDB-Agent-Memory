# Held-out v10 results: Phase A replication achieved

Date: 2026-09-14. v10 is a complete valid matrix under the near-miss checker standard. It replicates
one independent full-raw benefit beyond v4. It does not establish general product or open-source
superiority.

## Integrity

- Frozen protocol: [v10 protocol](HELDOUT_V10_PROTOCOL.md).
- Results: `.local-evidence/project-agent-route-v2-heldout-v10/results-v1`.
- Receipts SHA-256: `e5adc118cfe58dd59d2679212e03b37e8ab58a771694ee5ac0b6c621b2c253f8`.
- Summary SHA-256: `74ead72aa6204468b2f77d9a55fe56ec5f053dbeb215dda764cc19364c192a46`.
- Calls: 16/16 completed; checkers: 16/16 completed; usage missing: 0.
- Filesystem isolation: 16/16 true; visibility violations: 0; unexpected paths: 0;
  severe regressions: 0.
- Preflight: 42/42 expected outcomes, including 18 rejected near-miss stage rows.

The frozen runner's generic `decision` string still says `diagnosis_only_no_candidate_fix_tested`.
That label predates v10 and is not used as a score. The prospective runner now emits a Phase A candidate
label only after a complete necessary-task split, still pending manual patch audit.

## Quality

Raw-full passed 8/8 tasks; no-history passed 6/8. The mechanical task comparison is two wins and six
ties, but both wins belong to one persistent project family. The independent first-task result is:

| Family | No history | Raw full | Family result |
| --- | --- | --- | --- |
| h2 | pass | pass | tie |
| pycodestyle | pass | pass | tie |
| path | pass | pass | tie |
| importlib_resources | fail | pass | raw-full win |

All four raw-full cumulative controls passed. The importlib_resources no-history control repeated its
first-task failure and is not a second independent win.

Patch audit confirmed every frozen semantic witness:

- h2 arms both scan all content-length fields, accept equal repeats, and reject a later conflict.
- pycodestyle arms both use the actual common filesystem path and retain single-file local discovery.
- path arms both accept positional and keyword `TempDir` arguments while preserving context and removal.
- importlib_resources raw-full raises the required `TypeError`, names the module, explains
  `__spec__ is None`, and does not reject a falsey valid spec. No-history chose `ValueError` and failed
  the frozen checker. Its agent explicitly inferred that different exception from repository-local
  precedent; the accepted history supplied the otherwise underdetermined maintenance decision.

The raw-full importlib_resources agent's one optional inline smoke command had a quoting `SyntaxError`
and was not retried; the independent frozen checker completed and passed. This is retained as execution
detail, not hidden or counted as an agent failure under the frozen contract.

## Cost accounting

| Metric | No history | Raw full | Raw-full change |
| --- | ---: | ---: | ---: |
| Total input tokens | 1,074,156 | 523,336 | -51.28% |
| Non-cached input tokens | 189,548 | 81,480 | -57.01% |
| Output tokens | 22,474 | 11,534 | -48.68% |
| Reasoning-output tokens | 11,571 | 4,761 | -58.85% |
| Total wall time | 668.636 s | 438.657 s | -34.40% |
| Injected context | 0 bytes | 17,322 bytes | — |

Each cell ran once, and cache/order effects are not independently replicated. These figures are exact
v10 accounting but not a stable latency, token, or price claim.

## Decision

Phase A is satisfied: v4 had one valid independent family win (tqdm), and v10 adds a second valid win in
a new project and decision type (importlib_resources), with no raw-full family loss or control regression.
The supported mechanism is narrow: verbatim accepted maintenance history disambiguates a choice that
the current repository and generic coding ability do not uniquely determine.

Proceed to a broader public quality comparison and a same-model open-source comparator. Do not add a
compiler, learned selector, or new retrieval layer unless a repeated quality failure motivates it.
