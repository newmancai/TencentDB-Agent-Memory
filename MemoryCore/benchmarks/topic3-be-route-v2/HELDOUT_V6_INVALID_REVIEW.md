# v6 invalid review: correct partial edit without completion

Date: 2026-09-14. v6 stopped after the first no-history call timed out. It is not a Phase A
replication and contributes no quality win, loss, tie, or cost comparison.

## Exact stop state

The frozen inputs were valid before execution. The first platformdirs no-history call reached the
300-second limit, returned no final completion or usage, and did not run the checker. The runner then
started the paired full-raw call. Once the first timeout was confirmed to invalidate the entire
matrix, the operator canceled that second call at 191.242 agent seconds and stopped the remaining
queue. No hpack, PrettyTable, or importlib_metadata model call occurred, so those three families and
their prompts remain unexposed.

| Cell | Agent status | Formal checker | Usage | Formal reading |
| --- | --- | --- | --- | --- |
| platformdirs / no-history / first task | timeout at 300.005 s | not run | missing | indeterminate execution |
| platformdirs / full-raw / first task | operator canceled at 191.242 s | not run | missing | indeterminate execution |

The runner correctly wrote `indeterminate`, not a memory win. Its execution-failure list exposed a
smaller reporting issue—identical task IDs were ambiguous across arms—so future summaries now prefix
the arm. The frozen v6 summary remains unchanged.

## Failure mechanism

Both agents had already implemented the target source behavior and were continuing repository work.
The no-history log shows focused smoke checks passing, followed by additional test/doc edits and a
final file-change operation when the deadline killed the process. The full-raw log shows source
compilation and focused behavior checks passing, then more tests, changelog work, and final review
before operator cancellation. This broad platformdirs task changed up to five files in no-history and
four paths in full raw despite a two-source-file target.

An audit-only run of the frozen stage-one checker on the quiescent partial workspaces returned
compatibility pass / behavior pass for both arms. Those checks explain the operational failure but
cannot replace the missing formal checker, completion receipt, or usage. They also show that v6 did
not observe a memory-dependent quality split.

## Isolation and decision

Both raw event logs exist and contain no model web-search event, remote command, product-checkout path,
checker path, result path, or sibling arm. Both receipts report the filesystem wrapper. No actual
visibility violation was found.

Do not rerun platformdirs, raise its timeout, or count the post-hoc passes. For the next clean matrix,
reuse only the three families no model saw and add one new small family. Every current task must limit
the edit to its named source file, forbid adding tests/docs/changelog, request at most one focused
smoke check, and require the agent to stop after the source decision. This is a prospective execution
contract, not a post-hoc relaxation of v6.

The observed timeout also supplies concrete E evidence: a correct quiescent partial edit cannot use
the product's existing `check-run`, which requires a completed agent checkpoint. Treat explicit
incomplete-run checking as a bounded recovery candidate after the clean B replication, without
automatically accepting partial edits.

Raw evidence is at `.local-evidence/project-agent-route-v2-heldout-v6/results-v1`. The frozen receipt
and summary SHA-256 values are `21a3eb3b72a0a766b5220ba8d5d735aa1aa17bb379d7acfc71327ab43e7f872f`
and `d883277fff85456ccea56684989be2c25be623cf90a32bcabe1a6d55d6eb22e4`.
