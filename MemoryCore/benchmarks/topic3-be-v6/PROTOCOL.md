# B v6: verbatim targets, no fact rewriting

Written before outputs, 2026-09-12. Fixed next ranks32:40 per v2 stratum with same
exclusions/adapter/privileged pair selection. Development reuse: all500oracle
questions historically exposed. No train/test/generalization or discovery claim.
No QA/gold/support metadata in B input. Missing pairs remain missing.

Write the complete old user source to native MemoryCore L1, read back by exact
record ID/version/content. Form verbatim sentence spans with v4 lossless splitter;
skip whitespace-only segments, preserve all text and original offsets. At most
first8 nonempty spans become targets; report omitted spans. Later source is
context, never used to rewrite/select old spans. Span-level record pointers refer
to the same native original; no new extraction model or engine changes.

Compare one whole-old-record judgment vs independent judgments on each verbatim
span. Same model/prompt/full source context and output interface; only target
text/ID differs. Output a single A/B/C (changed/same/unknown), max8tokens. No
generation repair or accepted explanations. No invented subject/old_fact fields.
The host owns target identity and maps the label back to immutable text. Evidence
is the supplied later source; this is not precise later-clause localization.

A means later evidence replaces a current-valued fact/use asserted by the target
under the same subject/property/scope. B means no supported replacement, including
addition/different scopes or a target that merely asks a question. C means uncertain
alignment. Explicit ongoing needs/goals may change; topic turnover alone does not.
Aggregate per-span labels existentially (anyA, else anyC, elseB). A multi-fact span
can still be ambiguous: audit target support, not only pair label. Invalid output
is operational unknown with error retained, not successful semantic abstention.

This isolates immutable verbatim target granularity with constant evidence and
fixed labeling prompt. Span arm costs more calls and input tokens; it is not
equal-budget superiority. Whole-record is a necessary simple baseline. Do not
claim a benefit over prior JSON prompts from this new cohort. Stop after this
bounded cohort; inspect the mechanism before any feedback learning or larger run.
Two independent source-only assistant silver reviews, without QA/gold/model,
plus separate post-output target localization audit. Keep disagreement and
duplicate text. Report accuracy/coverage/false alarms/cost; no high-confidence
claim based on this silver. No persistent E update or new policy default.
