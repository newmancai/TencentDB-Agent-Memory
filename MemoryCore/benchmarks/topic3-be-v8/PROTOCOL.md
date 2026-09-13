# B v8: qualify a failure signal before blaming memory

2026-09-13, before any new model predictions. v7 failed to demonstrate useful
example-label learning. Repeating already-seen evidence cannot measure new
verification value. This round instead tests a prerequisite for B: whether an
observed failure warrants memory/retrieval investigation or belongs elsewhere.

Use the seven non-LongMemEval RAG graphs in MemTraceBench revision
`2a12240b36330aab5f40207c078eba0a2cc41194`: four LoCoMo graphs (16 annotations)
for controlled feedback fitting, three RealMem graphs (17 annotations) for
source-separated transfer evaluation. All such graphs and annotations are kept.
No synthetic additions, no replacement of difficult cases. These sources and
label counts were inspected during the source audit; this is an exploratory
transfer diagnostic, not a pristine confirmation or evidence of unseen-model
pretraining. RealMem has only three independent conversation groups.

Keep AnnotationError cases as non-memory controls. Official root-cause labels
were human annotated; explanatory reasons were subsequently polished by GPT-5.5.
Labels are not causal intervention results. The dataset contains selected failed
queries, so no overall natural-stream false-alarm rate can be estimated.

Runtime adapter allowlists the actual query, prediction and memory_context node
that directly fed that prediction through its question-answering operation.
No gold answers, judge output, final error type/operation, human reason, oracle
source-evidence selection, filesystem path or graph comments enter model input.
The immediate retrieval and answer operation IDs are remapped to local IDs.
Input nodes must exist before prediction completion; ambiguity is a recorded
adapter failure. Source labels live in a separate offline file. Identifying the
failure query itself is supplied controlled feedback, not automatic failure
detection. Source evidence is NOT expanded using annotated evidence IDs.

Native integration persists the actual retrieved-context string and reads it
back by record ID before judging. This checks a portable immutable evidence
record contract. It does not rerun the external RAG system in MemoryCore, test
MemoryCore retrieval quality, or transfer the external failure label to our core.

Frozen local Qwen3-4B-Instruct-2507, independent calls, greedy A/B/C/D max8tokens:
1. Direct: one joint judgment of query/context/answer, output memory, response,
   no demonstrated error, or unknown.
2. Factorized: first assess evidence sufficiency without showing the answer;
   separately assess visible answer misuse using the same full evidence.
   Fixed host rule: insufficient evidence -> memory candidate; sufficient evidence
   plus misuse -> response; sufficient evidence plus no visible misuse -> no
   demonstrated error; otherwise unknown. These are candidates, not authority
   for an E deletion. Factorization is tested as a hypothesis, not assumed valid.
3. Controlled feedback: a fixed L2 linear head with intercept and two features,
   sufficiency and misuse logits, fitted only on the 16 LoCoMo outcomes to predict
   RetrievalError versus other labels. Fixed ridge penalty1, no search. Score
   all three RealMem groups before reading their labels for scoring. Compare
   matched per-group budgets with direct memory probability, insufficiency score
   and deterministic ID order. Binary routing is separate from four-way accuracy.

Offline labels: RetrievalError -> memory; ResponseError -> response;
AnnotationError / JudgeError -> non-memory. Unknown types remain unevaluated,
not silently mapped. Fixed host decisions do not distinguish an actual annotation
error from a correct answer without demonstrated error; measure this mismatch.
Always-memory, always-non-memory and training-majority controls must be included.
Actual operation recall is scored only where a candidate operation applies;
non-memory cases cannot count as successful memory-operation localization.

No prompt examples, changes to extraction or index engines, persistent E actions,
or defaults. Context max16384tokens; over-budget/failed reads become explicit
unknown/fallback, not truncation or dropped rows. Up to three score calls per
query; report all acquisition, fitting and evaluation cost separately. Collect
single-example next-token logits directly to avoid v7 batch/generation mismatch;
these are model scores, not calibrated confidence claims. Report finite known
choices versus full-vocabulary argmax; an invalid argmax is a model failure.

Per-RealMem-group budget is one and two memory investigations, both declared
before outputs. Include every case; no global pooling of future users. A selected
human RetrievalError is a correct investigation target, not measured E repair
benefit. Same-source prefix streaming / selective missing feedback is not solved.
Report source-group wins/losses/ties, non-memory misattribution, stage agreement,
candidate operation reach, abstention, score errors, tokens, service p50/p95 and
total cost. Calibration sample size cannot establish high-confidence bounds.

Stop after this cohort and diagnose any negative result against the independent
annotations. Do not tune this evaluation cohort, extend the model prompt from
its failures, discard non-memory controls, or claim overall Topic3 acceptance.
