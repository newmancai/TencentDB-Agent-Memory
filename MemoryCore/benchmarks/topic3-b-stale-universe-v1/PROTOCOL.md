# STALE candidate-universe retrieval v1

Frozen on 2026-09-13 after candidate-only dependency nomination passed 15/16.
That component received the correct old memory, so it did not test whether an
ordinary retriever can place that old memory in the proposer candidate universe.

Use the same fixed STALE parquet. Exclude all 24 positive UIDs used by the three
model experiments. Within T1 and T2, sort by
`SHA256("topic3-b-stale-universe-v1:" + uid)` and take 100 each. This consumes
200 rows for retrieval evaluation and leaves 176 rows untouched by this route.

For each row, use only sessions strictly before the annotated newer relevant
session as candidate documents. A document is the concatenated user messages in
one session. The target is the annotated older relevant session. Rank with a
fixed dependency-free BM25 implementation (`k1=1.2`, `b=0.75`, lowercase ASCII
alphanumeric tokens, fixed stopword list) under two queries:

1. `observed_session`: all user text in the actual newer session, available to a
   runtime writer;
2. `normalized_m_new`: the dataset's normalized `M_new`, an evaluator-side
   optimistic diagnostic that is not a production input.

Report recall at 1/5/8/16/32, median rank, zero-overlap count and ranking latency
p50/p95, separately for T1/T2 and combined. No LLM, embedding model, answer
probe or label enters retrieval.

The ordinary lexical universe passes the practical `k=8` gate only if observed
session recall@8 is at least 80% overall and at least 70% for T2. Failure blocks
claiming that the candidate-only proposer is end-to-end ready; it does not reject
embedding, structured-bucket or graph candidate discovery.
