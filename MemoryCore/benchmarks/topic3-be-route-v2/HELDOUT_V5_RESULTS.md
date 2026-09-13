# Lossless full-raw replication v5 results

Date: 2026-09-14. **This matrix is not an admissible Phase A replication.** All 16 scheduled
calls left receipts, but the two jsonschema no-history calls reached the 300-second deadline and
never ran the frozen checker. The pre-registered long-term contract says that any execution failure
invalidates the matrix. Timeout rows are missing quality observations, not losses for no-history and
not wins for memory.

## Formal outcome

The frozen manifest and checker still have SHA-256
`86b275635b621fb306045cba769cc075d137ec8fc01a980d741dbe8adbc3edf0` and
`56c4789ab1fd35cf9dce3db78c4a598dd930bbd5a9171bc56424d572f3dbd3b3` respectively. The final
receipts and summary hashes are `1850443ab8f046ce5a48d4e01cd1b8844534ab30fa8b337bb1edf3b3c95d8200`
and `5feaeda3d9e5dbc9f38ca5cada00cd4ceecd2adf2f87998ab4478011fd63c942`.

| Project family | First necessary task, no history | First necessary task, full raw | Accumulated control | Family reading |
| --- | --- | --- | --- | --- |
| Websockets | completed, behavior fail | pass | no-history fail; full raw pass | behavioral split in favor of history |
| jsonschema | **timeout; checker not run** | pass | no-history timeout; full raw pass | indeterminate execution, not a quality win |
| Scrapy | pass | pass | both pass | tie |
| wsproto | completed, behavior fail | pass | both pass | behavioral split in favor of history |

Full raw completed and passed 8/8 checks. No-history produced six completed/checkable calls, three
passes, three behavior failures, and two execution failures. There were no compatibility-severity
return codes. The frozen `summary.json` mechanically labels five rows as wins, including both timeout
rows and the accumulated Websockets control. That aggregation is not an admissible interpretation.
Only the two completed first-task splits above are direct quality observations; they remain useful
diagnostic evidence inside an invalid replication matrix.

An audit-only checker run after the matrix found that the jsonschema timeout workspace still failed
both stage-one and stage-two target behavior while preserving compatibility. This explains the
partial state but does not retroactively turn either timeout into a formal checker result.

## Observed mechanisms

In Websockets, no-history chose a plausible Latin-1 decode and insecure header insertion. It changed
the returned value from surrogate-escaped bytes to Unicode characters, contrary to the maintenance
decision. Full raw retained `decode("ascii", "surrogateescape")` and changed only insertion to
`set_insecure`, which accepted obs-text while preserving the required representation.

In wsproto, no-history changed one parser caller to raise `RemoteProtocolError` with a hint but left
the error constructor's `event_hint` optional. Full raw applied the earlier project-wide decision at
the constructor boundary and made the parameter required while preserving explicit hints and local
errors. The following control passed in both arms, so this is one first-task split, not two wins.

These two cases strengthen the mechanism hypothesis from v4: exact prior maintenance decisions can
disambiguate a locally plausible implementation. They do not satisfy the promised independent
replication because the matrix-level execution contract failed.

## Cost and isolation audit

| Arm | Scheduled calls | Completed/checkable | Known input | Known cached input | Known output | Known reasoning | Wall sum | Context bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no history | 8 | 6 | 1,938,853 | 1,734,656 | 22,313 | 7,324 | 1,277.754 s | 0 |
| full raw | 8 | 8 | 2,264,126 | 2,037,376 | 26,330 | 8,552 | 876.921 s | 16,540 |

No-history usage is missing for both timed-out calls and its wall sum includes two 300-second
deadlines. Therefore neither token nor latency totals are comparable and no saving or overhead claim
is made. Every cell still represents one run only.

All 16 event logs exist, all receipts report the outer filesystem wrapper, and no model web-search
event, benchmark checkout, checker, results directory, or sibling arm appeared in an agent log. A
same-construction namespace probe confirmed that the main product checkout is hidden. Three agents
issued broad-path or remote commands: broad paths resolved only to the current rebound clone, while
`git ls-remote` and `curl` failed to connect and returned no remote source. These attempts are retained
in the raw logs rather than silently omitted; no obtained cross-arm or future information was found.

## Decision

Do not advance to natural sequential-use validation and do not rerun or raise the timeout on these
exposed projects. Preserve lossless full raw as an experimental default candidate, with v4 still the
only fully admissible matrix. The next Phase A attempt must use new families, smaller checkable tasks,
two arms only, and a summary schema that records execution failures as `indeterminate` rather than
quality losses. The runner was corrected after v5 for that reporting error; the frozen v5 summary is
left unchanged as evidence.

Raw evidence is at `.local-evidence/project-agent-route-v2-heldout-v5/results-v1`: exact prompts and
contexts, 16 event logs and receipts, checkers, usage where available, and cumulative workspace diffs.
