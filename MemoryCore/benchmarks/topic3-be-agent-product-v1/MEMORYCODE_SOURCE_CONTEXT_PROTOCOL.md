# MemoryCode authoritative-source context infra protocol

Date: 2026-09-14

## Objective

Reduce the retained-focus route's coding-path input without repeating the failed `focus_compact`
assumption that compiled guidelines can replace every raw source. The candidate keeps every mentor turn
verbatim, with its session boundary, while deterministically omitting mentee acknowledgements and replies.
The same source-only history is used by the compiler and the coding call. This matches the product's
lossless user-observation boundary; it is not semantic summarization.

The model, reasoning effort, timeout, empty workspace, tool prohibition, scorer, and compiler instructions
remain those of `memorycode-quality-first-focus-v2`. The new arm is `focus_source_raw`; `raw_full` remains
the paired baseline. Compilation is still accounted separately so the persisted-revision coding stage can
be reported without pretending that ingest is free.

## Bounded pilot and decision

First run only exposed task `memorycode-300`, where removing raw history previously changed the receiver
state and failed the target. Continue only if `focus_source_raw`:

- has receiver-aware target score `1` and no active-rule regression against paired `raw_full`;
- completes both calls with usage and no timeout, retry, empty output, or tool event;
- uses less non-cached input in its coding stage than paired `raw_full`.

If it passes, select one new single-target update dialogue per official update-capable session-count stratum
using domain-separated SHA-256 ordering. Exclude the original 24 generation dialogues and both prior
10-dialogue focus sets before any calls. Run exactly `raw_full` versus `focus_source_raw` on that fixed set.
Do not change the parser, compiler instruction, prompt, model, or scorer after seeing those outputs.

Promotion requires zero target regressions, all calls valid, and aggregate warm coding-stage non-cached
input below raw. A failure is retained and the route stays experimental/off. This protocol does not use a
natural-validation count and cannot establish production SLOs, dollar cost, or superiority to an external
memory system.
