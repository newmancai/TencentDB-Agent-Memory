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

The extra compiler call deliberately optimizes quality before cost. If it helps on new public data, later
AI-infra work must remove or amortize its additional non-cached input, call count, and latency without
lowering the frozen quality result.

## Disjoint quality set

Select one single-target update dialogue from each update-capable official session-count stratum
`3, 4, 5, 10, 15, 20, 30, 40, 50, 100`. Exclude all 24 dialogues from the earlier generation subset, then
use domain-separated SHA-256 ordering with domain `topic3-be-memorycode-focus-quality-v1`. Selection and
scoring are fixed before model output.

The primary metric is strict target correctness with constructor attributes followed through the actual
first receiver argument; this fixes the known literal-`self` extractor defect before the new calls. The old
official-compatible strict score is also retained. Report paired wins/losses/ties, both accuracies, usage,
non-cached input, model calls, and wall time. A timeout, missing usage, tool event, nonzero exit, or empty
output invalidates the run.

This is a public synthetic quality comparison, not a product-success rate. It is useful only if the focus
arm repairs at least one raw miss without introducing a paired loss. No result from the removed natural
validation route is involved.
