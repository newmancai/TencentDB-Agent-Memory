# v7 invalid review: edit-scope enforcement missing

Date: 2026-09-14. v7 was stopped after 11 of 16 scheduled calls because the runner recorded but did
not enforce the frozen single-source-file contract. The matrix is invalid and contributes no formal
replication, including its apparent importlib_metadata split.

## Exact stop state

- hpack and PrettyTable each completed all four calls. Both first tasks tied and both cumulative
  controls passed; all eight cells changed only their declared source file.
- importlib_metadata no-history completed its first task, changed only the declared source file, and
  failed target behavior without a compatibility-severity return.
- importlib_metadata full-raw completed and passed the behavior checker, but also left two untracked
  `__pycache__` directories. That violated the frozen instruction forbidding generated files and
  edits outside `importlib_metadata/__init__.py`.
- The runner had already started the full-raw control when the scope defect was confirmed. It was
  operator-canceled at 17.586 agent seconds. The no-history control and both zipp tasks never ran.

The frozen summary reports one `memory_dependent_win` because its checker pass did not include the
declared edit scope. Do not quote that field or the partial arm totals. The 11 receipts remain useful
only for diagnosing the checker and task mechanisms.

## Diagnostic mechanism

The no-history importlib_metadata edit replaced a missing source with an empty string and returned an
empty metadata message. That is locally plausible but violates the accepted API decision to return
`None`. Full raw applied the optional return and public type change recorded in prior history. This is
the same kind of decision disambiguation seen in valid v4 and invalid v5 diagnostics, but its output
also violated the file-scope contract. A favorable behavior assertion cannot erase that regression or
repair a checker missing an acceptance condition.

The unwanted bytecode arose during the agent's focused Python smoke check. Future isolated calls now
set `PYTHONDONTWRITEBYTECODE=1`, and the runner prospectively checks every porcelain change against the
declared file/directory prefixes. Any extra path makes `checker_pass=false` and
`severe_regression=true`; execution failures remain arm-qualified indeterminate rows. Five route-runner
tests and 21 project-agent tests pass after these changes.

## Isolation and decision

The 11 event logs contain no model web-search event, visible benchmark checkout, checker/result path,
or sibling arm. No isolation leak was found. The failure is output-contract enforcement, not input
contamination.

Do not rerun hpack, PrettyTable, or importlib_metadata and do not reuse their partial favorable rows.
zipp received no model call and may remain in a new protocol. A clean replacement needs three new
single-file families plus zipp, base/head/equivalent behavior preflight, frozen allowed-path
enforcement, and the same two arms. If evaluation-integrity failures continue, stop constructing more
replay matrices and prioritize the explicit incomplete-run recovery path before more B claims.

Raw evidence is at `.local-evidence/project-agent-route-v2-heldout-v7/results-v1`. Frozen receipts and
summary SHA-256 values are `cc05b89926ed8d52e418a4aa64d1feadd260f7116008da3a5d76ba033313b240`
and `6f516d78fe11c4c6ab9f0d3cecf1afc27f84576ad62f7d052a87aa4d648fdbef`.
