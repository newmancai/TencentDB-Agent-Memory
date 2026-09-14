# Replacement held-out v2 invalidated by cross-arm visibility

Date: 2026-09-14. The frozen v2 manifest, eight completed receipts, one interrupted call, and all raw
events are retained for audit. None is held-out quality or efficiency evidence.

## What happened

The run completed the two urllib3 tasks across three arms and the Starlette necessary-update task for
`raw_full` and `raw_top8`. While the next `no_history` call was running, its raw Codex events showed
that it walked upward from its absolute workspace, searched the shared `.local-evidence` root, and
read the completed Starlette `raw_full` diff, task, retrieved context, prompt, and checker result. It
then copied the accepted implementation shape. Independent Git clones and disabled remotes prevented
future-revision leakage, but did not prevent filesystem reads across benchmark arms.

The owned runner and remaining Codex process group were stopped before a ninth receipt was written.
The apparent urllib3 win (`raw_top8` passed while `raw_full` timed out) and the apparent Starlette
top-8 efficiency saving are excluded with the rest of the matrix. urllib3, Starlette, AnyIO, and Trio
are all treated as exposed because the agent could search the frozen manifest and checker sources.

This invalidates the v2 held-out set, not the raw-top-8 implementation. A retrospective scan of the
earlier route-v2 development event logs found no command or tool read of a sibling arm or route-v2
checker. Those development results remain diagnosis-only evidence; prospective matrices now require
enforced filesystem isolation rather than relying on agents not to search.

## Correction implemented

The installed-CLI adapter now has an opt-in `bwrap` wrapper used by the route-v2 runner. It mounts the
host root read-only, hides the entire research workspace, and rebinds only the current independent
clone at its original path. The current agent cannot see benchmark code, receipts, or sibling clones.
Codex receives a fresh writable runtime and `.codex` directory with only its bootstrap credential and
configuration files bound read-only.

Twenty project-agent tests pass, including an executable mount-visibility test. A real Codex CLI
preflight on an already exposed AnyIO clone confirmed that the main research checkout and sibling arm
were absent while the current Git clone remained usable. The preflight used 28,371 input tokens,
24,448 cached input tokens, 261 output tokens, no reasoning-output tokens, and 22.741 seconds; it is
infrastructure validation, not a benchmark row.

The next held-out attempt must use four new project families, execute every model call through this
wrapper, and automatically scan raw events for forbidden absolute paths before accepting results.
