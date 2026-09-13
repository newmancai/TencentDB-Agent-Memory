# B temporal invalidation research review

## Question and connection to the earlier B work

The initial delivery established two different facts: exact, explicit
current-interaction corrections can be represented safely, while public
long-dialogue feedback did not beat its frozen baseline. The unresolved gap was
not another feedback-summary format. It was whether a later observation can
identify an older memory whose practical basis changed **without** turning broad
association into destructive over-update.

This is directly connected to the earlier target/scope work:

- exact answer targets and exact user spans protect the source boundary;
- scope predicates protect current applicability;
- the missing operation is temporal dependency discovery across interactions;
- discovery, final invalidation, and durable promotion must remain separate.

## Related work and method choice

[STALE](https://arxiv.org/abs/2605.06527) is a public benchmark focused on stale
memory: direct conflicts, propagated conflicts and downstream probes over long
contexts. Its [official repository](https://github.com/icedreamc/STALE) includes
CUP-Mem, whose code separates affected-bucket proposal, candidate selection and
invalidation judgment. That decomposition matches this project's previous
finding that attribution/scope discovery is not the same claim as final memory
correctness.

We therefore used STALE as a method-validation source, not a business metric and
not a claimed CUP-Mem reproduction. The three small experiments isolate the
component boundary before any end-to-end integration.

## Public data and reproducibility

- Dataset: `STALEproj/STALE`, CC BY 4.0.
- Hugging Face revision:
  `617c51dc200b5ab09970834144c7e51c77959af0`.
- Converted parquet: 288,947,099 bytes; SHA256
  `b432e28f13505096f87ad1cad0e5725fb8ea18297b125a4ca78d4b6f34160d53`.
- Rows: 400, comprising 200 T1 direct and 200 T2 propagated conflicts.
- Official code inspected at commit
  `ea7d391103a151927cd29d2f01d87597a782bdcb`.
- Each experiment selected four T1 and four T2 positives by a documented SHA256
  seed, excluded all earlier selected positives, and added eight cross-attribute
  negatives audited before inference.
- Inference saw only old and later observations. Type, explanation, probes,
  haystack and labels stayed evaluator-only.

Raw public data, prompts and Codex event receipts remain in local evidence and
are excluded from Git. Protocols, scripts and aggregate structured results are
reviewable in the three experiment directories.

Each runner exposes `prepare`, `infer`, and `score`. For example, from
`MemoryCore` with a Python environment containing `pyarrow`:

```bash
python benchmarks/topic3-b-stale-candidate-v1/stale_candidate.py prepare \
  --parquet ../.local-evidence/topic3-b-stale-v1/STALE-train.parquet \
  --out ../.local-evidence/topic3-b-stale-v1/candidate-v1
python benchmarks/topic3-b-stale-candidate-v1/stale_candidate.py infer \
  --out ../.local-evidence/topic3-b-stale-v1/candidate-v1
python benchmarks/topic3-b-stale-candidate-v1/stale_candidate.py score \
  --out ../.local-evidence/topic3-b-stale-v1/candidate-v1
```

## Results

| Configuration | Overall | T1 | T2 | Negatives | Calls | Outcome |
|---|---:|---:|---:|---:|---:|---|
| [Direct final binding](topic3-b-stale-binding-v1/RESULTS.md) | 13/16 | 4/4 | 1/4 | 8/8 | 16 | fail |
| [Proposal + final judge](topic3-b-stale-bridge-v1/RESULTS.md) | 13/16 | 3/4 | 2/4 | 8/8 | 48 total | fail |
| [Candidate-only proposal](topic3-b-stale-candidate-v1/RESULTS.md) | 15/16 | 4/4 | 4/4 | 7/8 | 16 | pass |

The direct binder was safe but too conservative on propagated conflicts. The
two-stage bridge recovered one T2 but lost one T1, producing no net gain while
roughly doubling decision calls and input. Its proposal stage suggested that
candidate discovery might be useful before the final judge. A fresh holdout then
confirmed the narrower claim: candidate-only expansion achieved 8/8 positive
recall and 7/8 negative retention.

The candidate experiment used 228,302 input tokens and 2,458 output tokens over
171.741 summed seconds, with 10.596/14.447 second per-call p50/p95. These are
model-call costs, not MemoryCore retrieval/injection costs. L1 extraction, L0
retrieval, injected tokens and downstream answer latency were not exercised and
remain not applicable here.

## Design decision

The optimized boundary is:

1. retrieve a bounded caller-owned old-memory universe;
2. use the later observation to nominate exact old bases via direct or possible
   dependency paths;
3. validate candidate ID, exact later-observation span, path count and `k`;
4. expose nominated IDs only to retrieval or verification;
5. never convert nomination directly into invalidation or durable promotion.

`selectDependencyCandidates` implements step 3 as an additive adapter. It has an
off switch, empty-addition fallback, bounded candidate/path/selection limits and
a decision log including mode, signal, `k`, counts, fallback and latency. Its
type and log both make the non-mutation boundary explicit. It is not wired into
Gateway.

## Confidence and next falsifiable test

This improves the research direction, not the final B verdict. Eight positive
and eight negative cases are enough to reject obvious method shapes, not to
claim high confidence. The negative controls are constructed cross-attribute
pairs, so they underrepresent hard same-topic non-causal associations; the one
false positive already shows that failure mode.

The next meaningful test is end-to-end and should use a new held-out source or a
substantially larger untouched STALE split:

- obtain a bounded candidate universe through ordinary MemoryCore retrieval;
- compare ordinary retrieval with retrieval plus candidate-only dependency
  nominations under the same answer model and information;
- include hard same-topic negatives, not only cross-attribute negatives;
- report candidate recall/precision separately from downstream answer utility,
  added injected tokens, p50/p95 latency and failure fallback;
- require positive held-out answer utility without severe-regression growth
  before considering a persistent or default path.

Until that test, the candidate interface remains experimental and off. The
direct-final and bridge-final configurations are closed; no further prompt
tuning on their used 32 pairs is justified.
