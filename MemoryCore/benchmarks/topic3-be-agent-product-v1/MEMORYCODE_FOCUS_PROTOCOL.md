# MemoryCode quality-first focus comparison

Date: 2026-09-14. The existing complete-update Codex diagnostic exposed one real miss in a 40-session
dialogue: full raw history contained the active variable suffix but the generated code omitted it. This
comparison tests one direct repair before any AI-infra cost optimization.

## Method

`raw_full` receives the complete verbatim history and current request exactly as before. `focus_raw`
first asks the same Codex model to extract the latest explicit coding guidelines from prior history only,
then supplies both the unchanged verbatim history and that focus list to the coding call. The focus list
is navigation, not evidence replacement. It receives no target regex, instruction ID, source-session label,
or expected code.

The first disjoint comparison (`v1`) found a real compiler error on the 100-session item: it kept the
latest method suffix but discarded the independently active method prefix, substring, and digit rules.
The `v2` compiler therefore treats object type and rule category separately. Prefix, suffix, required
substring, digit, and capitalization can coexist; an explicit update replaces only the same category for
the same object type. Separately named decorators and imports also coexist unless explicitly revoked.
This is a single mechanism correction from the observed failure, not a search over prompts.

The extra compiler call deliberately optimizes quality before cost. If it helps on new public data, later
AI-infra work must remove or amortize its additional non-cached input, call count, and latency without
lowering the frozen quality result.

## Disjoint quality set

Select one single-target update dialogue from each update-capable official session-count stratum
`3, 4, 5, 10, 15, 20, 30, 40, 50, 100`. The first comparison excludes all 24 dialogues from the earlier
generation subset and uses domain `topic3-be-memorycode-focus-quality-v1`. The `v2` confirmation excludes
those 24 dialogues plus all 10 first-comparison dialogues and uses domain
`topic3-be-memorycode-focus-quality-v2`. The frozen `v2` IDs are `067`, `117`, `139`, `151`, `185`, `240`,
`250`, `300`, `301`, and `352`; selection and scoring are fixed before model output.

The primary metric is strict target correctness with constructor attributes followed through the actual
first receiver argument; this fixes the known literal-`self` extractor defect before the new calls. The old
frozen target score, mean official-compatible score, and receiver-aware mean across all active rules are
also reported so a target-only gain cannot hide broad regressions. The receiver-aware aggregate follows
the constructor's actual first argument; the old official-compatible aggregate is retained to expose the
pinned extractor's literal-`self` behavior. Report paired wins/losses/ties, accuracies, usage,
non-cached input, model calls, and wall time. A timeout, missing usage, tool event, nonzero exit, or empty
output invalidates the run.

This is a public synthetic quality comparison, not a product-success rate. It is useful only if the focus
arm repairs at least one raw miss without introducing a paired loss. No result from the removed natural
validation route is involved.

## AI-infra stages

Once `focus_raw` has a frozen quality result, `focus_compact` removes the duplicated raw history from the
second model call. The compiler still receives the full verbatim history; the coding call receives only
the compiled active-guideline list and current request. This targets input-token transfer, prompt-prefill,
and wall time without changing the quality model or compiler model.

A development-only 40-session check rejected `focus_compact`: it lowered non-cached input substantially
but moved state to class attributes, missing the frozen constructor-attribute target. It is not evaluated on
the third held-out set and is not a release candidate.

`focus_cached` instead retains verbatim history in the coding call and places the identical dataset role plus
history at the beginning of both model prompts. Only the task-mode suffix differs. This allows provider prefix
caching to reuse the long prefill while keeping the same evidence available to the quality model. Its third
domain-separated set excludes the earlier 24-dialogue generation subset plus both 10-dialogue focus sets.
It is an AI-infra improvement only if it preserves or improves receiver-aware target and active-rule scores
against `raw_full` and materially lowers the focus-over-raw non-cached-token or wall-time ratios observed for
`focus_raw`; model-call count remains two until compiled state can be cached or maintained across requests.
