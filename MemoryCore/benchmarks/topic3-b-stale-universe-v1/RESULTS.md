# STALE candidate-universe retrieval results

## Outcome

The fixed ordinary lexical candidate universe **passed** its registered gate on
200 new rows. Using the actual newer session's user text, BM25 old-session
recall was 67.5% at 1, 90.5% at 5, 96.0% at 8, 98.0% at 16 and 100% at 32.
T2 recall@8 was 94.0%, above the frozen 70% requirement. Median rank was 1;
all 200 targets shared at least one retained query token.

The evaluator-only normalized `M_new` diagnostic was much weaker: overall
recall@8 61.0% and T2 53.0%, with median ranks 6 and 8 respectively. The earlier
exploratory weakness was therefore caused by querying with the compact state
sentence. The actual session contains additional runtime-visible user language
that bridges retrieval. A system must not assume a generated summary preserves
that candidate-discovery value.

Ranking 400 query/row combinations took 1.767 summed CPU seconds. For the
runtime-visible observed-session arm, per-row p50/p95 were 4.952/5.822 ms. This
is a small in-process Python BM25 measurement and excludes ingestion, MemoryCore
storage, network and model latency.

## Boundary

This result validates a lexical top-8 candidate source for a subsequent method
test; it does not validate MemoryCore's production retriever, candidate
nomination precision, downstream answers, invalidation or persistence. The
annotated older-session index is used only for scoring. The 200 evaluated rows
must not be reused as an untouched model holdout; 176 STALE rows remain outside
all four experiments.

See [the frozen protocol](PROTOCOL.md), `stale_universe.py`, and
`results/summary.json`.
