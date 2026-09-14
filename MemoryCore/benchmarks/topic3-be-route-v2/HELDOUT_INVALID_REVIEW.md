# First held-out run invalidated

Date: 2026-09-14. The frozen manifest and checker are retained for audit, but this run is not held-out
quality or efficiency evidence.

## What happened

The run reached 15 of 24 receipts. On `attrs-python315-message`, the raw-top-8 agent changed the test
to compute `match_name = "prefixmatch" if sys.version_info >= (3, 15) else "match"` and used that in
the expected error message. This is semantically the requested version-dependent expectation.

`heldout_checker.py` incorrectly required both the literal old message and the exact source spelling
`if sys.version_info >= (3, 15):`. It therefore returned exit 2 and labeled the equivalent change a
compatibility regression. The checker had been tested on the upstream patch and one authored stage-2
patch, but not on a second semantically equivalent stage-1 implementation. Positive-patch validation
was insufficient to establish implementation independence.

The runner and its owned Codex process group were stopped immediately after confirming the checker
defect. `.local-evidence/project-agent-route-v2-heldout/results-v1/INVALID.json` records the exclusion.
All 15 rows and partial aggregate cost are excluded; apparently passing rows are not retained
selectively. Click, HTTP Core, attrs, and MarkupSafe are now exposed and cannot be relabeled as a new
held-out set.

## Required correction

The next held-out set must use new project families and tasks. Before freezing it, each checker must:

1. fail on the declared base while compatibility passes;
2. pass the real reviewed result where one exists;
3. pass at least two materially different but behaviorally equivalent implementations when the task
   permits implementation freedom;
4. execute behavior or inspect parsed structure rather than require incidental source text;
5. keep compatibility failures limited to genuine old-behavior regressions.

No retrieval, task, threshold, or result was tuned from the invalid rows. The development conclusion
remains only that full raw and raw top-8 repeatedly showed an efficiency lead with tied checker
quality on eight valid tasks. A new held-out matrix is still required.
