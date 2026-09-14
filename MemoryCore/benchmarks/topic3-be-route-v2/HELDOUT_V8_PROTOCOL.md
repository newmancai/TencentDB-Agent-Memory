# Path-enforced single-file full-raw replication v8 protocol

Date: 2026-09-14. Frozen before any v8 model call. v5, v6, and v7 remain formally invalid;
v8 is a new matrix and does not recover or reinterpret their exposed cells.

## Frozen inputs and execution

- Manifest SHA-256: `ebd47489f1280058432f08c3b6d4a4f7a9f712ea6f241a5b8c0df8ef70c1a378`
  at `.local-evidence/project-agent-route-v2-heldout-v8/manifest.json`.
- Checker SHA-256: `dfb8fd115cb7aeeeddce3739cda8dc941c1383f1a7f2736718cf85ae6aa42cbe`.
- Runner SHA-256: `498efceb9b728914edefe572936e2b89ad2a6ae466ecc110c220fb0d084182a8`.
- Backend: Codex `gpt-5.6-sol`, medium effort, ephemeral, controlled instructions,
  `web_search="disabled"`, 300-second hard limit.
- Arms: `no_history` and lossless `raw_full`, rotated order, two sequential tasks per family;
  16 scheduled calls. Retrieval/top-8 remains closed.

Each request names one editable source file, prohibits internet and outside-workspace search, prohibits
tests, docs, changelog, configuration, generated files, and bytecode, and permits at most one focused
smoke check. The runner now rejects every changed path outside the declared file and marks that cell a
severe regression. Isolated agent execution also sets `PYTHONDONTWRITEBYTECODE=1`.

The outer filesystem sandbox exposes only the current opaque lane clone. All eight clones are fixed at
the declared base, contain only the benchmark marker as an ignored untracked path, have no remotes, and
cannot resolve the reviewed head. Event logs are retained and scanned for model web search and forbidden
workspace paths. Execution failures remain arm-qualified indeterminate observations.

## Families and exposure boundary

- [hyperframe PR #167](https://github.com/python-hyper/hyperframe/pull/167), base
  `b57beaff1cce7d7b7c38ea3514a349cb05a80d3c`: SETTINGS identifiers and values use their full
  16-bit and 32-bit serialized fields.
- [jmespath PR #335](https://github.com/jmespath/jmespath.py/pull/335), base
  `2ad18b0e51ef3c22ef0d4bbeb11506746a39e228`: the parser cache uses insertion-order FIFO,
  capacity 512, hit-without-refresh, and no insertion after a concurrent removal failure.
- [pluggy PR #727](https://github.com/pytest-dev/pluggy/pull/727), base
  `6a7f8960eb4009b551f14030233cea7a64ccaf5d`: missing-hook-argument warnings point to the
  external caller through ordinary and `call_extra` paths.
- [zipp PR #154](https://github.com/jaraco/zipp/pull/154), base
  `d14b72023b442e0eab42d59a6d849e31c2ab243e`: listing children of a file raises
  `NotADirectoryError` while directory iteration remains intact.

zipp appeared in the frozen v7 matrix but received zero calls before v7 stopped. The other three
families are fresh. hpack, PrettyTable, and importlib_metadata are excluded because v7 exposed them.

## Checker preflight

For all four families and both stages, the declared base returns compatibility pass / behavior fail;
the exact reviewed head and a separately authored equivalent implementation return compatibility pass /
behavior pass. The jmespath stage-two check deterministically simulates the concurrent-mutation boundary.
The 24-result matrix is stored at
`.local-evidence/project-agent-route-v2-heldout-v8/preflight/checker-matrix.json`, SHA-256
`1c1921509928e2ff731237007fb2a39d7e283856d9ec684d775114f713fb9bfc`.

Every full-raw first task has 12 ordered user observations including the accepted maintenance decision.
The second task adds no history and tests accumulated same-topic behavior. No retrieval, compilation,
local model, GPU, production path, Gateway, or hand-authored answer enters an arm.

## Frozen interpretation

The first necessary task of each family is the independent quality unit; the cumulative control is not
an additional win.

- At least one completed new-family first-task split favoring full raw, with no completed first-task
  full-raw loss, is the minimum replication of v4's qualitative mechanism.
- Four first-task ties leave lossless full raw experimental and do not upgrade v4.
- A completed first-task full-raw loss blocks expansion pending mechanism review.
- Any timeout, cancellation, checker defect, isolation leak, output-scope violation, or missing audit
  receipt makes the whole v8 matrix invalid. A post-hoc checker cannot repair it.

Report every call, usage completeness, context bytes, wall time, changed path, and severe regression.
One run per cell is not a stable latency or cost estimate. v8 alone cannot establish product or
open-source superiority and cannot authorize learned selection or production enablement.
