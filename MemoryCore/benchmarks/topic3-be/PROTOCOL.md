# Topic 3 B+E delivery protocol v1 — 2026-09-12

This protocol is written before the new candidate/model results. It supersedes no
historical experiment. The deliverable is a bounded, optional MemoryCore sidecar,
not a claim of commercial readiness or reliable autonomous deletion.

## Public main experiment

Use PersonaMem v1 32k, MIT, revision a8076d5608c93ba2a28983cd78aa99b01a163ae7.
Exclude personas 0 and 1 used in the old failed prototype. Sort the remaining
personas by SHA256(`topic3-be-v1:` + persona_id): first six are development, remaining
twelve evaluation. Per persona choose the first hash-ordered question in each of
`track_full_preference_evolution` and `recall_user_shared_facts`. Missing categories
remain missing; do not replace according to answers or outcomes. These are public
synthetic long dialogues, not self-authored test conversations or coding results.

The adapter retains all chronological messages before the official question
boundary in L0. User messages are divided losslessly into <=1600-character records
and written via the existing episodic L1 writer in ALL arms. This is source-text
storage, not learned L1 extraction. System persona summaries are excluded.
Answer labels and question category never reach candidate selection or models.
Options reach only the answer reader. Record actual source lengths and overlaps.

Native FTS retrieves 12 records for the public question. Generate at most two
different-target old/new sentence pairs from these records: strictly later same
owner sources; sentences 30..500 characters; at least two shared non-stopword
tokens; rank by token intersection / union, then stable identity. No gold-based
pair selection. Candidate recall outside this bounded pool is unknown.

## B, E, and the actual adaptive state

B uses a pinned independent pretrained DeBERTa NLI contradiction score on the
source sentence pair. This is NOT a calibrated probability of memory expiry.
E is a separate local Qwen3-4B source-relation reviewer that sees both complete
source chunks, exact sentence offsets, and chronology. It emits
`changed|same|unknown` with exact pair identity. It can be wrong; a source read
and valid JSON do NOT make its semantic verdict ground truth.

Development runs E on every candidate. Its normal verification receipts update
four bounded score bins. The adaptive B estimates each bin's E-changed rate;
with >=3 observations it skips a bin if `4 * changed_count < observation_count`.
Unseen/undersupported bins always verify. Counts saturate at 1024 and are isolated
by source/verifier version. Freeze the policy before evaluation. E unknown and
read failures never train a same label. Policy cost is counted, including cold
start; no evaluated QA labels are used to train B.

Base: native 12-result source-text recall. Fixed B+E: check all candidates.
Adaptive B+E: same candidates and E, selected by the frozen feedback policy.
E changed replaces only the exact old span in the auxiliary view with a historical
annotation plus the later assertion, preserving the rest and immutable originals.
Same/unknown/failure makes no lifecycle change. Replacements are written and read
back in a separate native SQLite store before a single-writer atomic manifest
publication. No production stores or default hooks are modified.

## Evaluation

Use the same greedy Qwen reader, 12 results and output limit for all arms. Identical
requests may reuse outputs, disclosed separately from logical per-arm costs.
Report official MC-letter accuracy, paired wins/losses, verifier coverage within
the candidate pool, observed B-to-E agreement, lifecycle changes, full-span
preservation, original history, token totals and p50/p95 measured latency. NLI,
E, reader, learning acquisition and persistence costs are separate. Do not equate
candidate-pool coverage with global stale recall or label-match with task causality.

Audit every candidate pair against its visible source text, separately from the
QA labels. Record a single-pass assistant source audit, NOT human/double-blind
gold. Use changed/same/unknown; report E disagreements and wrongful historical
annotations with this limitation. QA correctness is the independent public label
endpoint. Evaluation labels cannot enter the runtime or frozen policy.

## Required delivery checks

Test disabled/read-failed/timeout/corrupt/stale-version/foreign-scope fallback
against the identical native baseline, late verifier completion without mutation,
restart, duplicate updates, capacity, feedback identity, unknown exclusion from
learning, and unrelated content preservation. A second neutral JSON adapter and
LongMemEval adapter establish schema separation; only PersonaMem is this main run.
Run repository tests and plugin build on the delivery checkout. Preserve failures
and negative results; no seed, pair rule, prompt or threshold tuning on evaluation.

## Recorded implementation notes (after the main run; no prediction retuning)

The literal span replacement now uses a function replacement so JavaScript `$&`
and `$'` text is preserved verbatim. Source IDs are validated as nonempty and
target/source records must differ. Repeated-target updates use newer source order
and bound total historical records. These fixes do not change any of the 72 main
candidate transformations; the preserved native outputs are checked in a fresh
process. Model readiness is checked before starting the task loop. Failed reader
receipts remain charged in the scorer. The 16-token reader budget, all model
prompts, split, candidates and policy rule are unchanged.
