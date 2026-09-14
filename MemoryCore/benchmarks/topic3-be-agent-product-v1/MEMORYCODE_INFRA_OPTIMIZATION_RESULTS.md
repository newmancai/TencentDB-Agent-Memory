# MemoryCode AI-infra optimization results

Date: 2026-09-14. Machine-readable result: `memorycode-infra-optimization-results.json`.
The runs use public synthetic MemoryCode data, Codex CLI `0.153.4`, `gpt-5.6-sol`, medium reasoning,
isolated empty workspaces, no tools, and saved raw events and usage. They test cost mechanisms around the
accepted B+E quality route; they are not natural validation, production SLOs, or dollar-cost estimates.

## Decision

Keep the accepted two-stage quality mechanism, but compile only when explicit feedback changes the
history revision and persist the result. Do not enable either new prompt shortcut by default:

- authoritative-source context materially reduced coding-stage input, but its disjoint confirmation had
  one primary target win and one primary target loss;
- single-pass self-focus failed its bounded pilot on both quality and cost and was stopped before the
  third pilot task or a new held-out selection.

This is a useful optimization result: it identifies a real lower-input candidate and rejects two unsafe
ways of claiming that saving tokens preserves quality.

## Authoritative-source context

This arm preserves every mentor turn and its session boundary verbatim, while deterministically removing
mentee acknowledgements and replies. It is source selection, not semantic summarization. Across all 54
distinct packets used by the four MemoryCode stages so far, UTF-8 history bytes fell from `3,517,121` to
`2,214,624`, a `37.03%` reduction before tokenization.

The exposed `memorycode-300` pilot passed: target and active-rule scores both tied at `1`, and the persisted
coding stage used `0.710x` non-cached input and `0.683x` wall time versus paired raw. A third disjoint set
was then selected and committed before calls, excluding all 44 earlier dialogues. All `30/30` calls were
valid.

| Disjoint 10-task confirmation | Raw full | Source context | Paired / ratio |
| --- | ---: | ---: | ---: |
| Receiver-aware target | 9/10 | 9/10 | 1 win, **1 loss**, 8 ties |
| Official-compatible mean | 84.25% | 91.26% | secondary |
| Receiver-aware active-rule mean | 82.59% | 89.36% | 4 wins, 0 losses, 6 ties |
| Persisted coding-stage input | 249,774 | 202,049 | **0.809x** |
| Persisted coding-stage non-cached input | 181,678 | 125,889 | **0.693x** |
| Persisted coding-stage wall time | 355.424 s | 403.715 s | 1.136x |
| Persisted coding-stage calls | 10 | 10 | 1.000x |

The primary bootstrap interval is `[-0.30, 0.30]` and the exact sign-test value is `p=1.0`; the arm does
not pass the frozen zero-regression promotion gate. Cold use also remains expensive: compiler plus coding
is `1.493x` raw non-cached input, `1.965x` wall time, and `2x` calls.

The target loss was `memorycode-297`. The generated code contains target-compliant attributes
`t_chx0_capacity` and `t_chx1_cache`, but represents an otherwise illegal digit-prefixed class through
dynamic `type(...)`; the frozen receiver-aware extractor follows ordinary class constructors and returns
zero. That is a genuine metric boundary, not permission to edit the frozen score after seeing output. The
reported primary loss is retained, and the source arm remains off.

## Single-pass self-focus

This arm kept the complete raw history and folded checklist derivation into the coding call. It used one
call per task, but failed before confirmation:

| Two exposed pilot tasks | Raw full | Self-focus | Self/raw |
| --- | ---: | ---: | ---: |
| Receiver-aware target | 1/2 | 1/2 | 1 win, 1 loss |
| Active-rule mean | 82.81% | 81.25% | net regression |
| Input tokens | 94,660 | 95,022 | 1.004x |
| Non-cached input tokens | 78,532 | 86,958 | **1.107x** |
| Wall time | 108.178 s | 177.389 s | **1.640x** |
| Calls | 2 | 2 | 1.000x |

`memorycode-339` improved, but `memorycode-300` moved from target `1` to `0` and active-rule score from
`1.000` to `0.667`. That already violates the absolute-target, no-regression, and `<=1.05x` non-cached
input gates. Per the frozen protocol, `memorycode-206` was not run and no fourth confirmation set was
selected.

## What remains on the main line

- Quality path: full evidence remains available; the validated focus is an explicit experimental route.
- Cost path: compile at feedback ingest, persist by exact history/protocol/model revision, and reuse the
  state for ordinary coding requests.
- Candidate only: authoritative-source context deserves a larger independent study only if the primary
  checker is expanded prospectively to cover valid dynamic implementations; it is not enabled now.
- Rejected: compact-history replacement, independent-process prefix-cache assumption, and single-pass
  self-focus.

No removed “natural validation” count participates in these results.
