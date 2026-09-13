# Topic 3 B+E — public long-dialogue method result

Date: 2026-09-12. **Negative quality result; optional research implementation ready
for review. No default activation or commercial/coding-business claim.**

## Main findings

PersonaMem v1 32k: 18 previously unused personas, 36 questions. Development uses
six personas/12 questions; evaluation uses twelve personas/24 questions. There is
zero persona overlap and zero identical user-source chunk overlap across splits.
The observed dialogues contain 99–230 messages; evaluation contains 104–215.
Full source prefixes are written to L0; user text chunks use the native L1 writer.
This does not evaluate learned L1 extraction. Query/options/answer boundaries and
candidate construction are in the versioned protocol.

| Evaluation arm | Public MC correct | E calls | Historical annotations | Exact-span audit: compatible / ambiguous (not action-error counts) |
|---|---:|---:|---:|---:|
| Native base | 10/24 | 0 | 0 | 0 / 0 |
| Fixed B+E | 10/24 | 48 | 16 | 13 / 3 |
| Adaptive B+E | 10/24 | 9 | 5 | 4 / 1 |

All three comparisons have 0 task wins, 0 losses, 24 ties. Development is 8/12
for all arms. The frozen policy changes behavior: evaluation E calls fall 81.25%,
but it skips 11/16 E-changed verdicts. These are NOT eleven established missed
truth changes. The verifier can conflate new activities, separate situations,
and past events with exact-assertion supersession, but its action validity requires
a separate current-use judgment. The single-pass assistant source
audit classifies the 72 bounded pairs as 68 compatible/same, four unknown, zero
clear refutations of the selected old propositions. It is not independent human gold, and supports no
global stale-memory coverage claim. See SOURCE_AUDIT.md for the complete audit.

This is a concrete no-gain result for the tested candidate/annotation configuration;
it does not establish that every annotation was wrong or that B+E is ineffective.
The candidate ranker often selects repeated wording rather than the state-bearing
assertion. Consequently, even a perfect judge of those pairs would not establish
global change coverage. NLI contradiction scores do not solve entity/time/scope
alignment, and learning to imitate a weak E's outcomes does not create high-confidence
feedback. No threshold, prompt, seed or candidate rule was retuned on evaluation.

### Independent reassessment of the negative interpretation

The original `source_audit_unsupported_annotations` field is an overstrong name:
it counts E-changed verdicts whose selected old proposition the first audit marked
compatible with later evidence. Compatibility of a past event does **not** establish
that adding a later-state annotation is unsupported. Signing up and later dropping
out can both be true, while the inference of continued enrollment becomes invalid.
The implementation retains the old text and appends later evidence; neither the
13 fixed nor four adaptive compatible-span counts is a verified harmful-update or
false-deletion count. Raw audit labels, predictions and scores are preserved; this
is a correction of interpretation, not a new scoring protocol or rerun.

Both members of every candidate pair were already in the common top-12 recalled
evidence. The E reviewer acquired no new observation, and the incoming query's
possible change signal was not offered to B as a source event. Thus this experiment
tests same-evidence temporal annotation and learned reviewer-call selection; it
does not test active evidence acquisition or complete streaming change discovery.
The five truncated evaluation outputs already start with the same wrong option
in all arms. Inspecting those prefixes gives no evidence of hidden gains, although
a future protocol should separate constrained option selection from format errors.

See [the research reassessment](REASSESSMENT.md) for the source checks, competing
explanations and the next version's falsifiable experimental design. No proposed
new route has been measured in this v1 result.

## Effects, costs, and their limits

| Evaluation arm | Generative input tokens | NLI input tokens | Output tokens | Measured component service p50 / p95 |
|---|---:|---:|---:|---:|
| Base | 50,551 | 0 | 137 | 411 / 651 ms |
| Fixed | 75,344 | 0 | 425 | 958 / 1,443 ms |
| Adaptive | 55,299 | 2,159 | 191 | 474 / 1,018 ms |

The quantiles sum measured per-task stages and are **not deployed wall latency**.
Evaluation NLI+E+reader service totals are 23.65s fixed versus 14.90s adaptive.
Including development, these totals become 37.86s versus 54.62s: NLI cold-start
cost outweighs the short evaluation-period saving. The 25.50s development NLI
time, including its first-use initialization, remains charged. Generation and
NLI tokens are separated because they are different models and costs.

Fixed and adaptive E receive the same source evidence. The paired harness executes
E once and charges each arm for the calls it would request; identical reader inputs
reuse deterministic outputs. Logical arm costs and actual experiment costs are
reported separately. The main run used 133 actual Qwen calls: 164,106 input and
875 output tokens, 52.824s recorded generation time. Failed/truncated generations
are included in these totals and in logical arm costs.

Five evaluation tasks have truncated reader outputs in all arms; these are scored
as failures, not repaired. Development has one base and two fixed/adaptive truncated
outputs. They are part of the negative result; the output budget was not increased
after seeing answers. The first launch occurred before model readiness and produced
only transport failures (zero model calls). Its output is retained separately as
`run/`, excluded from method scores; a provider-readiness check now fails before
the task loop. The completed experiment is `run-ready/`.

## Lifecycle and engineering evidence

- All 36 task histories preserve the original recalled record contents.
- Read failure, malformed state and timeout each return the exact native baseline:
  108/108 public-task checks.
- A fresh process reopens both native stores and the sidecar manifest: 108/108
  base/fixed/adaptive reads match the completed results.
- A separately identified public **development** transition (task
  `aa303aec-d355-4dc2-bae6-116e76aa0863`, message 57 -> 72) changes book-podcast
  listening from current activity to stopped. A known-target E fixture publishes
  a native replacement, preserves the other film-related text and original, and
  retrieves the historical annotation plus later assertion. It passes. This is
  an E integration example selected after diagnosing the candidate failure, not
  B discovery or additional test-set quality evidence. It adds one Qwen call:
  461 input/6 output tokens, 0.326s generation, and never trains the main policy.
- Repository tests: 176/176; adapter contracts: 2/2; plugin build passes. Runtime
  tests include off bypass, stale versions, scope/content corruption, read/score/
  policy/verifier failure, timeouts, late completion, duplicate/obsolete updates,
  history capacity and second lifecycle updates.

No physical deletion occurs. Byte preservation is an implementation check, not a
semantic retention guarantee. Wrong historical annotation can still change what a
reader believes; its observed downstream MC impact is zero wins and zero losses
in this small experiment, not proof of harmlessness. Complete stale suppression,
global false-positive rates and production recovery are not established.

An extra standalone TypeScript check with Node types found only the baseline's
uninstalled optional `node-llama-cpp` peer declaration; it is not reported as a
full typecheck pass. Required repository tests/build passed. All owned model
processes are stopped. No production Memory was accessed.

## Reproducibility and original-task acceptance

Public source revision: `a8076d5608c93ba2a28983cd78aa99b01a163ae7`.

| File | Bytes | SHA256 |
|---|---:|---|
| questions_32k.csv | 1305366 | cccd34cf53e0bc4d9536c04cff5ca045156d9a4e227e83327112482840bbc93c |
| shared_contexts_32k.jsonl | 5613210 | 217247ebfec9e8442fc53570c795ab69f21aad08745f7de78d9beab51b122d4a |

The deliverable provides the requested design/research position, public native
runner and structured results, B+E implementation and comparison, reproducible
off/failure checks, and dataset/evidence/scoring adapters with internal migration
instructions. It meets the **negative-result submission scope**, subject to the
reviewer's acceptance; it does not meet a claim of effective high-confidence
memory self-optimization. Merely calling a verifier does not resolve the B evidence
problem. The next research hypothesis, if pursued, concerns current-state claim
discovery and verifier qualification, rather than retuning this evaluation pool.

The following structured summary and per-task table are generated from the retained
raw receipts. They are included inline rather than committing generated JSON files.

```json
{
  "protocol": "topic3-be-v1",
  "splits": {
    "development": {
      "arms": {
        "base": {
          "tasks": 12,
          "correct": 8,
          "accuracy": 0.6666666666666666,
          "e_calls": 0,
          "annotations": 0,
          "source_audit_unsupported_annotations": 0,
          "source_audit_ambiguous_annotations": 0,
          "errors": 1,
          "input_tokens_including_nli": 25669,
          "output_tokens": 49,
          "nli_input_tokens": 0,
          "generative_input_tokens": 25669,
          "nli_service_ms": 0,
          "e_service_ms": 0,
          "reader_service_ms": 5039.486609166488,
          "component_service_p50_ms": 390.8290841271546,
          "component_service_p95_ms": 712.9983452376556
        },
        "fixed": {
          "tasks": 12,
          "correct": 8,
          "accuracy": 0.6666666666666666,
          "e_calls": 24,
          "annotations": 5,
          "source_audit_unsupported_annotations": 5,
          "source_audit_ambiguous_annotations": 0,
          "errors": 2,
          "input_tokens_including_nli": 38342,
          "output_tokens": 206,
          "nli_input_tokens": 0,
          "generative_input_tokens": 38342,
          "nli_service_ms": 0,
          "e_service_ms": 8436.543102608994,
          "reader_service_ms": 5775.97853471525,
          "component_service_p50_ms": 1017.1844574089387,
          "component_service_p95_ms": 2069.4535339317854
        },
        "adaptive": {
          "tasks": 12,
          "correct": 8,
          "accuracy": 0.6666666666666666,
          "e_calls": 24,
          "annotations": 5,
          "source_audit_unsupported_annotations": 5,
          "source_audit_ambiguous_annotations": 0,
          "errors": 2,
          "input_tokens_including_nli": 39490,
          "output_tokens": 206,
          "nli_input_tokens": 1148,
          "generative_input_tokens": 38342,
          "nli_service_ms": 25499.2096030619,
          "e_service_ms": 8436.543102608994,
          "reader_service_ms": 5786.431599874049,
          "component_service_p50_ms": 1077.4890553635864,
          "component_service_p95_ms": 13134.670980187906
        }
      },
      "paired": {
        "fixed_vs_base": {
          "wins": 0,
          "losses": 0,
          "ties": 12
        },
        "adaptive_vs_base": {
          "wins": 0,
          "losses": 0,
          "ties": 12
        },
        "adaptive_vs_fixed": {
          "wins": 0,
          "losses": 0,
          "ties": 12
        }
      },
      "candidate_pairs": 24,
      "e_relations": {
        "changed": 5,
        "same": 16,
        "unknown": 3
      },
      "adaptive_skipped_e_changed": 0,
      "fallback_checks": 36,
      "fallback_pass": 36,
      "original_history_preserved": 12,
      "l0_message_range": [
        99,
        230
      ]
    },
    "evaluation": {
      "arms": {
        "base": {
          "tasks": 24,
          "correct": 10,
          "accuracy": 0.4166666666666667,
          "e_calls": 0,
          "annotations": 0,
          "source_audit_unsupported_annotations": 0,
          "source_audit_ambiguous_annotations": 0,
          "errors": 5,
          "input_tokens_including_nli": 50551,
          "output_tokens": 137,
          "nli_input_tokens": 0,
          "generative_input_tokens": 50551,
          "nli_service_ms": 0,
          "e_service_ms": 0,
          "reader_service_ms": 10780.544457724318,
          "component_service_p50_ms": 410.9565673770412,
          "component_service_p95_ms": 651.0095306929718
        },
        "fixed": {
          "tasks": 24,
          "correct": 10,
          "accuracy": 0.4166666666666667,
          "e_calls": 48,
          "annotations": 16,
          "source_audit_unsupported_annotations": 13,
          "source_audit_ambiguous_annotations": 3,
          "errors": 5,
          "input_tokens_including_nli": 75344,
          "output_tokens": 425,
          "nli_input_tokens": 0,
          "generative_input_tokens": 75344,
          "nli_service_ms": 0,
          "e_service_ms": 12450.88083203882,
          "reader_service_ms": 11200.02317475155,
          "component_service_p50_ms": 957.7436710270704,
          "component_service_p95_ms": 1443.4793788483546
        },
        "adaptive": {
          "tasks": 24,
          "correct": 10,
          "accuracy": 0.4166666666666667,
          "e_calls": 9,
          "annotations": 5,
          "source_audit_unsupported_annotations": 4,
          "source_audit_ambiguous_annotations": 1,
          "errors": 5,
          "input_tokens_including_nli": 57458,
          "output_tokens": 191,
          "nli_input_tokens": 2159,
          "generative_input_tokens": 55299,
          "nli_service_ms": 840.8084593247622,
          "e_service_ms": 2518.941150745377,
          "reader_service_ms": 11537.312932312489,
          "component_service_p50_ms": 474.0826453492573,
          "component_service_p95_ms": 1017.9524707838136
        }
      },
      "paired": {
        "fixed_vs_base": {
          "wins": 0,
          "losses": 0,
          "ties": 24
        },
        "adaptive_vs_base": {
          "wins": 0,
          "losses": 0,
          "ties": 24
        },
        "adaptive_vs_fixed": {
          "wins": 0,
          "losses": 0,
          "ties": 24
        }
      },
      "candidate_pairs": 48,
      "e_relations": {
        "changed": 16,
        "same": 29,
        "unknown": 3
      },
      "adaptive_skipped_e_changed": 11,
      "fallback_checks": 72,
      "fallback_pass": 72,
      "original_history_preserved": 24,
      "l0_message_range": [
        104,
        215
      ]
    }
  },
  "actual_model": {
    "calls": 133,
    "input_tokens": 164106,
    "output_tokens": 875,
    "generation_ms": 52824.087623739615
  },
  "limitations": [
    "NLI score and E reviewer are fallible; no calibrated semantic confidence claim",
    "candidate coverage is conditional; global stale-memory recall is unknown",
    "source audit is single-pass assistant judgement, not independent human gold",
    "component service quantiles are sums of measured stages, not deployed wall latency",
    "identical deterministic E and reader outputs are reused across arms; logical arm costs are separately charged",
    "L0 text is stored via L1 episodic writer; no learned extraction comparison or coding-business claim"
  ]
}
```

| Task | Split | All three modes |
|---|---|---|
| d3c87d0b-b8e9-4ad3-80dd-440da22899ec | development | pass |
| 3903b4e6-b412-4900-b435-5a4d4b955d1b | development | pass |
| 5117e665-5204-44ae-9946-0c984965c04e | development | pass |
| 125bfe37-0589-4c4e-879d-3409857a2053 | development | fail |
| aa303aec-d355-4dc2-bae6-116e76aa0863 | development | pass |
| c184227e-848c-4bb4-b6e0-04be947a6b5f | development | fail |
| 27ea48b1-f44c-4681-a0db-a3d8c7a86516 | development | fail |
| 7929ddc3-cd4e-4090-8e8c-a3a796de0659 | development | pass |
| 7d41fe64-def7-42a3-997f-5e296a22484a | development | pass |
| 44c04db4-7f3c-4af9-b1a2-7aebfe0b27c8 | development | pass |
| c2c223e2-36e7-4af5-89b5-6caf6fa0c877 | development | pass |
| d83d7e84-1ea3-461c-8916-0d519efe092e | development | fail |
| e35caa23-d8d2-47bf-8b2e-38c1f2520491 | evaluation | pass |
| 14f4861a-612b-462b-9b6b-2d9f0f903be3 | evaluation | pass |
| 8528894e-b57d-4053-9f5d-e1d9f8bfa419 | evaluation | pass |
| a96a528a-b2c6-4da4-bf79-c606314cc057 | evaluation | fail |
| 5192ed85-2542-4790-b36b-3c6ac081289a | evaluation | pass |
| aeeb1507-1fed-4d48-82b1-583d9251f07a | evaluation | fail |
| 0db82c52-bb20-49ae-87ca-abdafbe767a1 | evaluation | fail |
| 2bfdcdc8-1052-4c38-902f-1a023d41509d | evaluation | fail |
| 0d47c704-6ad5-4587-8fdf-d6418a428ded | evaluation | fail |
| 27ad7552-b0e8-440b-b0e1-19c3c216e36a | evaluation | fail |
| bb0462d3-2527-4ed2-ac75-2869d57c851c | evaluation | pass |
| 5b19b568-0c8f-43ac-8fdc-7f0ce67604e5 | evaluation | fail |
| 932a77e4-2654-415b-9692-32d527ecb10e | evaluation | pass |
| 8d52f6de-0bc5-4cac-8873-ca57060186b3 | evaluation | fail |
| 6d9d885e-b8fd-47c7-9be8-8b3b35561b05 | evaluation | fail |
| bf1209ec-2d77-4385-be78-04abfba82f31 | evaluation | fail |
| 72cb814c-aa52-4f39-a647-24aec1e3037c | evaluation | pass |
| d2c42ca1-5b3a-48b4-b3cc-ea27b9bed8e3 | evaluation | fail |
| 37eef83c-8772-463f-847a-07d9f0500bbf | evaluation | pass |
| 8e77a1eb-94be-451f-8c6e-db50537a602e | evaluation | fail |
| ca958afd-7fb1-497b-9234-735115cc3813 | evaluation | pass |
| fe2e91a8-fd23-4ea7-a3f1-722a0396712d | evaluation | fail |
| 78d544c0-e6f5-479f-b27b-a4b3d7b590a7 | evaluation | pass |
| 2f795c6f-e04f-4af0-8ff4-feff57e54a48 | evaluation | fail |

## Recorded Qwen weight hashes

```text
75311d91bb08cf0b882913da464a1e722a31fb44db35208663487efb7a3d8ed6  model-00001-of-00003.safetensors
0b48adbb1f60e901153d91907ba11ce63bd4b8b584482e730f48808d055dfba1  model-00002-of-00003.safetensors
7dd39ccca5e4de123c74c14af44c9bf2eb75df33b4614382af0134528e060d5d  model-00003-of-00003.safetensors
```
