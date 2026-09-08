# STALE raw-observation semantic challenge v1 (before model outputs)

This complements the executable-receipt subclass. It does not assume STALE's commonsense
implications are logically necessary or suitable for automatic commercial invalidation.

Fixed official source revision 617c51dc200b5ab09970834144c7e51c77959af0. Select 24 eligible T1
and 24 eligible T2 cases by normalized-old-observation hash, one per exact old-observation group.
Round-robin groups into development/calibration/heldout (16 each). Labels and gold explanations
are separate. Shared distractors mean this is not globally source-disjoint; report that limitation.
No claims of statistical coding-business generalization from these 48 public synthetic cases.

Evaluate at the actual user turn containing the annotated later observation. Before that turn,
all raw USER history is stored as <=1600-character records with identity and chronological order.
Selection of the observation boundary is offline protocol sampling, not online conflict detection.
B sees the later raw turn and native retrieval candidates, not the canonical M_old/M_new pair,
the target-session indexes, type, explanation or answers. The public dim1 query is reserved for
the subsequent reader, not for B candidate retrieval. Source alignment strips punctuation only
offline for mapping: it never changes runtime text or validates a model proposal.

First measure whether native retrieval even contains an annotated target. Report target-localized
feedback, misses, abstention and off-target proposals. Off-target does not automatically prove a
false invalidation: other distractor claims lack exhaustive labels. Inspect accepted proposals.
Public-label agreement is separate from confidence suitable for commercial actions.

No model outputs have been inspected. Candidate model is official Qwen3.5-9B, revision
c202236235762e1c871ad0ccb60c8ee5ba337b9a, isolated dependency/model directories. Download and
runtime compatibility remain to be verified. Freeze inference prompts and budgets before runs.
This protocol is incomplete until baseline, B, calibration and native E reader comparisons run;
do not mark the persistent goal complete based on prepared inputs.

## Calibration rule fixed before inference

Run the same direct/relations prompts independently on development, then calibration. Before
any heldout inference, select the smallest threshold in {0, .5, .7, .8, .9, .95, 1} with at least
five accepted calibration proposals and at least 90% agreement with the annotated target IDs.
If none qualifies, the corresponding calibrated arm abstains on all heldout cases. Do not change
the prompt or threshold rule in response to heldout results. Report both raw arms and calibrated
heldout results, including zero coverage and malformed outputs. Candidate misses stay in the
denominator. `calibrate.py` only uses calibration rows to select and cannot overwrite a policy.

This is a benchmark localization selection rule, not a calibrated probability of semantic truth.
Positive-only labels, 16 calibration cases and shared noise cannot support a commercial false
invalidation claim. Consequently this semantic experiment produces review proposals, not
automatic persistent invalidations. Native executable-receipt E and subsequent public reads
are reported separately; do not disguise their verified evidence as general semantic capability.

## Retrieval v2: fair native hybrid baseline (before judge outputs)

The FTS-only development recall was 8/16. A local Qwen3-Embedding-0.6B model was already
available, so v2 restores the base's existing vector + FTS RRF ability without changing either
engine. `embed.py` uses the model card's normalized last-token embedding, 1024 dimensions,
with one generic query instruction for every case. No gold, old/new canonical pair, category,
or sample-specific query rewriting is provided. Native `retrieve-hybrid.ts` writes actual vectors,
reruns FTS and hybrid on the same store and returns exactly eight candidates for both.

Development FTS repeats at 8/16 and hybrid reaches 10/16. Keep the native default fusion and
candidate count; no per-case patch. Judge direct/relations arms will use the same v2 hybrid
inputs, with the unchanged calibration rule above. Preserve v1 outputs as the lexical retrieval
ablation. This is a stronger baseline, not a novel B contribution. Calibration follows the fixed
mapping; heldout semantic outputs remain unused until the policy is selected.

## Input v3: preserve public observation timestamps

STALE includes one timestamp per source session. v1/v2 retained order but omitted these dates.
v3 adds raw `observedAt` to every source and new observation for both systems; it does not change
the selected 48 IDs, text, splits, queries or labels. Native stores carry event dates in metadata,
separate from their actual ingestion timestamps. Where a database requires a timezone, the
dataset's naive timestamps use a disclosed UTC convention for ordering, not a claim about the
original user's timezone. Hindsight receives the same available event dates.

Outputs live in `semantic-v3/`. Actual text embeddings are reused because embedding input is
unchanged; FTS and native hybrid baselines were both rerun. Development remains 8/16 vs 10/16,
calibration 8/16 vs 9/16. No heldout v3 retrieval or semantic outputs have been inspected.
The direct/relations prompts and calibration rule remain unchanged, and run on common v3 input.

`model_server.py` supplies the same Qwen3.5-9B model to both systems, with native chat templates,
greedy generation, seed 20260908, no thinking, no truncation, and raw response/token/time logs.
It reuses the existing tool-envelope parser without repairing calls. Bounds are 32768 input and
16384 output tokens; B still requests 384 output tokens and checks a 12000 input cap. The server
does not implement JSON grammar enforcement. Hindsight must use its documented soft-schema
provider mode (lmstudio), not receive an unimplemented strict-output promise. Backend contract
failure is reported as such, not scored as evidence that Hindsight's memory method failed.
`infer.py --endpoint` checks the returned prompt token count against local native-template
tokenization. Endpoint wall time and server generation time are separate accounting measures.
Implementation is syntax-checked only; actual model loading and endpoint compatibility remain
unverified until weights finish downloading.
# v4 development optimization after v3 failure

The completed v3 development comparison (same hybrid candidates, Qwen3.5-9B)
localized 3/16 for direct and 1/16 for relations, accepting 16 and 12 respectively.
All model confidence scores were 0.95. Relations cost more and is not adopted.
Off-target remains benchmark disagreement, not a proven semantic false-positive.

`assertions-v4.json` changes the representation of feedback: distinguish current
fact transitions from request/task progress, coexistence and insufficient evidence.
Require actual old/new assertion spans and an incompatibility explanation for a
fact target. Exact quotations are only an alignment check, not proof of a true
transition or calibrated confidence. This addresses observed invention of premises
from questions and preferences for recent requests. No case IDs, benchmark types,
labels, topic-specific words or heldout outputs enter the rule.

Run only development first, using the same v3 candidates/model/384 output cap;
save outputs separately under semantic-v4. The unchanged direct/relations v3 runs
remain the measured comparator; preserve their raw inputs/outputs and costs. If
candidates/model change, rerun those affected comparators. V4 must improve useful
coverage and localization rather than winning by abstaining on everything.
# v5 model-capability correction, before v5 outputs

Official downloaded Qwen3.5-9B README Best Practices recommends sampling for
thinking tasks: temperature 1, top_p .95, top_k 20, presence penalty 1.5. The old
greedy/no-thinking setting was a reproducibility choice, not that recommendation.
V5 uses those sampling settings with seed 20260908, thinking enabled, same model
revision and candidates, and 4096 total output tokens per B call. That cap is a
local cost constraint, below the model card's general 32768 recommendation;
unfinished reasoning/length exits count as incomplete output, not abstention.

`comparison-v5.json` contains unchanged direct and assertions prompt texts.
Both are rerun under the same generation settings. V3/v4 results remain separate;
an improvement over them cannot be attributed solely to the B method. All thinking
tokens and generation time are retained in shared service receipts. The final
message excludes the native reasoning segment; no final JSON/tool-call repair is
performed. Sampling is seeded per call; this is not a guarantee of reproducibility
across GPU/library versions.

The assertion witness check permits only curly/straight quote and whitespace
equivalence, retaining the raw model quotation and recording alignment kind.
Negative checks preserve negation, numeric value, subject and modality differences.
V4 exact-check results are not overwritten. Alignment is not semantic verification.

Hindsight v5 must use `--generation-profile thinking-v5` and the same shared server.
The interrupted greedy bank cannot serve as a v5 baseline because its extracted
facts were produced with different model settings; retain it as an interrupted
attempt with recorded cost. A fresh v5 bank is required by this configuration
change, rather than silently mixing old and new derived facts. It has not run yet.
