# Route v2 failure-discovery development results

Date: 2026-09-14. This is a development diagnosis, not held-out evidence or a product score.

## Question and sources

The first run asked whether two ordinary bug fixes are suitable for locating a project-memory failure.
The projects and commits were previously unused by this B+E product evaluation:

- Tenacity at `fd7842774cc10d41e68e6bc64afe7d9f83221aa0`, before
  [issue #233](https://github.com/jd/tenacity/issues/233) / [PR #278](https://github.com/jd/tenacity/pull/278):
  copying retry behavior omitted `retry_error_cls` and `retry_error_callback`.
- cattrs at `44aba28bd02388e0dc2c7d1539f7688b76c365cc`, before
  [issue #190](https://github.com/python-attrs/cattrs/issues/190): generated structuring with a renamed
  field and `forbid_extra_keys` rejected the effective input key.

For each issue, step 1 reproduced the real behavior and step 2 was an explicitly authored same-topic
control. Three independent persistent worktrees compared no project history, all raw observations,
and exact raw observations selected by BM25 top-8. All arms used requested Codex `gpt-5.6-sol`, medium
effort, controlled instruction discovery, the same external checker, and no compiler. The CLI did not
expose a served model ID or dollar cost.

The pre-fix checker returned 1 for both projects while its compatibility section passed. This proves
the target behavior was absent at the declared base; it does not prove that an agent needs memory to
repair it.

## Valid result

The valid result is `.local-evidence/project-agent-route-v2-development/results-v2`.

| Arm | Checker | Severe regressions | Input | Cached input | Uncached input | Output | Reasoning output | Complete wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no history | 4/4 | 0 | 1,118,438 | 1,031,040 | 87,398 | 17,882 | 6,474 | 467.415 s |
| full raw | 4/4 | 0 | 618,976 | 551,808 | 67,168 | 9,748 | 2,460 | 278.342 s |
| raw BM25 top-8 | 4/4 | 0 | 684,743 | 619,648 | 65,095 | 9,627 | 2,849 | 280.886 s |

All twelve agent calls and checkers completed. Every paired outcome was a tie: two necessary-update
ties and two same-topic-control ties for every comparison. There were no current-system failures,
memory-dependent wins, full-raw regressions, or retrieval misses. Top-8 selected the final correction
in both issue tasks, so its ties were not caused by dropping the update.

The no-history agents recovered both fixes from local code structure and the current request. These
four tasks therefore have no observed discrimination and must not be reused as held-out B evidence.
The lower aggregate exploration, token and wall-time totals in the two raw arms are only a development
cost hypothesis: four tasks, sequential cache/order effects, and no crossed replication are too weak
for an efficiency claim.

## Invalid interrupted result

`results-v1` is retained with `INVALID.json`. Its first checker defined callbacks with a parameter
named `state`, while the pinned Tenacity implementation calls them with `retry_state=`. Correct agent
changes were consequently misclassified. After fixing the checker, all three saved Tenacity diffs
passed the corrected stage-2 check. The run was stopped before completion and every v1 row is excluded
from quality and cost conclusions.

## Decision and next failure source

Close these two issue sequences as B-quality tasks; keep them only as runner/checker smoke material.
Do not implement a candidate memory repair from them.

The next development set must bind real issue or PR review decisions whose answer is not recoverable
from the pre-fix repository: an exact policy choice, exception, name/default, or scope decision selected
by the maintainer or user among multiple valid implementations. The current request should genuinely
depend on that prior decision, paired with an explicit same-topic case where carrying it over would be
wrong. Only a repeated full-raw or retrieval failure under those conditions justifies a repair arm.
