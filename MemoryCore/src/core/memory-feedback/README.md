# Memory feedback sidecar

This directory contains the opt-in runtime boundary for the B and E experiments.
It is deliberately not re-exported from `core/index.ts`: hosts that adopt the
experimental API import `memory-feedback/index.ts` explicitly.

The module does not install Gateway hooks. Disabled and failed calls preserve the
host-provided baseline, and the B selectors receive no memory-write handle.

## Temporary answer feedback (B)

`selectAnswerFeedback` validates a host-owned candidate set and runs a selector
under one deadline. Only candidates whose checker returned `false` are eligible;
passing and unknown candidates cannot be selected. A valid empty list is success.

```ts
import {
  parseAnswerFeedback,
  runAnswerFeedbackAdapter,
} from './index.js';

const result = await runAnswerFeedbackAdapter({
  enabled: config.feedback.enabled,
  observation,
  baselineFeedback,
  policyVersion: 'feedback-selector:v1',
  signalType: 'explicit_correction',
  maxSelectedK: 8,
  timeoutMs: 5_000,
  selector: async (input, signal) => {
    const reply = await selector(input, { signal });
    return parseAnswerFeedback(reply.text, reply.outputLimited);
  },
});

logger.info(result.decisionLog);
showFeedback(result.feedback);
```

The adapter records mode, status, policy version, candidate counts, selected `k`,
auxiliary-path use, fallback and elapsed time. Logging remains host-owned so a log
failure cannot alter the decision. Invalid configuration, invalid selection,
selector failure and timeout return the exact supplied baseline.

Limits: at most 256 candidates, `k` in 1..32 and timeout in `(0, 30000]` ms.
The selector must honor cancellation and must not publish side effects.

## Dependency candidates (B)

`selectDependencyCandidates` turns a bounded, already-computed proposal into an
additive retrieval/verification set. Active paths must reference the caller's
candidate universe and quote the later observation exactly. Off and fallback
return no additive IDs. The result always records `memoryMutationAllowed: false`.

This is candidate expansion, not invalidation or durable state learning. Defaults
are 64 input candidates, 16 paths and 8 selected IDs; hard maxima are 256, 64 and
32 respectively.

## Verified lifecycle view (E)

`processFeedback` verifies an exact old/new evidence pair before publishing a
replacement to an isolated auxiliary store. `FeedbackMemory.search` overlays that
view on native results without modifying the original records.

```ts
import {
  FeedbackMemory,
  FeedbackPolicy,
  processFeedback,
} from './index.js';

const memory = new FeedbackMemory(owner, sidecarDirectory, baseStore, auxiliaryStore);
const policy = new FeedbackPolicy('source/action/verifier:v1');
const decision = await processFeedback({
  enabled: config.feedback.enabled,
  candidate,
  memory,
  policy,
  score: () => proposalModel.score(candidate),
  verifier: (evidence, signal) => verifier.verify(evidence, { signal }),
});
```

The reference implementation is single-writer and local. It caps source text at
16,000 characters, auxiliary history at 128 entries by default, policy identities
at 4,096 and observations per bin/outcome at 1,024. Read, validation, capacity and
timeout failures require a baseline read. `unknown` never mutates memory.

## Evaluation-only support

Causal ledgers, replay validation, scope matching, target binding and candidate
compilation live under `benchmarks/support/memory-feedback/`. They remain available
to reproduce experiments but are not shipped as MemoryCore runtime APIs.

The product-slice rationale and verification are summarized in
[`benchmarks/topic3-be-agent-product-v1/OPTIMIZATION_REPORT.md`](../../../benchmarks/topic3-be-agent-product-v1/OPTIMIZATION_REPORT.md).
