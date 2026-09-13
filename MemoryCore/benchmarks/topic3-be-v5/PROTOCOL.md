# B v5: form old targets before exposing later evidence

2026-09-12, written before outputs. Next ranks24:32 in each v2 stratum, same
exclusions, adapter and privileged source-pair construction. Missing stays missing.
All LME oracle targets are previously exposed: development reuse, no holdout or
autonomous discovery claim. Runtime never reads QA/gold/support annotations.

Three arms: v4 direct source-ID judgment (one call); joint-target extraction then
target decisions (two calls); old-only extraction then target decisions (two
calls). Joint and old-only use exactly the same extraction prompt/schema, except
joint sees later evidence as context and old-only cannot. Targets must always
describe facts supported by OLD source. Both share an identical decision prompt
and full old/new evidence. Alternate block order; Qwen3-4B greedy, max256 tokens
per call. Actual costs reported; same call count is not same input token count.

Extract up to3 compact targets: subject, attribute, scope, fact, old source IDs.
Host assigns t0..t2. Decision selects only target IDs and later source IDs, with
changed|same|unknown. It cannot mutate the old target. Host reconstructs each
feedback with the original target and checked references. Invalid/missing/duplicate
target decisions fail the contract, no late fabricated target accepted. Empty
extraction abstains unknown and skips the impossible decision call; count cost
and coverage, never score it as proof of same. Extraction contract failure also
abstains unknown but is separately an error. Pair aggregation: any changed =>
changed; else any unknown => unknown; otherwise same. This existential pair
definition is a limited diagnostic, not complete target-level correctness.

changed requires replacement of matched current property/use; same means addition
or clearly different scope; unknown means ambiguous alignment. Mere conversational
topic/request turnover is outside the enduring-memory target. Explicit ongoing
needs/goals are allowed but questions/plans do not establish achieved states.

Independent assistant source-only silver, blinded to predictions/QA, records pair
relations and reasons. Keep disagreements. After prediction separately audit old
target support and omitted changed attributes, including effects of the3-target
cap. No human-gold or calibrated-confidence claim. Primary contrast old-only vs
joint at equal logical call budget, then direct for cost/quality context. No
training, E publication, policy default, model retries or post-output prompt edits.
