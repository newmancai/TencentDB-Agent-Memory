# Public long-dialogue method-validation protocol

The required public benchmark is CUPID, used only as a method-validation set.
CUPID publishes simulated user interactions filtered by human annotators; it is
not described as natural production traffic or a final business metric.

## Frozen data and sampling

- Hugging Face revision: `f6e5fdae9b31f2b400d6ceb281a6a6760cc00309`
- official source commit: `a8560cab293ae98be4fe260689d58bddf96b51ef`
- source parquet SHA-256: `6d68af09f7fbe52df0a3bd621604104696d0f481f166be5c06dd65bbb089aaae`
- release shape: 756 observations, 252 personas, three variants per persona,
  eight sessions and 32–129 messages per observation;
- split: 126 development and 126 validation personas. This protocol uses only
  four development personas, twelve tasks and two earlier development examples.

Sampling has no integer PRNG. After excluding 14 already used development
personas, sort by `SHA256("cupid-feedback-learning-v1:" + persona)` and take four.
Sort their tasks by `SHA256("learning-task:" + observation_id)`. The exact IDs
are in `../topic3-b-contextual-feedback-v1/results/learning/selection.json`.
One persona, not one variant, is the independent cluster.

## Arms and alignment

The four fixed arms are `request`, `frozen`, `unlabelled`, and `feedback`.
`frozen` is the ordinary same-model history baseline. `unlabelled` adds two
bounded development examples and their drafts. `feedback` sees the same two
examples plus controlled correction objects. The new task's hidden factor,
reference preference and checklist never enter model input.

Every selected task ID maps one-to-one to one adapted CUPID observation and one
four-arm receipt. The two injected correction objects map to the two
`training_ids` in the selection file. Official labels are opened only after
generation for semantic review; they are not per-memory correctness or causal
labels. This protocol therefore aligns prompt fragments rather than claiming a
durable MemoryCore entry is correct. The separate native raw replay establishes
exact L0 event provenance, not method quality.

All arms use the same local Qwen3-4B-Instruct-2507 artifact, greedy decoding,
24k input limit and 256-token output limit, with arm order rotated by task. The
historic run did not record an exact model revision, so none is invented here.

## Metrics and pass/fail

- `coverage`: reviewer judgment `full/partial/absent` for target preference
  content; the reviewer is an assistant, not an official automatic grader.
- `paired_quality`: task-level win/loss/tie for `feedback` against the same
  task's comparator. Feedback gain passes only if wins exceed losses against
  `frozen`; ties remain ties.
- cost: summed input/output tokens and per-call `model.generate` latency p50/p95.
  Quantiles use R-7 linear interpolation. Model loading, data preparation and
  human/assistant review time are excluded and not silently counted as zero.
- injection cost: feedback/frozen input-token and generation-time ratios.
- L1 extraction and MemoryCore L0 retrieval latency are `not_applicable` here;
  prompt evidence injection is measured separately from native storage.

Run the frozen inference with the commands in
`../topic3-b-contextual-feedback-v1/LEARNING_PROTOCOL.md`. Recompute the published
evaluation JSON without a model call:

```bash
python benchmarks/topic3-b-delivery-v1/delivery_eval.py
```

The runner must retain a failed feedback-gain check. Completing an experiment is
not the same as demonstrating a positive method result.
