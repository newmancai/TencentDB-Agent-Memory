# MemoryCode complete-update Codex diagnostic results

Date: 2026-09-14. The complete fixed update stratum finished with 20/20 valid Codex calls. Under the
unchanged frozen scorer, full verbatim history beat no history on 7 of 10 dialogues, lost none, and tied
three. This materially strengthens the earlier selected two-dialogue observation, while remaining an
open public-data diagnostic rather than a product-comparison result.

## Execution integrity

- Requested model: `gpt-5.6-sol`, reasoning `medium`; Codex CLI 0.153.4.
- Source: all ten `target_status=update` rows in the already frozen 24-dialogue packet.
- Calls: 20/20 completed; syntax valid: 20/20; retries: 0; timeouts: 0.
- Missing usage: 0; tool or web events: 0; nonempty stderr files: 0.
- Every call used an empty read-only directory with user configuration, project rules, memories, and
  web search disabled. Arm order alternated by dialogue.
- The two tasks used in the earlier bounded diagnostic were freshly rerun; both reproduced their original
  pair outcome. No old receipt was mixed into this matrix.

## Frozen primary result

| Task | Sessions | Class | No history | Full raw | Pair |
| --- | ---: | --- | ---: | ---: | --- |
| `memorycode-079` | 3 | short | 0 | 1 | raw win |
| `memorycode-113` | 4 | short | 0 | 1 | raw win |
| `memorycode-150` | 5 | short | 0 | 1 | raw win |
| `memorycode-179` | 10 | short | 0 | 1 | raw win |
| `memorycode-197` | 15 | short | 0 | 0 | tie |
| `memorycode-219` | 20 | long | 0 | 1 | raw win |
| `memorycode-249` | 30 | long | 0 | 1 | raw win |
| `memorycode-278` | 40 | long | 0 | 0 | tie |
| `memorycode-321` | 50 | long | 0 | 1 | raw win |
| `memorycode-359` | 100 | long | 0 | 0 | tie |

- Overall strict accuracy: no history 0/10; full raw 7/10.
- Paired outcome: **7 wins, 0 losses, 3 ties**; mean delta `+0.70`.
- Dialogue bootstrap 95% interval: `[+0.40, +1.00]`, seed 20260914, 10,000 samples.
- Exact two-sided sign test over non-ties: `p=0.015625`.
- Short history: 4/5 versus 0/5; long history: 3/5 versus 0/5.

The no-history score is not a measure of generic Codex programming ability. These synthetic tasks ask for
code under mentor conventions that are intentionally absent from that arm. The comparison isolates whether
the model can recover an updated convention from supplied history.

## Frozen-scorer sensitivity

The three primary ties were inspected rather than treated as interchangeable failures:

- `memorycode-278` is a real target miss. Full raw generated a valid palindrome function, but did not use
  the required `_y` variable suffix.
- `memorycode-197` assigned every constructor attribute with `_t`, and `memorycode-359` assigned every
  constructor attribute with `_xt`. Both also obeyed prior rules that rename the receiver away from the
  literal `self`.
- The pinned official-compatible MemoryCode extractor only records constructor attributes reached through a name literally
  equal to `self`, and in the latter case the assignments are nested inside `try`. It therefore reports the
  target object as absent even though the generated attributes visibly satisfy the required suffix.

A separately implemented receiver-aware AST sensitivity follows the actual first constructor argument and
nested assignments. Its focused unit test rejects unrelated-object writes. It changes only those two raw
rows and yields **9 wins, 0 losses, 1 tie; full raw 9/10**. This analysis was added after outputs were visible,
so it is explicitly secondary: the frozen 7/10 result remains primary and unchanged.

## Cost

| Aggregate | No history | Full raw | Full-raw change |
| --- | ---: | ---: | ---: |
| Calls | 10 | 10 | — |
| Total input tokens | 116,270 | 256,448 | +120.56% |
| Cached input tokens | 78,336 | 62,464 | -20.26% |
| Non-cached input tokens | 37,934 | 193,984 | +411.37% |
| Output tokens | 4,879 | 11,150 | +128.53% |
| Reasoning-output tokens | 884 | 4,749 | +437.22% |
| Wall time | 180.223 s | 273.357 s | +51.68% |

Unlike the controlled repository matrices, full history is substantially more expensive here. Each cell
was sampled once; cache and service variance were not replicated. The valid conclusion is that the quality
gain purchases much more context and reasoning, not that this is an efficient production policy.

## Interpretation and boundary

On the same ten frozen update dialogues, the earlier Qwen3-4B full-history and raw top-8 arms both scored
0%. Codex full raw now scores 70% under the frozen extractor and 90% under the post-hoc receiver-aware
sensitivity. This is strong evidence that using feedback history depends heavily on the base model/agent
path; it is not evidence that model weights alone caused the difference.

The route decision remains simple: keep lossless raw history as the evidence-preserving default and do not
promote the existing compiler or top-8 selector. The remaining real miss and large cost are reasons to seek
a safe, update-aware representation on new development data, not to tune these ten outputs.

MemoryCode is synthetic, the full dataset is already open, prompts inject history directly, and no repository
tools or behavior checker are involved. This result does not replace the valid public-repository result or
a same-condition open-source system comparison. It supports a stronger public method
claim only: Codex can use verbatim multi-session history to follow updated coding conventions on most rows
of this complete frozen update stratum.

Raw evidence is stored at
`/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-memorycode-codex-update-full-v2`.
The committed JSON summaries record the source packet, selection, inputs, and receipts hashes. For archive
identity, the raw summary SHA-256 is
`54170d33738d422c06bb095131179a75a22a64acf61f9bf6fec83e760718e8fe`; the receiver-aware sensitivity
SHA-256 is `7be8b46c3c29db1edbba46101f8fcc71c096e1232f6d6c2c30b8d762e953dc9f`.
