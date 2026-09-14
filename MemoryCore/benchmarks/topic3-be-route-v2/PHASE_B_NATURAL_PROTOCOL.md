# Phase B protocol: prospective natural project-memory validation

Date: 2026-09-14. Status: **collecting, 0 eligible sequences**. Phase A opened this stage through valid
v4 and v10 matrices. This protocol is frozen before any Phase B outcome and does not convert earlier PR
replays into natural data.

## Project and unit

The maintained project is this product worktree and its MemoryCore code. The independent unit is a
user-authored project decision followed later by a genuinely requested related coding task. Episodes are
grouped by decision thread; multiple later checks caused by one code patch do not create extra units.

An episode is eligible only when all conditions hold:

1. the user explicitly corrects, replaces, narrows, or confirms a concrete project behavior or scope;
2. the exact user text and timestamp are recorded before the later task exists;
3. a later related coding task arrives naturally from the user, not from an evaluator searching for a win;
4. clean and raw-full arms start from the same recorded Git revision in separate marked worktrees;
5. the task, allowed paths, behavioral checker, and severity boundary are frozen before either arm output
   is opened;
6. neither arm can see the other, future revisions, research evidence, checker source, or network search.

Broad goals, assistant conclusions, public PR answers, synthetic follow-up prompts, evaluator-generated
corrections, and any previously exposed benchmark family are ineligible. If code already makes the user
decision unambiguous, the episode remains eligible and may tie; it must not be discarded.

## Arms and execution

- `no_history`: same model, base, project guidance, prompt, and checker, with project memory disabled.
- `raw_full`: default product behavior, using only verbatim eligible user observations with source and
  version chain; no automatic compilation, learned selection, or stale inference.

Use the current Codex execution base in both arms at episode time and record requested model/effort,
CLI version if available, usage, cache tokens, context bytes, wall time, exit state, diff, checker output,
and visibility audit. Execution failure is indeterminate and invalidates a paired episode; it is not a
quality loss. Undeclared paths stop that episode immediately.

After both benchmark arms are sealed, normal project work may adopt the user-accepted implementation;
benchmark worktrees remain evidence and are never recycled as a new episode.

## Required sample and controls

Collect at least 10 eligible sequences across at least four independent decision threads. At least three
must be naturally occurring scope-negative or same-topic controls where the prior correction should not
change behavior. Controls may not be manufactured merely to reach the quota. Until all counts are met,
the status remains incomplete regardless of favorable early rows.

Primary outcomes are repeated-decision error avoided, prior decision misapplied, control regression, and
severe compatibility regression. Cost is secondary. A valid Phase B success requires:

- raw-full avoids a no-history repeated-decision failure in at least two independent decision threads;
- raw-full has no decision-thread loss, no scope-negative control regression, and no severe regression;
- every included episode satisfies the prospective eligibility and audit contract.

Otherwise keep full raw experimental, classify the failure, and do not enter open-source comparison or a
more complex mechanism automatically. Report all eligible episodes, including ties and unfavorable rows.

## Evidence registry

The prospective registry is [phase-b-natural-registry.json](phase-b-natural-registry.json). Append only
after eligibility is established; never delete an eligible row because of its result. The registry stores
verbatim-text hashes and local evidence paths, not secret credentials or unrelated conversation content.
