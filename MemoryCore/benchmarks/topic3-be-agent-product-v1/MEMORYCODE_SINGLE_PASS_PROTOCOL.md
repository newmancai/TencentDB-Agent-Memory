# MemoryCode single-pass self-focus infra protocol

Date: 2026-09-14

## Objective

Test whether the quality-first route needs a separate compiler model call. `self_focus_raw` keeps the same
complete raw history and asks the coding call to derive the active-guideline checklist internally before
writing code. It emits code only. The corrected independent-rule semantics from the frozen two-stage
compiler are included unchanged; there is no external compiler output, second call, or compacted history.

`raw_full` is the paired baseline. Model `gpt-5.6-sol`, medium reasoning, Codex CLI `0.153.4`, 180-second
timeout, empty workspace, no tools, scorer, and receipt requirements remain fixed.

## Bounded pilot and confirmation

Pilot on three already exposed mechanisms only:

- `memorycode-339`: the original two-stage compiler regression;
- `memorycode-300`: the compact-history state-placement regression;
- `memorycode-206`: the source-only confirmation's raw failure and focus win.

Continue only if self-focus has receiver-aware target score `1` on all three, no active-rule regression,
one valid call per task, and aggregate non-cached input no greater than `1.05x` paired raw.

If it passes, select a fourth disjoint 10-dialogue set using the existing domain-separated rule, excluding
all 54 previously used dialogues before model calls. Run exactly `raw_full` and `self_focus_raw`. Do not
change the prompt or scorer after seeing confirmation outputs. Promotion requires zero target regressions,
all 20 calls valid, aggregate non-cached input and calls no greater than raw, and no material wall-time
regression. Otherwise retain the result and keep the route off.

This is public synthetic method evidence, not natural validation, a dollar-cost estimate, or a production
SLO.
