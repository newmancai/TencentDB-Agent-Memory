# MemoryCode Codex update diagnostic results

## Outcome

The fixed four-call diagnostic completed without retries, timeouts, stderr, or
tool events. On the two selected update dialogues, `raw_full` scored 2/2 on the
strict updated target while `no_history` scored 0/2. Both pairs are wins.

This is bounded evidence that the earlier Qwen3-4B update result cannot be
generalized to Codex: on these same public task IDs, the earlier Qwen
`full_history` and raw top-8 arms both scored zero, whereas Codex used verbatim
history to apply the latest target rule. The difference is attributable to the
model/agent execution path as a whole, not isolated model weights.

| Task | History | No history | Full raw | Pair |
| --- | ---: | ---: | ---: | --- |
| `memorycode-079` | 3 sessions | 0 | 1 | raw win |
| `memorycode-219` | 20 sessions | 0 | 1 | raw win |

The frozen official-compatible active-rule mean was 0 for both no-history
outputs, 1.0 for the 3-session raw output, and 0.8333 for the 20-session raw
output. The long output names its attribute `r_stock_x`, which semantically
starts with the required `r_`; the pinned extractor records a miss because it
only discovers assignments through a receiver literally named `self`, while
this output uses `self_x`. The recorded score is not changed, and this does not
affect the target method-name result.

## Execution and cost

Requested configuration was `gpt-5.6-sol`, reasoning `medium`, Codex CLI
0.153.4. Every call was ephemeral in an empty read-only directory with web
search, user configuration, project rules, and memories disabled. All four
event streams contain only one completed agent message plus turn lifecycle
events; usage is present for every call.

| Aggregate | No history | Full raw | Raw change |
| --- | ---: | ---: | ---: |
| Calls | 2 | 2 | — |
| Input tokens | 23,247 | 34,488 | +48.35% |
| Cached input tokens | 11,648 | 16,128 | — |
| Non-cached input tokens | 11,599 | 18,360 | +58.29% |
| Output tokens | 1,255 | 2,531 | +101.67% |
| Reasoning output tokens | 119 | 891 | +648.74% |
| Wall time | 43.598 s | 62.951 s | +44.39% |

These are two single samples, not stable latency or cost estimates. The CLI
reports the requested model but does not independently expose a served-model
identity or account charge.

## Evidence and boundary

The fixed packet SHA-256 is
`ecabcda9142f5094cfa73b62ce1c41e6c87bad33633b2ccb2c29b1c69f1c76e4`.
Raw prompts, events, outputs, receipts, and summary are preserved at
`/home/edarace/Tencent-Memory-2/.local-evidence/topic3-be-memorycode-codex-update-v1/`.
Committed hashes and aggregates are in
[`memorycode-codex-update-results.json`](memorycode-codex-update-results.json).

The selection deliberately uses the shortest update and shortest official
long-history update, so it is a low-cost feasibility probe, not a representative
sample. MemoryCode is synthetic, the prompt directly injects history rather
than exercising the full MemoryCore runtime, and there is no natural-user or
open-source product comparison. The result supports keeping simple verbatim
history as the Codex-first route; it does not justify a compiler, learned
selector, prompt sweep, or automatic extension of this diagnostic.

