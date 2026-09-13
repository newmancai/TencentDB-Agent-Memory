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

## Public-data adapters and real host path

The public datasets are isolated from MemoryCore through benchmark adapters:

| Capability | Adapter | Agent-visible input | Evaluator-only data |
|---|---|---|---|
| Long-dialogue feedback | `benchmarks/topic3-be/adapters.py` plus `topic3-b-delivery-v1/delivery_eval.py` | selected conversation/history fragments | persona preference, checklist, semantic review |
| Lifecycle validity | `benchmarks/topic3-b-public-suite-v1/validmem_adapter.py` | query, current day, shuffled choices, chronological store | correct choice, superseded/expired/irrelevant identities |
| Read/write triggering | `benchmarks/topic3-b-public-suite-v1/trigger_adapter.py` | prompt, initial store, optional workspace | trigger, operation and include/exclude rules |
| Coding-task outcome | `benchmarks/topic3-b-public-suite-v1/amb_adapter.py` | task and isolated repository state | checker contract and harm labels |

The Trigger host does not emulate storage. `trigger_memory_bridge.ts` calls the
existing `writeMemory`, `executeMemorySearch` and `queryL1Records` paths against a
fresh SQLite store per case. `trigger_memory_mcp.py` only exposes those bounded
operations to the agent; it owns no second index. The `*` query is an adapter-level
bounded list operation capped at 20 records, and one write is capped at 4,000
characters. Removing the MCP registration is the off switch. Bridge errors are
returned as tool failures and the isolated store is not promoted or shared.

## Internal multi-turn coding-data mapping

Internal migration should implement a new loader, not edit public gold or the
MemoryCore index. A minimal record needs:

```text
task_id, user_or_project_cluster, chronological_events,
current_request, optional_workspace_fixture, initial_memory,
decision_trace, checker_or_user_feedback, final_outcome
```

The loader emits agent-visible `current_request`, workspace and initial memory;
it keeps expected trigger/action, accepted answer/store facts and checker outcomes
in evaluator-only records joined by `task_id`. For a true B→E→B experiment, the
first attempt's actual checker receipt becomes a candidate observation, and a
later related task is evaluated under paired baseline/enabled arms. Do not copy a
public `ground_truth`, hidden checklist or future turn into the memory input.

Keep the statistical unit at user/project/task-family level, preserve all runtime
failures and retries, and report L1 extraction/write separately from L0
retrieval/injection. The current Trigger policy is a tool-description method, not
a learned durable updater; an internal host may reuse its trace schema and bounds
without claiming its public score transfers.

## Rollback

Rollback is additive and local: disable the answer-feedback flag, omit the Trigger
MCP server registration and stop reading auxiliary candidate IDs. The host then
uses its original baseline and original MemoryCore index. No migration deletes,
rewrites or permanently replaces base L0/L1 records.
