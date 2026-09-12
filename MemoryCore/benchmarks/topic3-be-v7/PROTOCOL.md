# B v7: controlled feedback examples on fixed native targets

Before outputs, 2026-09-12. Freeze v6 single-target prompt, lossless spans, cap8,
native original write/readback and A/B/C output. No new E policy or fact extraction.
Select ALL remaining knowledge-update rows after rank40 in the existing v2 hash
order/exclusions, plus the same number of single-session-user rows at ranks40
onward. Keep missing pairs and all failures. Do not replace based on outputs.
This is a larger predeclared development cohort, not unseen-answer evaluation:
all500 LongMemEval oracle questions were historically used. Privileged pair
selection still uses offline support annotations; no discovery claim.

Freeze4 examples from v6 BEFORE new predictions: first2 consensus-changed targets
and first2 targets from consensus-same pairs in hash order, one per source pair.
Selection uses prior independent assistant silver, not v6 model correctness. The
same negative target is not treated as human gold; its source/support remains
auditable. Mix final example order by hash, no class-order cue. Examples contain
full old/later context and exact target. Labeled version adds only relation A/B/C;
unlabeled is byte-equivalent JSON after removal of that field. No rationales.

Arms: none, unlabeled, labeled. Same runtime target/evidence/model/max8tokens;
the same examples appear in both example arms; only labels differ. Per-target
execution order rotates. Fixed Qwen3-4B local model. This is bounded in-context
adaptation from controlled assistant-silver feedback, NOT online trusted E or
training weights. No evaluation silver is fed to runtime; no case retrieval,
threshold fitting or post-output prompt updates. No-example also receives the
shared instruction explaining examples, to avoid confounding that instruction.

Primary contrast labeled vs unlabeled, then none. Report pair agreement, actual
changed target coverage, all alarm locations/false-alarm audit, abstention and
cost. Report matching and differing silver interpretations separately. Duplicate
texts/source overlap with examples must be disclosed, with no-leak sensitivity
where applicable; do not quietly change cohort. Do not treat support-turn labels
as expired-memory labels. Source-only review is fallible assistant silver.

Learning cost: audit/example selection is not free. Count example input tokens
on every call and all model costs. Prior v6 calls can be shown as acquisition
overhead but are not automatically necessary online learning costs. No claimed
break-even without a stated acquisition-cost assumption. No synthetic main data.
Stop at this cohort; inspect whether labels add benefit rather than adding more
prompt fields or selecting a favorable tiny slice.
