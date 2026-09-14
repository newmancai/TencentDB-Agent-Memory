# Project-memory porting guide

This guide defines the smallest integration surface needed to move the B+E
implementation into another coding host while preserving its baseline, source
identity and failure semantics. The core rule is that host adaptation may map
events and storage, but must not silently widen memory scope or convert an
unverified observation into a durable rule.

## Runtime integration surface

The product runtime is an additive package subpath:

```ts
import {
  runAnswerFeedbackAdapter,
  selectDependencyCandidates,
  FeedbackMemory,
  processFeedback,
} from "@tencentdb-agent-memory/memory-tencentdb-v2/memory-feedback";
```

Importing the module installs no Gateway hook. A host needs four local changes:

1. expose a default-off feature flag;
2. map its answer/checker receipt to `AnswerFeedbackObservation`;
3. call the adapter after computing and retaining the ordinary baseline;
4. emit `decisionLog` through the existing logger and consume the returned
   baseline when `useBaseline=true`.

The adapter must not receive hidden evaluation labels. The selector receives a
bounded candidate view and an abort signal, but no memory-write handle.

## Required host mappings

| Product contract | Internal source |
|---|---|
| `answerId` | immutable response/turn ID |
| candidate `id` | checker assertion, patch hunk or tool-action ID |
| `checkerPass` | authoritative checker result; `null` when unknown |
| `signalType` | explicit correction, executable checker or other enumerated host signal |
| `baselineFeedback` | result the host would return with the feature disabled |
| `policyVersion` | source/binder/gate version tuple |
| elapsed time and fallback | existing structured decision log sink |

For verified lifecycle use, map internal storage through `IMemoryStore`. Keep the
ordinary store and auxiliary store distinct, use the host user/project isolation
key as `owner`, and preserve original records. The lifecycle view caps entries,
text size, policy identities and observations; record readback is batched in
groups of 20.

## Evaluation-data adapter

`public_eval.py` does not import CUPID code. Internal or another public adapter
produces one JSONL object per task with:

- stable task ID, independent cluster ID and diagnostic stratum;
- the same named arms declared in the manifest;
- per-arm input/output tokens, generation milliseconds and error;
- per-arm coverage label;
- paired `win/loss/tie` decided by an evaluator that did not generate the answer.

For internal programming data, use project as the minimum cluster. Store the
commit, checker argv/provenance, selected MemoryCore record IDs, exact injected
spans and token accounting outside the model prompt. User/project identifiers
must be pseudonymized before exporting receipts.

Dataset adapters may change; the aggregator and result schema should not. L1
extraction, L0 retrieval and model generation timers must be captured separately
when those paths actually run.

### MemoryCode adapter boundary

`memorycode_store.ts` is the concrete public reference adapter. It maps one raw
dialogue session to one source-bound MemoryCore record and queries the existing
SQLite/FTS implementation; it does not add another index or delete base rows.
Only the dataset loader is MemoryCode-specific. The inference path consumes
`record content`, `source session ID` and the current coding request. Public
`type`, `topic`, `instructions` and regex fields remain scoring-only.

An internal multi-round programming adapter therefore needs only:

| Public field | Internal equivalent |
|---|---|
| dialogue ID | pseudonymized project/task cluster |
| session index | immutable turn/session source ID plus timestamp |
| session text | user/tool/assistant evidence allowed by retention policy |
| evaluation query | later coding request |
| public regex | authoritative checker result, never prompt content |

Keep the fixed `k`, context-token cap and latest-session rule in configuration,
not in the loader. If internal events are individual turns rather than sessions,
change only the chunk adapter and record the changed evaluation granularity.
The current public run deliberately does not pretend deterministic session
chunking is L1 semantic extraction; an internal extractor needs its own
precision/coverage/cost report before its outputs enter the retrieval arm.

## Rollback and fallback

- Feature off: return the exact precomputed baseline; do not invoke the selector.
- Invalid observation/configuration/selection: return baseline and log fallback.
- Auxiliary exception or timeout: abort the selector, return baseline, do not
  issue a second model call.
- Lifecycle corruption, stale source or unavailable store: return the native
  search result and mark fallback.
- Rollback: disable the flag and stop reading the auxiliary store. Original
  MemoryCore records remain untouched.

The host integration test must reproduce the four cases in
`runtime-contract-results.json` and confirm its logger/config wrapper cannot alter
the returned decision.

## Host-owned responsibilities

Authentication, privacy retention, checker authority, configuration rollout,
logger availability, distributed single-writer coordination and traffic
experimentation remain the responsibility of the integrating host. They are
kept outside the sidecar so that deployment policy does not leak into the memory
state machine.
