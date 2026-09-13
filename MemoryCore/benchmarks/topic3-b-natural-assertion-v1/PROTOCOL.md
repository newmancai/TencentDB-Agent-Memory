# Raw conversational correction to assertion candidate v1

2026-09-13, written before selecting or running the cases.

This is a bounded development diagnostic for the first unresolved stage after the
synthetic end-to-end result: can a raw follow-up user message create a **candidate**
assertion without turning every negative reaction into memory?

The fixed source is the already aligned public WildChat portion of
`topic3-b-feedback-audit`. It contains real conversational follow-up text and public
feedback-behaviour labels, but no record of this MemoryCore policy, no candidate
memory set, and no counterfactual memory-cause label. Therefore this experiment may
test correction extraction and abstention only. It may not claim memory attribution,
durable preference learning, production safety, or final-set generalization.

## Fixed sample and contract

Select by SHA-256 from distinct WildChat conversations:

- four `NEG_2` messages (the public taxonomy says the user identifies a problem and
  supplies a correction); expected action: `propose`;
- four `NEG_3` messages (problem stated without correction); expected action:
  `abstain`;
- four `NEG_4` messages (clarification); expected action: `abstain`.

Selection uses no message-content filter and no model result. Only the immediately
preceding user message, the assistant answer, and the follow-up message are visible.
The source label, source name, conversation ID, future turns, and all other history
are hidden from Codex. This is a development reuse of a source previously evaluated
by the old six-class experiment, not a fresh final holdout.

Codex must return one JSON object. `propose` is legal only when the follow-up both
identifies an error and supplies replacement content. It must include a nonempty
verbatim substring of the follow-up and a concise proposition, scoped to
`current_interaction`. For a bare complaint, retry, clarification, style reaction,
or ambiguous reference it must return `abstain`, empty evidence/proposition, and
scope `none`. A proposed assertion remains `candidate`; it is never promoted to a
durable user preference in this experiment.

Model and execution are fixed to `gpt-5.6-sol`, medium reasoning, isolated
`codex exec --ephemeral --ignore-user-config --ignore-rules`, no tools, no browsing,
and a 300-second per-call timeout. There are 12 calls and no quality retries.

## Checks and exit rule

The deterministic checker reports exact action, exact output contract, and whether a
proposal's evidence is a literal nonempty substring of the follow-up. The main agent
then reviews the four proposed propositions for fidelity to the quoted correction;
that review is explicitly an assistant judgment, not independent gold.

Advance to a host-integrated candidate stage only if all calls complete, at least
10/12 pass the combined deterministic contract, at least 3/4 `NEG_2` cases propose
with exact evidence, and at least 7/8 non-correction cases abstain. Otherwise freeze
this prompt/configuration and diagnose the observed failure class without tuning on
these twelve messages.

Raw messages, prompts, event streams, receipts, and the private label join remain in
local evidence. Git stores the protocol, runner, aggregate result, selected opaque
IDs, and costs.
