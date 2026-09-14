# Held-out v8 invalid execution review

Date: 2026-09-14. v8 is formally invalid and stopped after two initiated calls. It provides no
memory-versus-no-history quality result.

## What happened

The first no-history hyperframe task completed normally in 43.871 seconds and changed only
`src/hyperframe/frame.py`. It widened the SETTINGS identifier mask to 16 bits but did not apply the
32-bit value mask, so the frozen behavior checker returned compatibility pass / behavior fail.

The runner nevertheless recorded the allowed source edit as an unexpected path and a severe
regression. `workspace_state` called `git_output`, whose global `.strip()` removed the leading blank
from the first porcelain-v1 status line. The valid ` M src/hyperframe/frame.py` entry became
`M src/hyperframe/frame.py`; the path parser then sliced it as `rc/hyperframe/frame.py`. This is a
runner defect, not an agent output-scope violation.

The root operator interrupted the matrix immediately after observing that frozen-invalidating event.
The raw-full hyperframe call was already in progress and is retained as an operator-cancelled receipt:
23.685 agent seconds, no file change, no checker, no usage. No jmespath, pluggy, zipp, or control call
was started.

## Evidence and bounded interpretation

- Results: `.local-evidence/project-agent-route-v2-heldout-v8/results-v1`.
- Receipts SHA-256: `192548b131b6a3486a25c7b6086efb85ce2b55d28aa482503e8fe1e5f39064f0`.
- Summary SHA-256: `c10e0138f6baa1ff64cd4710a2387a414fe07174e5a05da6df055476bf51bd7b`.
- Initiated cells: 2/16; completed and checkable: 1; operator-cancelled: 1.
- Accounted completed usage: 72,802 input, 59,008 cached input, 1,027 output, 193 reasoning-output
  tokens. Cancelled raw-full usage is unavailable.
- Filesystem isolation passed and visibility violations were empty for both receipts.

The completed no-history patch is a useful mechanism observation: the task prompt said only to apply
the accepted field-width decision, and the agent inferred the identifier half but missed the value
overflow boundary. It is not a paired win because raw-full was cancelled, and v8's scope classification
was defective. The mechanical v8 `severe_regressions=1` is explicitly withdrawn as a factual agent
regression; the raw receipt remains immutable.

## Recovery

`git_output` now removes only trailing line terminators, preserving the two-character porcelain status.
A repository-backed regression test asserts that the first tracked modification remains
` M src/value.py`, and the existing exact-file/directory classifier tests remain green. The project-agent,
agent-product, and route-runner suites pass (21, 16, and 5 tests respectively).

v8 will not be rerun. A v9 matrix may reuse jmespath, pluggy, and zipp only because they had zero v8
model calls, and must replace exposed hyperframe with a fresh family. v9 must freeze a new runner hash
and repeat base / reviewed-head / independent-equivalent checker preflight before any model call.
