# Native Hindsight local-model comparison (before model outputs)

The baseline is the installed official `hindsight-api-slim==0.9.2`, native concise
extraction and observation consolidation, PostgreSQL 18.1 / pgvector 0.8.5. It is
not a reimplementation, the old chunks-only lane, or a vendor leaderboard run.

Input is the same `semantic-v3/runtime.json`: all prior user source parts, their
public timestamps, then the actual new user turn. No gold, canonical M_old/M_new,
explanation or target IDs are read. The public probe query is used only for the
subsequent recall/reflect, never to select facts before retention. Development is
run first. `--limit 1` means a prefix compatibility run, not a reportable subset.

Both methods use Qwen3.5-9B at official revision
`c202236235762e1c871ad0ccb60c8ee5ba337b9a`, greedy generation, and the existing
Qwen3-Embedding-0.6B. The shared server preserves actual raw generations and tool
calls. Hindsight uses its native lmstudio soft-schema provider; the server does
not implement constrained JSON decoding. Invalid generation is recorded rather
than repaired. A backend contract error is not a semantic method failure.

Hindsight's concise extraction and observations remain enabled. To make the
comparison occur after consolidation, automatic scheduling is replaced by an
explicit native consolidation call after history and after the new turn. Fresh
bank statistics must show no pending or failed consolidation. Otherwise the case
is incomplete. This is a scheduling configuration, not evidence that background
deployment has the same latency.

RRF reranking is the official supported configuration, matching the initial
Anchor hybrid lane. It is not the default learned cross-encoder. The comparison
must be named **Hindsight concise+observations / Qwen3.5-9B / RRF** and cannot
justify superiority over all Hindsight configurations. A positive claim against
stronger reranking requires running that configuration too.

Native `reflect(max_tokens=...)` is documented in the installed source as unused.
Effective operation settings are therefore explicit: retain and consolidation
maximum output 16384, reflect maximum output 4096, reflect context threshold
24000 and ten iterations. The shared endpoint accepts at most 32768 input tokens
without truncation. Reaching a context/backend limit is recorded. These settings
are **not equal whole-lifecycle token budgets**: extraction and agentic reflection
consume more calls. Compare quality with measured total tokens, GPU generation
seconds and wall time; do not declare budget parity from a function argument.

`run.py` saves native IDs, source provenance issues, both consolidation phases,
native recall and reflect, and before/after endpoint counters. Run the systems
sequentially when measuring counter deltas. Native derived facts and raw L0
records must be reported separately. Timestamps without timezone use UTC only as
an ordering convention. No immutable native fact version is fabricated.

A separate diagnostic recall after history uses only the raw new observation,
before retaining it, and saves native fact candidates and source mappings for the
same host B judge. This is not Hindsight's native feedback classifier. Its cost is
separately identifiable between history counters and `b_diagnostic_counters_after`.
Do not compare native fact IDs directly to raw-source gold: use recorded provenance
offline and report gaps. No derived immutable version is invented.

Current state: runner syntax and installed API/configuration examined; no native
semantic retain/reflect result yet. The STALE target labels remain non-exhaustive
and positive-only: target agreement cannot estimate commercial false invalidation.
