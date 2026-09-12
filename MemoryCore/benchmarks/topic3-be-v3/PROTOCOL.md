# B current-applicability qualification v3

2026-09-12, before outputs. Scope: improve semantic feedback for a supplied
old/later source pair. No autonomous discovery, QA gain, policy learning or
persistent-update claim. All LongMemEval oracle questions were previously used;
this is development reuse, not held-out generalization.

Select next eight knowledge-update and eight single-session-user rows by the v2
hash order after excluding the same eight earlier full-s IDs. Use ranks 8:16;
keep missing pairs missing. Reuse v2 conversion and privileged supporting-turn
pair selection, disclosed as known-target diagnosis. No question, answer, category
or support flags enter B. Runtime gets opaque ID, full old/later user text and dates.

Three frozen prompts use one local Qwen3-4B-Instruct-2507 call per pair, greedy,
max256 tokens each, rotating execution order. Same final schema and same evidence.
Direct: ordinary replacement judgment. Roles: prior v2 historical/current roles
reasoning in instructions. Grounded: explicitly extract matched subject/property,
scope and old/new supported propositions before judging current applicability.
All outputs include old/new exact quotes. Quote validation is provenance only;
not semantic truth. Report raw decisions separately from contract failures.
Relation changed means a matched current value/use is replaced or withdrawn;
same means no established replacement (including addition); unknown is ambiguity.
Clearly different subjects/attributes/scopes count as same (no replacement of the
old target); uncertain alignment counts as unknown. This clarification and the
non-object JSON guard were added in independent review before any model outputs.
This is narrower than general lifecycle labels or general contradiction detection.

Independent assistant review sees only source pairs, not questions, gold or model
outputs, and records relation plus rationale. It is fallible silver annotation,
not human gold or calibrated confidence. Ambiguous cases remain unknown. Primary
comparison: relation agreement and changed precision/recall conditional on these
supplied pairs; show full confusion and paired wins/losses. Costs include every
call and errors. No synthetic examples in the main results. Do not train on these
annotations or revise prompts after viewing outputs. If disagreement concentrates
in scope ambiguity, inspect it rather than relabel to reward an arm.

This stage isolates whether explicit evidence interpretation helps beyond a role
prompt. It does not test verified-example learning. Continue to that stage only
if supported by results; preserve negative evidence without repeated prompt edits.
All three arms request the same structured fields. Thus this is a decomposition
instruction ablation, not an independently verified grounding architecture.
Actual input/output costs may differ despite the common output cap.
