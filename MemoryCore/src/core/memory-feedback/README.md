# B+E memory feedback sidecar

This host-neutral module adds optional, bounded feedback selection and reversible
span-level lifecycle views to MemoryCore. It does not install a Gateway hook or
change default recall. `base` and `auxiliary` must be different stores. The host
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
