# MemoryCode Codex update diagnostic

Date: 2026-09-14. This is a four-call development diagnostic, not a new
holdout or a product score. It answers one question left open by the earlier
Qwen3-4B run: can the fixed Codex coding model use verbatim history to follow a
later version of a coding rule?

## Fixed subset and arms

Use the already frozen MemoryCode packet file from the pinned public release.
Select exactly two update dialogues without looking at new Codex output:

- the update dialogue with the fewest sessions (`memorycode-079`, 3 sessions);
- the update dialogue with the fewest sessions in the official long-history
  class (`memorycode-219`, 20 sessions).

For each dialogue run two independent arms:

- `no_history`: the dataset role instruction and current coding request only;
- `raw_full`: the same instruction and request plus every verbatim session in
  the frozen full-history packet.

The requested backend is `gpt-5.6-sol`, reasoning `medium`, Codex CLI 0.153.4.
Each call is ephemeral in an empty read-only directory with user config,
project rules, memories, and web search disabled. The prompt forbids tools.
Arm order is reversed on the second dialogue. A timeout, nonzero exit, missing
usage/output, or any tool event stops the diagnostic; there are no retries.

## Evaluation and decision

Reuse the pinned MemoryCode AST/regex scorer unchanged. The primary metric is
strict correctness of the updated target rule; syntax validity and the
official-compatible active-rule mean remain visible. Save exact prompts,
events, stderr, outputs, usage, and wall time outside Git.

- If `raw_full` is correct on both dialogues and beats `no_history` on at least
  one, record that the earlier zero was model-dependent in this bounded pilot.
- If `raw_full` is correct on neither, record that verbatim history remains
  insufficient here even with Codex.
- Every other outcome is mixed/inconclusive.

No outcome automatically authorizes more MemoryCode calls, rule compilation,
prompt tuning, natural-use claims, or an open-source superiority claim.

