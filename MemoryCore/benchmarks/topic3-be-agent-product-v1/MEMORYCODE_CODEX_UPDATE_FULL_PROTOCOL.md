# MemoryCode Codex complete-update diagnostic

Date: 2026-09-14. This is an exhaustive diagnostic over the update stratum of the already frozen
24-dialogue MemoryCode generation subset. It is not a new holdout: the public dataset, Qwen results,
and two earlier Codex rows are already open. Its purpose is to replace a deliberately selected two-row
probe with the complete fixed set of ten update dialogues, without changing the prompt or scorer.

## Fixed selection and arms

Use packet SHA-256 `ecabcda9142f5094cfa73b62ce1c41e6c87bad33633b2ccb2c29b1c69f1c76e4`.
Select every row whose frozen `target_status` is `update`, yielding exactly these ten IDs in packet order:

`memorycode-079`, `memorycode-113`, `memorycode-150`, `memorycode-179`, `memorycode-197`,
`memorycode-219`, `memorycode-249`, `memorycode-278`, `memorycode-321`, `memorycode-359`.

Run two independent arms for every dialogue:

- `no_history`: dataset role instruction and current coding request only;
- `raw_full`: the same instruction and request plus every verbatim prior session in the frozen packet.

Reuse `memorycode_codex_update.py::prompt_for` unchanged. Request `gpt-5.6-sol`, reasoning `medium`,
Codex CLI 0.153.4, and timeout 180 seconds. Alternate arm order by dialogue. Every call is ephemeral in
an empty read-only directory with user config, project rules, memories, and web search disabled. The
prompt forbids tools. There are no retries.

## Validity and reporting

A timeout, nonzero exit, empty final output, missing usage, or tool event makes the whole diagnostic
invalid. Preserve exact prompts, event streams, stderr, final messages, receipts, and timings outside Git.

Primary reporting is paired strict correctness of the updated target: wins, losses, ties, mean delta,
fixed-seed dialogue bootstrap interval, and exact two-sided sign test. Also report raw accuracy, syntax,
short/long strata, total/cached/non-cached input, output, reasoning output, and wall time. The AST/regex
scorer remains unchanged.

Because this is an open development stratum, even a favorable result only establishes model-specific
diagnostic evidence. It does not establish natural-user benefit, a population success rate, production
readiness, or superiority to an external open-source memory system. Do not tune a prompt, selector, or
compiler on these ten outputs.

