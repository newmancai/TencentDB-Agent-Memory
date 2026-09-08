# Semantic B method verification: no commercial invalidation claim

The fixed public STALE sample has 16 development, 16 calibration and 16 heldout
cases. Raw observations, timestamps and MemoryCore native hybrid candidates are
the model inputs. Target labels remain separate and unchanged. Shared distractor
sessions and non-exhaustive positive target labels limit generalization claims.

Each table cell is **accepted / exact target matches**, before calibration policy:

| Method | Development | Calibration | Heldout | Heldout total wall seconds |
|---|---:|---:|---:|---:|
| Direct Qwen3.5-9B | 16 / 3 | 16 / 4 | 16 / 5 | 122.26 |
| Raw pretrained NLI | 4 / 3 | 2 / 2 | 7 / 4 | 2.27 |
| Assertion proposal + NLI | 4 / 3 | 5 / 5 | 5 / 4 | 156.68 |

The combined method retains the four raw-NLI heldout matches and removes two
off-target choices, but costs substantially more and still accepts a false
relationship between moving home and an earlier meal-preparation plan. Its score
on that error is approximately .98. Two models do not guarantee independent errors.
Native hybrid target availability was 10/16 development, 9/16 calibration, 7/16 heldout.

Calibration required at least five accepted cases and ≥90% exact target agreement
on a fixed threshold grid. Only the combined lane qualified; its frozen threshold
is zero **after** the NLI three-way contradiction decision. On heldout it accepts
5/16 with 4/5 matches (80%), failing to maintain the calibration criterion. The
other two policies remain disabled; their raw results above must not be replaced
with 0/0 abstentions to manufacture a comparison win.

Combined costs include all upstream assertion calls, including abstentions and
alignment errors. Heldout combined input/output tokens are 23791/3286; raw NLI uses
20446 classifier input tokens and no generated output. Token counts across a
classifier and a generator are not equivalent monetary costs. Combined alignment
errors were 2 development, 1 calibration, 0 heldout. Typography equivalence allows
only quotes/whitespace, preserving original responses; it does not prove semantics.

Earlier development relation prompting performed worse (12 accepted, 1 matched)
than direct judgment. A separate thinking-mode budget probe had three completed
calls exhaust 4096 tokens without final output; the fourth in-flight call completed
after client cancellation. All four service receipts are retained (15612 output
tokens, 746.90 generation seconds). This is not a full-sample method score.

No semantic invalidation policy is enabled. Even under an IID assumption, five
successes in five calibration decisions give only about a 54.9% one-sided 95%
lower bound on target agreement. This dataset additionally has dependent sources
and incomplete labels; it does not estimate commercial semantic error probability.

Receipt-driven B→E in the sibling directory has separate executable-state and
subsequent-read evidence. This semantic study does not replace that closed loop or
claim real programming-task success. Hindsight native integration is still being
verified separately; these results do not establish superiority over Hindsight or
commercial memory systems. No production Memory operations were performed.
