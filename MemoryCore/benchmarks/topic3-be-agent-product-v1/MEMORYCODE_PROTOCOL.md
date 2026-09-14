# MemoryCode public programming-memory protocol

## Why this is the new primary public set

[MemoryCode](https://github.com/Cohere-Labs-Community/MemoryCode) is closer to
the product question than generic conversational QA: a mentor introduces and
updates mandatory Python coding instructions over 1–100 sessions, while
irrelevant and instruction-like filler competes for memory. The final action is
code, and public AST/regex checks make scoring deterministic. The dataset is
synthetic, so it remains method validation rather than a business KPI or a
substitute for repository checkers.

The official Apache-2.0 release is pinned to source commit
`1ab87e119b2f9a498de8075219e1c07f6041b394` and Hugging Face revision
`32d888b11c73c67be91414e571dfe98c5c20feac`. The 360-file source tree has
SHA-256 `b7f410c70cd806834c3944acf7b2213a68ca3572b077987a6d47e8d454fef1c2`;
`topics.json` has SHA-256
`e824600c4b49b5755f6e620127b96a17ebcba329b58a6cc4f151c2a96f5eb7a0`.
The pinned Hugging Face parquet has SHA-256
`1edb12380ea3410c888fffa795f6ddd3251e4e634b84a7142c8386e7c2869733`.

The release contains 360 dialogues, 8,400 sessions, 4,426 coding-instruction
additions, 2,913 coding-instruction updates and 4,182 final-history queries.
All twelve official history lengths (1, 2, 3, 4, 5, 10, 15, 20, 30, 40, 50
and 100 sessions) are retained.

## Two evaluation layers

### Full-release retrieval regression

Every one of the 4,182 final-history queries is run through the open-source
MemoryCore SQLite/FTS path. A dialogue session is stored verbatim as one bounded
record with an exact `dialogue/session` source ID. Retrieval reads only
`session.text` and the code request, uses fixed `k=8`, always retains the most
recent session, and injects records in chronological order.

`instructions`, `topic`, regexes and event types are unavailable to retrieval.
They are opened only after ranking to score latest-source recall, stale-source
collisions and add/update strata. This is retrieval/injection validation over
raw session chunks; it does not evaluate L1 semantic extraction.

### Frozen end-to-end method subset

`memorycode_prepare.py` selects two independent dialogues from every official
history-length stratum by domain-separated SHA-256 ordering. For 3+ sessions,
one task targets a newly added rule and one targets a rule with an actual prior
occurrence; 1–2 session strata contain additions because the release has no
true coding-instruction update there. One final-history query is selected per
dialogue using the same fixed hash domain. The result is 24 dialogue clusters
and 72 model calls. No result, model output or score enters selection.

The three arms use identical system text, query, Qwen3-4B-Instruct-2507
weights, greedy decoding, 65,536 input-token limit and 1,024 output-token limit:

- `full_history` (`baseline`): all raw sessions;
- `memorycore_l0` (`enabled`): only the label-blind MemoryCore top-8 session
  records plus the most recent session, within the same cap;
- `latest_guidelines_oracle` (`oracle`): the latest public template guideline
  texts. This privileged extraction ceiling is excluded from product-gain gates.

The local model download lacks revision metadata, so the release name is not
treated as a sufficient pin. The three safetensor hashes start with
`75311d91`, `0b48adbb` and `7dd39ccc`; complete weight, config and tokenizer
hashes are in `memorycode-model.json`.

A 512-token technical pilot was retained outside the scored artifacts after it
produced hard truncation. The formal run reruns every baseline and method arm at
the official local-generation ceiling of 1,024 tokens. No single truncated arm
is repaired or selectively retried.

## Metrics and confidence

The official evaluator omits a non-comment/import rule when the model produces
no corresponding Python object. We therefore publish four separate effect
metrics:

- `official_compatible`: the pinned evaluator's conditional mean;
- `target_coverage`: whether the target rule produces a non-null official
  judgment (absence-safe import/comment checks remain scoreable);
- `target_conditional`: target-rule correctness only when that object exists;
- `target_strict`: target-rule correctness with an absent target object scored
  as zero. This is the primary effect metric.

The local scorer was compared criterion-by-criterion against the pinned official
implementation on 849 pilot rule/output pairs, with zero differences. Syntax
errors score zero. Retrieval additionally reports latest target-source recall,
stale collision, stale-only selection, selected-record count and latency. Model
cost reports input/output tokens and generation p50/p95/sum by arm.

Enabled-versus-baseline utility is paired within each dialogue. We report
wins/losses/ties, mean delta, a 10,000-sample dialogue bootstrap 95% interval
with seed `20260913`, and an exact two-sided sign test. A high-confidence gain
requires a positive bootstrap lower bound and sign-test `p < 0.05`; even then it
would establish public method evidence, not direct coding-agent or commercial
utility.

## Reproduction

From `MemoryCore`, with the public MemoryCode repository at `$MEMORYCODE_ROOT`:

```bash
python benchmarks/topic3-be-agent-product-v1/memorycode_prepare.py \
  --dataset-root "$MEMORYCODE_ROOT" \
  --output benchmarks/topic3-be-agent-product-v1/memorycode-selection.json

npx tsx benchmarks/topic3-be-agent-product-v1/memorycode_packets.ts \
  --dataset-root "$MEMORYCODE_ROOT" \
  --selection benchmarks/topic3-be-agent-product-v1/memorycode-selection.json \
  --output benchmarks/topic3-be-agent-product-v1/memorycode-packets.jsonl --k 8

npx tsx benchmarks/topic3-be-agent-product-v1/memorycode_retrieval.ts \
  --dataset-root "$MEMORYCODE_ROOT" \
  --output benchmarks/topic3-be-agent-product-v1/memorycode-retrieval-results.json \
  --receipts-output /tmp/memorycode-retrieval-receipts.jsonl --k 8
```

Run `memorycode_model.py` once per GPU shard, then pass every shard to
`memorycode_score.py`. The scorer rejects missing/duplicate task arms, prompt
hash mismatches and source-session alignment mismatches.
