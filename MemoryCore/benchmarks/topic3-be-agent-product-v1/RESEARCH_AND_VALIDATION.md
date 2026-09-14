# Research and validation design

## Problem and claim boundary

The product target is memory self-optimization in long, multi-turn programming
work: after a checker result, user correction, tool receipt or changed project
constraint, the system should make a better memory action on a later task. The
action is one of `omit`, `include`, `verify` or `ask`; storing more text is not
itself success.

B is successful only when a fixed model and fixed evidence budget improve later
task utility over a strong non-learning baseline. E supplies source identity,
versioned replacement and reversible fallback, but cannot turn an unverified
feedback observation into truth.

This package therefore makes no claim that a single score directly judges memory
effectiveness. It separates:

1. component validity: IDs, spans, source versions, scope and checker authority;
2. method validation: paired behavior on public long dialogue;
3. product utility: repeated held-out coding tasks with real checkers.

Only the third level can support a coding-product claim. The first two are cheaper
and more diagnostic, but have weaker external validity.

## Related work and dataset choice

| Source | What it measures | Use here | Important limitation |
|---|---|---|---|
| [MemoryCode](https://github.com/Cohere-Labs-Community/MemoryCode) ([paper](https://arxiv.org/abs/2502.13791)) | Mandatory coding-instruction additions and updates over 1–100 noisy mentor sessions, scored by Python AST/regex | Primary public programming-memory method validation | Synthetic Python style tasks, not repository execution or natural user feedback |
| [CUPID](https://github.com/kixlab/CUPID) ([COLM 2025 paper](https://openreview.net/forum?id=JMxRn7orEk)) | Context-dependent preferences inferred from multi-turn feedback; 756 human-curated simulated histories | Secondary feedback-scope diagnostic | Preference/checklist labels are not memory-cause labels or programming outcomes |
| [LoCoMo](https://github.com/snap-research/locomo) ([ACL 2024 paper](https://aclanthology.org/2024.acl-long.747/)) | QA, event summarization and long-range temporal/causal understanding over ten very long conversations | L0 retrieval and answer regression | Factual QA does not show that feedback changed a memory policy |
| [LongMemEval](https://github.com/xiaowu0162/LongMemEval) ([ICLR 2025 paper](https://openreview.net/forum?id=pZiyCaVuti)) | Extraction, multi-session reasoning, temporal reasoning, knowledge update and abstention over 500 questions | E update/abstention component regression | End-to-end QA can improve through reader/context changes without B learning |
| [MemoryAgentBench](https://github.com/HUST-AI-HYZ/MemoryAgentBench) | Incremental accurate retrieval, test-time learning, long-range understanding and conflict resolution | Later adapter for learning/conflict breadth | Still simulated and not a substitute for repository checkers |

MemoryCode is the closest public source for the target programming interaction:
it changes the rules that later code must obey and contains both long history
and irrelevant interference. CUPID remains useful for deciding when a
correction applies. LoCoMo and LongMemEval remain retrieval/update breadth
regressions. Their scores must never be added into one synthetic B total.

## New primary public experiment

The frozen protocol, source hashes, exact subset, prompts and metric definitions
are in `MEMORYCODE_PROTOCOL.md`; results are in `MEMORYCODE_RESULTS.md`. Two
levels are deliberately separated:

- all 360 dialogues and 4,182 final-history queries exercise the open-source
  MemoryCore SQLite/FTS path without model calls;
- a hash-selected 24-dialogue subset covers every official history-length
  stratum and runs a 72-call fixed-model comparison of full history, label-blind
  MemoryCore top-8 injection and a privileged latest-rule ceiling.

Full-release retrieval finds only 45.89% of latest target sessions; 821 update
queries have 61.39% stale-source collision and 24.12% stale-only selection. The
model comparison reduces input to 23.20% of full history but yields only 1 win,
0 losses and 23 ties on strict target accuracy. Its bootstrap lower bound is
zero and sign-test `p=1.0`, so high-confidence gain fails. The oracle reaches
54.17% strict accuracy, including 50% on updates, while both non-oracle arms
score zero on update tasks. The next method must therefore improve extraction
and version consolidation, not tune `k` on the opened result.

## Historical CUPID diagnostic

`public_eval.py` is dataset-neutral: it consumes a manifest plus normalized JSONL
receipts. The committed fixture is a compact projection of the frozen CUPID run;
full generated text and reviewer packets remain in research PR #2. Source hashes
in the manifest bind the compact projection to those artifacts.

### Data and sampling

- CUPID Hugging Face revision:
  `f6e5fdae9b31f2b400d6ceb281a6a6760cc00309`;
- official source commit:
  `a8560cab293ae98be4fe260689d58bddf96b51ef`;
- parquet SHA-256:
  `6d68af09f7fbe52df0a3bd621604104696d0f481f166be5c06dd65bbb089aaae`;
- full release: 756 observations, 252 personas, three variants per persona,
  eight sessions and 32–129 messages per observation;
- frozen subset: four development personas, twelve tasks and 48 model calls;
- selection: exclude fourteen previously used personas, sort by the documented
  domain-separated SHA-256 keys, then take four personas and three tasks each;
- independent unit: persona, not task or turn.

The exact IDs, group names, sampling text and artifact hashes are in
`public-eval-manifest.json`. The historic Qwen3-4B artifact revision was not
recorded, so this package can exactly recompute metrics but does not pretend the
old model generation is bit-reproducible.

### Alignment

Each receipt ID maps one-to-one to one CUPID observation. `frozen` receives that
observation's user-message history. `feedback` receives the same two bounded
development examples as `unlabelled`, plus their controlled correction objects.
The current task's hidden preference and checklist stay outside inference and are
opened only for semantic review.

The experiment aligns injected prompt fragments, not durable MemoryCore records.
Consequently L1 extraction and native L0 retrieval metrics are explicitly
`not_applicable`; they are not recorded as zero. Runtime storage provenance and
fallback are validated separately.

### Metrics

- task outcome: reviewer `win=1`, `tie=0`, `loss=-1` for enabled versus frozen;
- cluster utility: mean task outcome inside a persona, then mean over personas;
- uncertainty: 10,000 persona-cluster bootstrap resamples with seed `20260913`
  and R-7 95% quantiles;
- cluster sign test: exact two-sided sign test over non-zero persona utilities;
- coverage: `full`, `partial` or `absent`, reported separately from preference;
- cost: total input/output tokens, generation p50/p95/sum, per-task injection
  token delta p50/p95 and enabled/baseline ratios;
- reliability: arm error counts, artifact/alignment pass and explicit modes.

High-confidence gain requires both a positive cluster-bootstrap lower bound and
cluster sign-test `p < 0.05`. This is still public component confidence, not a
business confidence guarantee.

## Recomputed result

The existing feedback arm remains negative:

- task outcomes: 3 wins, 4 losses and 5 ties;
- utility per task and cluster-mean utility: `-0.0833`;
- persona bootstrap 95% interval: `[-0.25, 0.0]`;
- cluster sign test: 0 positive, 1 negative and 3 zero clusters, `p=1.0`;
- feedback/frozen input tokens: `3.434x`, delta `+73,260`;
- feedback/frozen generation time: `1.620x`;
- full coverage: feedback 2/12 versus frozen 0/12, which is insufficient to
  overcome the paired losses.

The type split is diagnostic: changing has 2W/0L/2T, consistent 0W/3L/1T and
contrastive 1W/1L/2T. This suggests that indiscriminate correction injection
helps some changing cases but damages stable preferences. `instance_type` is a
post-hoc diagnostic label and must not enter inference.

Run from `MemoryCore`:

```bash
python benchmarks/topic3-be-agent-product-v1/public_eval.py
python -m unittest discover -s benchmarks/topic3-be-agent-product-v1 -p 'test_*.py'
```

## Expansion policy

The dataset has now been enlarged where extra volume is cheap and diagnostic:
retrieval covers the full 360-dialogue/4,182-query release. Model inference is
kept at 24 independent dialogues until a source-bound extractor can clear the
current zero-on-updates failure. Spending thousands of calls on the unchanged
raw FTS method would estimate a known failure more precisely without improving
the product.

The next fixed comparison must rerun full-history and raw-FTS baselines on the
same selected IDs, preserve every gold regex, and add one bounded extracted-rule
arm. Development may use the now-open MemoryCode release, but confirmation must
use either a pre-registered public extension or the held-out repository checker
protocol. LoCoMo/LongMemEval stay separate regression suites; CUPID stays a
scope diagnostic.

## Delivery status against the requested rubric

| Deliverable | Artifact | Status |
|---|---|---|
| Research and design | this document, `MEMORYCODE_PROTOCOL.md`, `OPTIMIZATION_REPORT.md`, final submission report | pass |
| Public long-dialogue runner and baseline result | MemoryCode prepare/packet/model/score runners and structured results | pass; raw 7/10 vs no-history 0/10, independent focus 9/10 to 10/10 |
| Implementation and comparison | `ProjectMemory`, project-agent host, public repository and MemoryCode comparisons | pass for the experimental product slice |
| Off switch and forced fallback | `runtime_contract_harness.ts`, `runtime-contract-results.json`, unit and package tests | pass |
| Portable PR and internal notes | draft PR #4, `PORTING.md`, final delivery index | pass for review; not production-enabled |

Negative public gain is retained as a first-class result. It explains why a
single classifier or reviewer is not high-confidence feedback and why the next
experiment must test selective action under equal information and cost.
