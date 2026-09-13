# Instrumented temporary-correction loop v1

2026-09-13, fixed before execution. This is the smallest host-integrated batch that
fills the trace fields absent from public conversational logs. It does not train a
gate or claim natural-user generalization.

Four new synthetic project configurations are written to isolated local authoritative
JSON files. For each project, MemoryCore writes and retrieves one deliberately stale
L1 fact from a real SQLite store. The exact rendered memory span is sent to Codex,
which answers a configuration lookup. A scripted explicit user correction matching
the authoritative file is then attached to that actual answer and passed through
`compileFeedbackAssertionCandidate`.

Within the same interaction, run two later answer actions using the same Codex model,
prompt, question, schema, and token budget:

- `include`: inject the current-interaction candidate;
- `omit`: do not inject it and require `UNKNOWN` when the value is absent.

Arm order alternates by case. Each action records the full candidate set, selected
IDs, policy version, exact prompt span, output ID, and marginal assignment propensity
0.5. Both paired actions are executed, so this is a blocked paired intervention, not
an online-policy IPS sample. The exact file value is visible only to the checker.

Model: `gpt-5.6-sol`, medium reasoning, isolated ephemeral Codex, no tools/browsing,
one call per initial/include/omit action, no quality retry. The fixed pass condition is
all 12 calls complete, include 4/4 correct, omit at most 1/4 correct, and four paired
include wins. Initial stale-memory accuracy is reported but is not a pass condition.

Passing proves only that the existing host trace/candidate machinery can execute and
measure a temporary correction intervention. Scripted corrections, exact-value tasks,
four projects, and current-interaction scope remain oracle development conditions.
Durable promotion and a learned gate stay off.
