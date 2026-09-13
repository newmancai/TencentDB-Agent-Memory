# B delivery acceptance package

This directory turns the existing B research into a line-by-line review package.
It does not replace the full [research retrospective](../B_DEEP_RESEARCH_RETROSPECTIVE_2026-09-13.md)
or manufacture a positive result from a negative public comparison.

## Delivery matrix

| Required item | Reviewable artifact | Status |
|---|---|---|
| Research report + design | [retrospective](../B_DEEP_RESEARCH_RETROSPECTIVE_2026-09-13.md), [final handoff](../B_FINAL_HANDOFF_2026-09-13.md), this confidence boundary | pass |
| Public long-dialogue runner + structured baseline result | [protocol](PUBLIC_LONG_DIALOGUE_PROTOCOL.md), `delivery_eval.py`, `results/public-long-dialogue.json` | pass for delivery; feedback gain fails 3W/4L/5T |
| Selected implementation + comparison | `src/core/memory-feedback/`, instrumented loop 4W/0L/0T, natural extractor 2/2 + abstain 12/12 | pass as bounded component method; not commercial B |
| Off switch + forced-failure fallback | `runtime_contract_harness.ts`, `results/runtime-contract.json` | pass |
| Reviewable PR + adapter/porting notes | additive adapter and [PORTING.md](PORTING.md); existing draft PR #2 remains the publication vehicle | local patch ready; publication state must be checked separately |

## What “direct judgment” and “high confidence” mean here

The project does **not** claim that one classifier score directly establishes
memory quality. Confidence is separated by evidence level:

1. Public CUPID gives low-to-moderate component evidence. It is useful for
   scope/content diagnostics, but has assistant semantic judgments, four persona
   clusters and no memory-cause label. The feedback arm loses the frozen baseline
   3W/4L/5T while using 3.434x input tokens and 1.620x generation time.
2. Natural raw corrections give high precision only for creating a
   current-interaction **candidate**: exact answer target, exact user span,
   explicit-user authority and conservative abstention. “Candidate” is not a
   verified durable fact and does not identify which memory caused the answer.
3. The instrumented loop has stronger internal causal evidence because the same
   task is paired with include/omit, exact prompt spans and an independent local
   checker. It is still four scripted synthetic projects. Four wins give a
   two-sided exact sign-test p-value of 0.125 under a 50/50 null, so no population
   or commercial confidence claim is made.
4. End-to-end business confidence would require independent natural outcomes,
   repeated/clustered held-out runs and a same-model same-information baseline.
   The retrospective pre-registers a learned-gate threshold of at least three
   utility points with a positive 95% cluster-bootstrap lower bound and no severe
   regression increase. That test has not been reached because deterministic
   exact-scope rules already saturate the current task domain.

The causal paired design costs more calls than a single end-to-end run—twelve
Codex calls, 168,480 input tokens and 90.356 seconds for four instrumented cases—
but diagnoses whether exposing the candidate changes the checker result. Repeated
end-to-end runs are the right tool for population stability and business value;
they are not replaced by the cheaper component checks.

## Metric separation

- Public long dialogue reports output coverage/paired quality separately from
  prompt token and generation latency. It performs no L1 extraction or native L0
  retrieval, so those metrics are explicitly `not_applicable`.
- Natural extraction reports proposal correctness and abstention separately from
  causal outcomes. Runtime gate replay reports record counts, not accuracy.
- The instrumented loop reports actual L1 write + FTS retrieval as a path check,
  prompt-span injection and model outcomes separately. Its historic runner did
  not time L1 extraction/retrieval independently, so no fabricated p50/p95 is
  added; model-call wall time and token usage are reported.
- Runtime integration reports adapter elapsed milliseconds in every decision log.

## One-command local verification

From `MemoryCore`:

```bash
python benchmarks/topic3-b-delivery-v1/delivery_eval.py
npx tsx benchmarks/topic3-b-delivery-v1/runtime_contract_harness.ts \
  benchmarks/topic3-b-delivery-v1/results/runtime-contract.json
npx vitest run src/core/memory-feedback/*.test.ts \
  src/core/self-supervision/openclaw-recall-turn-bridge.test.ts
```

The public JSON intentionally contains both `pass` and `fail`: artifacts and the
baseline pass; positive feedback gain fails. That distinction is the delivery
contract, not an embarrassment to hide.

`results/delivery-summary.json` is the machine-readable five-deliverable index.
Its overall value is `pass_with_negative_public_gain`: the package is reviewable,
while the public feedback method remains a recorded negative result.
