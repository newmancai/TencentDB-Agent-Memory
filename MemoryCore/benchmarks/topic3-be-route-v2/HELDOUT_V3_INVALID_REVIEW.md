# Filesystem-isolated held-out v3 invalidated by model-side web search

Date: 2026-09-14. The frozen manifest, interrupted first call, and its raw events are retained for
audit. No v3 row is held-out quality or efficiency evidence.

## What happened

The first matrix call was pytest `no_history` on the failed-mutation undo task. The outer `bwrap`
view worked: the agent could see its current clone but not the benchmark checkout, evidence root, or
sibling workspaces. However, Codex emitted three native `web_search` tool events and searched public
GitHub for the exact MonkeyPatch failure and implementation. Filesystem isolation cannot constrain a
server-side tool.

The owned runner and its Codex process group were stopped before the first receipt was written. The
pytest family is exposed. Packaging and Flask received no model call and remain eligible for a new
freeze. h11 was subsequently named in a deliberate negative search preflight, so it is also treated
as exposed. The whole v3 matrix is excluded rather than retaining a convenient subset.

## Correction implemented

The controlled Codex adapter now passes `web_search="disabled"`, hides the user's Codex
configuration inside the outer mount, and binds only the authentication file needed to start the
CLI. The route runner also treats any `web_search` event in raw output as a visibility violation and
stops the matrix.

Twenty project-agent tests and two route-runner tests pass. A real negative preflight in the already
exposed h11 clone explicitly demanded a web search for PR #181; the model returned
`SEARCH_DISABLED`, emitted no web-search event, and left the workspace unchanged. It used 30,556
input tokens (14,720 cached), 107 output tokens (40 reasoning), and 21.811 seconds. This is isolation
evidence, not a benchmark result.

The next held-out freeze may reuse only the unexposed packaging and Flask families, must add two new
families, and must retain both layers: filesystem isolation and explicit model-tool denial.
