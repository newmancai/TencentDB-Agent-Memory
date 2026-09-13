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

## Isolated PR-review result: valid but still no quality discrimination

The second development set used two real intermediate PR revisions and maintainer decisions:

- cachetools PR [#408](https://github.com/tkem/cachetools/pull/408), contributor commit
  `4dd976de71a0cb488f03719c2788b438e2f5ce1c`, before the accepted `Cache.__setitem__` review;
- HTTPX PR [#2278](https://github.com/encode/httpx/pull/2278), intermediate commit
  `424beb3d0f31e795ea9081e5c3171b97f17b789e`, before the final multipart-boundary review.

Each of the six workspaces was created by a direct depth-one fetch of its exact base SHA. It had one
reachable commit, no configured remote, and could not resolve the known final reviewed commit
(`b0ea1a4a0b38e1d3c60e802d171d776795c7a81b` or
`74de49482f0fdf49fb112d118bf580d764d18ccd`). The runner repeated this future-commit check before the
first model call. Both baseline checkers reported old compatibility passing and requested review
behavior failing.

The complete valid result is
`.local-evidence/project-agent-route-v2-review-isolated-development/results-v1`:

| Arm | Checker | Severe regressions | Input | Cached input | Uncached input | Output | Reasoning output | Complete wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no history | 4/4 | 0 | 2,160,978 | 1,998,080 | 162,898 | 11,955 | 3,384 | 368.908 s |
| full raw | 4/4 | 0 | 1,299,052 | 1,170,944 | 128,108 | 10,888 | 4,205 | 323.627 s |
| raw BM25 top-8 | 4/4 | 0 | 1,174,898 | 1,077,632 | 97,266 | 10,193 | 3,274 | 307.379 s |

All twelve calls and external checks completed. Every quality comparison was a tie: two necessary
updates and two same-topic controls. There were no memory-dependent wins, full-raw regressions,
retrieval misses, or severe regressions. In the harder HTTPX update, raw full and top-8 each used about
114k input tokens and 54 seconds of agent time, while no-history used about 607k and 127 seconds; all
passed. This is an efficiency lead worth testing, not evidence of a quality improvement. A single
development execution with order and caching effects cannot support a stable token or latency claim.

## Exact-policy development result

A third development matrix made the prior decisions less inferable from implementation alone:
[HTTP Core PR #1008](https://github.com/encode/httpcore/pull/1008) selected the exact safe h11 floor,
and [Werkzeug PR #3166](https://github.com/pallets/werkzeug/pull/3166) selected unpadded Base64 ETags.
Each was followed by an explicit later policy override. Isolation and pre-fix checker requirements
were identical to the second matrix. The complete result is
`.local-evidence/project-agent-route-v2-policy-development/results-v1`:

| Arm | Checker | Severe regressions | Input | Cached input | Uncached input | Output | Reasoning output | Complete wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no history | 4/4 | 0 | 1,419,154 | 1,291,520 | 127,634 | 9,353 | 2,513 | 281.702 s |
| full raw | 4/4 | 0 | 647,260 | 574,080 | 73,180 | 6,079 | 1,393 | 201.578 s |
| raw BM25 top-8 | 4/4 | 0 | 612,291 | 537,472 | 74,819 | 5,095 | 1,103 | 181.026 s |

Quality was again all ties. The strong no-history agent inferred both necessary decisions, so these
are not memory-dependent wins. Full raw nevertheless used 54.4% less total input and 28.4% less wall
time than no-history; top-8 used 5.4% less total input and 10.2% less wall time than full raw, although
its uncached input was 2.2% higher. Together with the valid PR-review matrix, this is a repeated
development efficiency signal with no observed quality loss. It justifies a frozen held-out test of
the already implemented top-8 baseline, not a compiler or learned selector.

## Exploratory result invalidated by repository-ref audit

The observed result below is `.local-evidence/project-agent-route-v2-development/results-v2`, but it
is no longer valid quality evidence. The first preparer used Git worktrees backed by a source clone
whose newer remote refs remained readable. A cattrs no-history agent explicitly searched `--all` and
attempted to inspect later `origin/*` versions. Even where the exact fix was not found or used, the
protocol did not prevent post-fix source access, so the complete matrix is excluded rather than
selectively retaining apparently unaffected rows.

| Arm | Checker | Severe regressions | Input | Cached input | Uncached input | Output | Reasoning output | Complete wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no history | 4/4 | 0 | 1,118,438 | 1,031,040 | 87,398 | 17,882 | 6,474 | 467.415 s |
| full raw | 4/4 | 0 | 618,976 | 551,808 | 67,168 | 9,748 | 2,460 | 278.342 s |
| raw BM25 top-8 | 4/4 | 0 | 684,743 | 619,648 | 65,095 | 9,627 | 2,849 | 280.886 s |

As an exploratory observation, all twelve agent calls and checkers completed. Every paired outcome was a tie: two necessary-update
ties and two same-topic-control ties for every comparison. There were no current-system failures,
memory-dependent wins, full-raw regressions, or retrieval misses. Top-8 selected the final correction
in both issue tasks, so its ties were not caused by dropping the update.

The no-history agents appeared to recover both fixes, but future-ref exposure prevents attributing that
to local code structure and the current request alone. These four tasks must not be reused as held-out B evidence.
The lower aggregate exploration, token and wall-time totals in the two raw arms are only a development
cost hypothesis: four tasks, sequential cache/order effects, and no crossed replication are too weak
for an efficiency claim.

## Earlier invalid interrupted result

`results-v1` is retained with `INVALID.json`. Its first checker defined callbacks with a parameter
named `state`, while the pinned Tenacity implementation calls them with `retry_state=`. Correct agent
changes were consequently misclassified. After fixing the checker, all three saved Tenacity diffs
passed the corrected stage-2 check. The run was stopped before completion and every v1 row is excluded
from quality and cost conclusions.

## Decision and next failure source

Do not implement a complex memory repair from the invalid first set or the valid all-pass matrices.
The simplest existing candidate is exact raw BM25 top-8; evaluate it under the frozen four-project
held-out protocol before changing retrieval or prompts. The preparers create standalone depth-one repositories by fetching only the declared
base; descendants, remote refs and post-fix commits are absent. Future reports must verify a known
post-fix SHA is not resolvable inside every evaluation workspace.

The next development set must bind real issue or PR review decisions whose answer is not recoverable
from the pre-fix repository: an exact policy choice, exception, name/default, or scope decision selected
by the maintainer or user among multiple valid implementations. The current request should genuinely
depend on that prior decision, paired with an explicit same-topic case where carrying it over would be
wrong. Only a repeated full-raw or retrieval failure under those conditions justifies a repair arm.
