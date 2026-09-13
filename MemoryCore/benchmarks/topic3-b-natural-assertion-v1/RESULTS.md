# Raw conversational correction candidates: results

2026-09-13. This stage evaluates a narrow missing component after the synthetic
end-to-end result: raw follow-up text to a current-interaction assertion candidate,
with abstention. It does not identify a memory cause or promote durable memory.

## V1: the public behaviour label is not assertion gold

The fixed v1 run completed 12/12 isolated Codex calls. Against the predeclared proxy
(`NEG_2` → propose; `NEG_3/NEG_4` → abstain), it scored 9/12: proposals 1/4 and
abstentions 8/8, below the 10/12, 3/4, 7/8 threshold. Cost was 174,493 input tokens
(42,496 cached), 499 output tokens, 80 reasoning tokens, and 95.860 seconds wall time.

The failure exposed a contract error. A source review after the run found that only
one of the four selected `NEG_2` messages both identified an answer error and supplied
replacement content. The other three asked for a tense edit, story continuation, or
formatting change. Under the stricter assertion contract, Codex's three abstentions
were reasonable. This review was not blind to outputs, so it diagnoses the proxy;
it does not retroactively convert v1 to a passed evaluation. The failed score and
all messages/receipts remain unchanged in local evidence.

## V2: freeze the message-level contract before inference

[The audited protocol](AUDITED_PROTOCOL.md) selected 14 different, previously
unselected WildChat conversations by hash. The main agent retained all selected
cases and froze the strict action labels before any v2 call: 2 proposals and 12
abstentions. Public behaviour labels remained metadata only. The Codex prompt,
model (`gpt-5.6-sol`), medium reasoning, schema, and no-retry rule were unchanged.

| Check | Result |
|---|---:|
| completed | 14/14 |
| exact action + schema + evidence contract | 14/14 |
| pre-audited explicit corrections | 2/2 |
| pre-audited abstentions | 12/12 |
| proposal evidence exact substring | 2/2 |
| fixed threshold | passed |

The two propositions faithfully restated only their quoted current-turn corrections:
one about what a song says and one about normalized relations. This fidelity check is
the main agent's judgment, not independent annotation or factual verification. The
run used 204,600 input tokens (74,368 cached), 516 output tokens, 66 reasoning tokens,
and 107.900 seconds wall time.

## Runtime gate and replay

`compileFeedbackAssertionCandidate` is now the fail-closed boundary for this output.
It accepts only one answer target bound to a decision, explicit-user authority,
current-interaction scope, a nonempty verbatim feedback span, and a nonempty
proposition. It returns `status: candidate`; it cannot verify, broaden, or durably
promote memory. Clean abstention returns no assertion, and invalid target/scope/span
throws.

`host_candidate_harness.ts` replayed all fixed v2 outputs through this real gate and
`JsonlFeedbackTraceStore`: 28 decisions, 14 bound feedback claims, 2 candidate
assertions, and 14 outcomes survived restart with zero replay issues. The 14 source
answers are correctly pending because these public off-policy logs contain no
MemoryCore task outcome. The 14 extractor decisions are learner-ready only for the
pre-audited extraction action, not for answer quality or memory causality.

## Conclusion and next boundary

This is positive development evidence that a conservative sidecar can preserve two
explicit corrections while abstaining on twelve complaints, clarifications, edits,
and new requests. It also proves the old six-class feedback taxonomy is too coarse
to serve directly as assertion gold.

The public conversations still have no logged MemoryCore candidate set, inclusion
action, propensity, or counterfactual answer outcome. Their correction candidates
therefore remain scoped to the current interaction and must not train a durable
memory selector. The next legitimate step is to locate or create an instrumented
development source where the original answer actually consumed known memory
candidates and a later task outcome can verify the effect. If no such source exists,
the learned target/promotion branch is data-blocked and should remain off rather than
manufacturing memory-cause labels from these messages.

Raw evidence: `.local-evidence/topic3-b-natural-assertion-v1/{run-v1,run-v2,host-v2}`.
Git stores no conversation text.
