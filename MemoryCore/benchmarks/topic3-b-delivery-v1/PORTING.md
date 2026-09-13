# Portable integration and rollback notes

The implementation is an additive host-neutral sidecar under
`src/core/memory-feedback/`; no Gateway branch is changed. Importing the module
does not activate it.

## Minimal host wiring

1. Compute the host's normal feedback result first and keep it as
   `baselineFeedback`.
2. Map the host answer and checker observations to `AnswerFeedbackObservation`.
   Gold evaluation labels must stay outside this object.
3. Call `runAnswerFeedbackAdapter` with the feature flag, a non-empty policy
   version, the signal type, `maxSelectedK`, deadline and a cancellable selector.
4. Use the returned `feedback`. Never perform a second fallback model call.
5. Emit the returned `decisionLog` through the host's existing logger. It records
   mode, policy, signal, candidate counts, `k`, auxiliary-path use, fallback,
   reason, baseline use and elapsed milliseconds.
6. If causal learning evidence is collected, append the separate Phase-0
   `decision_trace/feedback_claim/memory_assertion/outcome` records. Do not infer
   propensity or memory cause after the fact.

## Switch, fallback and bounds

The default host flag remains off. Off returns the exact host baseline and never
invokes the selector. Invalid observations/configuration, timeout, selector
failure, invalid IDs and an over-`k` selection all return that same baseline.
A valid empty selection is an enabled decision, not fallback.

- candidate capacity: 256;
- selected auxiliary feedback: default `k=8`, configurable only in `1..32`;
- shared selector deadline: default 30 seconds, maximum 30 seconds;
- current temporary adapter has no memory-write handle;
- Phase-0 trace storage is append-only local single-process JSONL;
- exact structured scope remains deterministic; a learned gate is not enabled.

The machine-readable regression is:

```bash
npx tsx benchmarks/topic3-b-delivery-v1/runtime_contract_harness.ts \
  benchmarks/topic3-b-delivery-v1/results/runtime-contract.json
```

It verifies feature-off, enabled selection, forced selector failure and over-`k`
fallback. A production host must additionally test its own logger, config system,
checker authority, timeout isolation and baseline callback; those dependencies
are deliberately not invented inside this PR.
