# Optional memory feedback sidecar

This host-neutral module exposes two separate opt-in entry points. Start with
`selectAnswerFeedback` for temporary B feedback about an answer. The older
`processFeedback` entry point manages E verification and reversible lifecycle
views. Neither installs a Gateway hook or changes default recall.

## B: select temporary answer feedback

The host supplies an answer ID, its existing candidate IDs and checker outcomes,
and an **already computed** baseline feedback list. Only candidates with
`checkerPass: false` are eligible for selection; `true` and `null` are not.
The selector can choose a subset, including an empty set. This interface does not
discover candidates or implement their checkers.

```ts
import { parseAnswerFeedback, selectAnswerFeedback } from './index.js';

// Host-owned adapters and values: answerObservation, baselineFeedback,
// loadSelectorState, feedbackModel and showTemporaryFeedback.
// answerObservation may extend { answerId, candidates } with visible evidence.
const decision = await selectAnswerFeedback({
  enabled: bEnabled,
  observation: answerObservation,
  baselineFeedback,
  timeoutMs: 5000,
  selector: async (observation, signal) => {
    // Load and validate any trained state inside this shared deadline.
    const state = await loadSelectorState({ signal });
    const reply = await feedbackModel.select(observation, state, { signal });
    return parseAnswerFeedback(reply.text, reply.outputLimited);
  },
});
showTemporaryFeedback(decision.feedback);
// decision.useBaseline/status/reason identify fallback; do not call the model again.
```

These adapter names are illustrative host functions, not additional exports.
The observation may carry original answer text, visible requirements and source
records. Keep evaluation gold out of it. The host remains responsible for the
meaning and authority of checker outcomes and for a valid baseline list: the
entry point returns that baseline unchanged on shutdown or failure.

When disabled, the entry point returns `status: 'off'` without calling the
selector. Invalid observations, thrown errors, unknown or invalid selections,
and timeout return `status: 'fallback'` and `useBaseline: true`. Successful
selection returns `status: 'selected'` and `useBaseline: false`; **a valid empty
list is success**, not a request to fall back. Duplicate IDs, IDs outside the
candidate set and selection of passing/unknown candidates are rejected.

`parseAnswerFeedback` accepts only a final `ACTIONABLE: ["candidate-id"]` line
(including `ACTIONABLE: []`); `unknown`, malformed output or an output-limit flag
returns `null`. It does not recover decisions from reasoning text. The selector
may also return a validated ID list directly without using a text model.

At most 256 candidates are accepted. The deadline defaults to 30 seconds and
must be positive and no greater than 30 seconds. State loading, validation and
selection share that deadline. On timeout the abort signal fires and late
results are ignored. The host callback must honor cancellation and avoid write
side effects. JavaScript cannot forcibly interrupt synchronous blocking work;
an overdue synchronous result is rejected, but this is not hard real-time
isolation. The interface provides no memory/store write handle and performs no
replacement, invalidation or persistent policy update.

### Learning and evidence boundary

Any learned state belongs to the host adapter; this entry point neither trains a
model nor establishes calibrated confidence. Training examples can inform a
bounded selector, but improved selection quality requires a separate comparison
against the same inputs, supervision and computational budget. A legal ID list
does not prove that its feedback is correct, that a memory caused an answer
failure, or that consuming the feedback improves a later answer.

The current native integration verifies database readback, terminal parsing,
off/failure fallback, rejection of late results and unchanged memory/search
state. It replays saved model outputs; it does not rerun inference on database
readback. Research candidates supplied from oracle historical rule values remain
oracle candidates after native integration. Neither those candidates nor replay
receipts establish autonomous discovery or production readiness. See
[the native integration record](../../../benchmarks/topic3-b-answer-feedback-v1/NATIVE_INTEGRATION.md)
for the executed checks, replay command and limitations.

## E: optional verification and lifecycle views

This separate path requires stores: `base` and `auxiliary` must differ. The host
owns their creation and closure; use an isolated pair for evaluation.

```ts
import { FeedbackMemory, FeedbackPolicy, processFeedback } from './index.js';

const memory = new FeedbackMemory(owner, auxiliaryDirectory, baseStore, auxiliaryStore);
const policy = new FeedbackPolicy('service/action/version/verifier-version');
const decision = await processFeedback({
  enabled: featureEnabled,
  memory,
  candidate, // exact target/version, later same-owner source, unique spans
  score: () => proposalModel.score(candidate),
  verifier: (evidence, signal) => sourceVerifier.verify(evidence, signal),
  policy,
  learn: collectingDevelopmentFeedback,
  timeoutMs: 30000,
});
const recall = await memory.search(query, {
  enabled: featureEnabled && !decision.useBaseline,
  limit: 12,
});
// Inject recall.result exactly as you would native memory_search results.
// Save policy.snapshot() atomically when learn=true; keep evaluator labels separate.
```

For persisted policy reads, pass `loadPolicy` and `policySignature` to
`processFeedback`. Corruption, read failure and timeout produce `useBaseline=true`.
The host must honor it on the next read. A new valid signature uses a fresh policy;
unseen score bins verify. Disabled processing calls neither score nor verifier,
and disabled search bypasses all auxiliary reads and invokes native memory_search.

`Verification` is a host evidence-provider result, not an independent-truth claim.
The public experiment deliberately uses a fallible semantic model verifier and
reports its errors. Production integrations should supply their own appropriate
authority: field-matched tool readback, explicit user correction, or a qualified
reviewer. JSON validity and exact quotations alone establish neither authority nor
semantic expiry. Treat `unknown`/failed reads as no update, never as same.

Only a `changed` verification may create a replacement. It labels the exact old
span as historical and appends the later assertion; all other characters survive.
Original records and historical auxiliary replacements are never deleted. Newer
source evidence can supersede the same target's prior auxiliary entry; old/repeated
events are obsolete/idempotent. A source/target version or content mismatch falls
back during reading rather than applying an obsolete decision.

Persistence is a **single-writer local reference**: native auxiliary write/readback,
then atomic rename of the visible manifest. It is not a distributed transaction or
a production TCVDB commit protocol. A pre-publication failure leaves no newly visible
replacement; an orphan auxiliary record can remain and counts against capacity.
Do not share a directory across writers. Timeout cancellation cannot authorize late
publication: reviewers return a value and never receive a store handle.

Limits: 128 total historical auxiliary records by default (configurable 1..2048),
16000 characters per supplied source, four policy bins, 1024 observations per
outcome/bin, and 4096 deduplicated feedback identities. No eviction silently makes
old evidence current. Capacity failure returns baseline via the processing entry
point; administrative compaction is outside this patch. Each read validates at most
the bounded active entries; it retains native ranking and result count.

There is no new calibrated-confidence, automatic deletion, extraction-model, or
coding-business claim. See `benchmarks/topic3-be/RESULTS.md` for the public negative
result and the distinction between E-verdict learning and true memory correctness.
