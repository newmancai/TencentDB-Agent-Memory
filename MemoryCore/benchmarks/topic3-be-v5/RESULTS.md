# v5: old-only targets and v5.1 isolated decision replay

2026-09-12. Implemented immutable target formation before later evidence and ran
the predeclared three-arm comparison. This is known-pair development diagnosis,
not learned B, autonomous discovery or unseen-answer evaluation. No E mutation.

16 selected tasks,13pairs,3missing. Two bicycle pairs have identical old/later
text with different dates:12 unique text pairs. Two source-only assistant reviews
agree on all13:3changed (only2 unique change pairs),9same,1unknown. They are silver,
not human gold. Original answers are never consumed by B. No labels were revised.

## Original strict v5 result (unchanged)

| Arm | Relation agreement /13 | Contract-valid agreement /13 | Contract failures | Calls | Input/output tokens |
| --- | ---: | ---: | ---: | ---: | --- |
| Direct | 6 | 6 | 1 | 13 | 5596/1183 |
| Joint old-target extraction | 2 | 1 | 12 | 18 | 8958/1455 |
| Old-only target extraction | 3 | 2 | 11 | 26 | 11595/1575 |

Unique-text agreement: direct5/12, joint2/12, old-only3/12. Joint has only12 accepted
targets because many whole-extraction failures prevent the second call. Old-only
has32 accepted targets and no extraction contract failures. No empty-target
abstentions and no output truncation. Do not mistake operational unknown for a
correct semantic uncertainty judgment (valid agreement is separately reported).

57 actual model calls,26149 input/4213 output tokens,145.557s generation service.
Direct41.750s,joint49.194s,old-only54.613s. Loading and source review are additional.
Both extraction arms have a maximum2-call budget, not identical actual cost.

## Interface error found and corrected separately

The initial batch contract was too strict. An unrelated target's unknown without
new_ids, or a missing target decision, discarded valid judgments for other targets.
Independent diagnosis found decision_schema cases were omitted evidence fields
for unknown, not attempted target rewriting. new_source failures included empty
arrays. This is an implementation mistake, not evidence against the semantic
old-only hypothesis.

The v5.1 replay is explicitly post-output development, documented before replay
scoring in REPLAY_PROTOCOL.md. It changes only the host parser, makes no model
calls and retains all original outputs/costs. Unknown may omit later IDs. Missing,
duplicate, malformed or unsupported target decisions remain unknown individually.
Changed/same require valid later IDs; new targets/extra mutation fields remain
rejected. Extraction validation is unchanged. Test coverage includes preservation
of valid feedback beside unknown, missing-is-not-same and target mutation rejection.

| v5.1 replay | Agreement /13 | Predicted changed | Matches among3silver changes |
| --- | ---: | ---: | ---: |
| Direct unchanged | 6 | 10 | 3 |
| Joint | 3 | 3 | 1 |
| Old-only | 5 | 6 | 3 |

Old-only's aggregate relations match all3 labelled changes with fewer change
predictions than direct, but target audit below shows this is NOT3correctly
localized changes. It produces5unknown and only2same. It is not an overall win; unknowns and limited
coverage cannot be hidden by reporting changed precision alone. These replay
numbers are not newly held-out evidence. Aggregate changed also does not establish
that the right target was changed.

## Mechanistic findings

Joint extraction sometimes literally assigns a later n-ID and new value to an
OLD target (six women/four bikes); rejecting it has a factual purpose. Hiding later
evidence removes that channel. However old-only still converts a readiness question
into a fact, and its decision stage can mark unchanged team size10 as changed
when female composition changed. Legal IDs can point to greetings or blank spans
instead of the asserted fact. Free-form extraction validity and factual correctness
remain distinct.

The independent INTERFACE_DIAGNOSIS.md covers the first7nonempty outputs and keeps
these interface and semantic errors separate. TARGET_AUDIT.md records a follow-up
audit of accepted old targets and changed-attribute coverage. Neither rewrites
the silver labels or supplies targets to the running model.

That target audit finds only1/3 changed attributes fully retained by old-only:
female composition survives, but both bicycle targets omit the old total-three
qualifier ("other two") and merely list types, which can remain true after a fourth
bike. Of32accepted targets,2explicitly turn a readiness question into an affirmative
fact, and1has plan/completion ambiguity. Joint has6literal later-ID contaminations;
even legal old IDs accompany later-only company, device and other details. Thus
the positive-looking aggregate changed coverage is not valid localization credit.

## Decision

Keep the immutable-target boundary and per-target failure isolation as concrete
engineering improvements. Do not promote the current4B semantic pipeline or
train a feedback selector from its judgments. v3-v5 have now separated citation
copying, target invention, input exposure and batch failure; continuing to append
free-form prompt clauses would not address the remaining factual discrimination.

Before a larger experiment, a capacity/representation diagnostic is warranted:
fix source-derived targets, separately check old-target support and per-target
relation, and compare a stronger independent verifier or an appropriately tested
entailment model to the same4B baseline. A supplied correct target must be labelled
privileged diagnosis. Do not silently download/train a large model or substitute
assistant judgment as calibrated truth. Only4B generative models were found in
the local task model directory during closeout; no new model was started.

Focus stays on B current-applicability feedback, not broader E engineering. A
positive precision/coverage/cost result and feedback-learning benefit are still
unproven. This experiment does not reject the old-only idea; it bounds what the
current implementation and model can support. Re-extracting facts inside B also
adds a writing/extraction confound. A further B-specific test should consume a
fixed already-written MemoryCore target (or an explicitly privileged old source
span), preserve its qualifiers, and measure target support and relation jointly.
Do not continue expanding a new fact-extraction subsystem as B's main contribution.

## Artifacts

Root `/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-v5/`: adapted runtime
and isolated offline files, all calls/results, two source reviews, summary.json,
partial-replay.json/partial-summary.json and independent diagnoses. Reproduce with
score.py and replay.py using that root. Six boundary tests,176repository tests and
plugin build passed. OwnedPID2333589 exited. No production memory; remotePR#2
unchanged. Code and evidence local; continue here rather than redoing old prompts.
