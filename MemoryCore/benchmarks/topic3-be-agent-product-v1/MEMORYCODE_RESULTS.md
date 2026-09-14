# MemoryCode results

## Decision

MemoryCode is accepted as the primary public method-validation dataset for the
programming-memory track. The current raw-session FTS configuration is **not**
accepted as a B+E quality improvement: it reduces context and latency sharply,
but does not establish a high-confidence correctness gain and fails to carry
updated rules into code.

This is a useful negative result. It localizes the next problem to
source-grounded instruction extraction and latest-version consolidation rather
than another `k` or prompt sweep.

## Full-release retrieval

The fixed `k=8` MemoryCore SQLite/FTS path completed all 4,182 final-history
queries from 360 independent dialogues. It read only raw session text and the
evaluation request; labels were opened afterward.

| Metric | Result |
|---|---:|
| latest target-session recall | 45.89% |
| short-history recall (1–15 sessions) | 87.92% |
| long-history recall (20–100 sessions) | 36.89% |
| 100-session recall | 20.01% |
| update-query recall (821 queries) | 46.77% |
| update stale-source collision | 61.39% |
| stale-only update selection | 24.12% |
| retrieval latency p50 / p95 | 1.39 / 2.79 ms |

The sharp monotonic deterioration after 10 sessions and the stale-version rate
show that lexical top-k session retrieval is not an update-aware memory policy.
Increasing `k` on this already-open result would only tune the same benchmark;
that route is deliberately not taken.

## Frozen 24-dialogue model comparison

All 72 Qwen3-4B greedy calls completed under the same 65,536 input and 1,024
output limits. `full_history` and the oracle each had one 1,024-token output;
`memorycore_l0` had none. Truncation and syntax validity remain explicit rather
than being retried or deleted.

| Arm | Strict target | Official-compatible | Target coverage | Input tokens | Gen p50 / p95 |
|---|---:|---:|---:|---:|---:|
| full history | 12.50% | 23.99% | 91.67% | 304,702 | 11.80 / 41.34 s |
| MemoryCore raw top-8 | 16.67% | 19.94% | 100.00% | 70,706 | 7.26 / 16.05 s |
| latest-guidelines oracle | 54.17% | 65.85% | 95.83% | 5,701 | 9.09 / 24.67 s |

For the primary strict target metric, MemoryCore versus full history is 1 win,
0 losses and 23 ties: mean delta `+0.0417`, dialogue bootstrap 95% interval
`[0, 0.125]`, exact two-sided sign `p=1.0`. The high-confidence gate fails. On
the official-compatible metric it is 3 wins, 7 losses and 14 ties, mean delta
`-0.0405`, with interval `[-0.0949, 0.0052]`.

Both ordinary history and raw FTS score 0% strict on the ten update tasks. The
privileged latest-guideline ceiling scores 50%. That gap is stronger evidence
for an extraction/versioning bottleneck than the one strict-score win is for a
retrieval benefit.

### Bounded Codex update diagnostic (2026-09-14)

A later four-call transfer diagnostic reused two fixed update dialogues but
changed the execution path to Codex `gpt-5.6-sol`, medium. Full verbatim history
scored 2/2 on the updated target versus 0/2 without history; both of the earlier
Qwen full-history and top-8 outputs were wrong on these IDs. This shows that the
Qwen update zero is model/backend dependent, not that raw history is inherently
unusable. Full raw cost 48.35% more total input and 44.39% more wall time in the
two-call aggregate. The subset was deliberately small and cost-bounded, so it
does not replace the 24-dialogue result, establish natural use, or validate
MemoryCore retrieval. See
[the bounded Codex result](MEMORYCODE_CODEX_UPDATE_RESULTS.md).

MemoryCore uses 23.20% of baseline input tokens, saving 233,996 tokens, and its
generation total is 210.92 seconds versus 398.24 seconds. These are valid cost
results, not a license to claim quality parity. Generation latency includes
prefill and excludes the separately logged 3.35–3.63 second model load on each
of four parallel shards.

## Artifact map

- `memorycode-selection.json`: fixed IDs, labels and source hashes;
- `memorycode_packets.ts`: regenerates exact prompts, retrieved source IDs and
  decision logs; the executed 24-row packet has SHA-256
  `ecabcda9142f5094cfa73b62ce1c41e6c87bad33633b2ccb2c29b1c69f1c76e4`
  and is not duplicated into the PR;
- `memorycode-receipts.jsonl`: 72 generated outputs and cost receipts, SHA-256
  `778ecd17b40116b8ba5734dd14f89e13359024fd5e2f17e9f839135d001de9e5`;
- `memorycode-results.json`: structured arm, paired, confidence and gate result;
- `memorycode-retrieval-results.json`: full-release retrieval strata; its 4,182
  local receipts hash to
  `5eccaf041950fdbe334563f9fda97c11711c171d40bd582fb0d23750a0dcb01c`;
- `memorycode-model.json`: executed model-file fingerprints.

The scorer matched the pinned official criterion implementation on all 849
formal rule/output pairs. The added strict target metric only changes how absent
target objects are accounted for; it does not change any gold regex.

## Next optimization boundary

The next method may use development data to extract mandatory mentor rules from
raw text, bind every rule to its source session, and supersede only a verified
predecessor. It must keep the raw FTS/full-history baselines, the same gold and
the same evaluation subset in any comparison. The full MemoryCode result is now
open development evidence, not an untouched final holdout. Final product claims
still require the repository-checker protocol in `PROTOCOL.md`.
