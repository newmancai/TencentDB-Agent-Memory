# Topic 3 B+E reproducible delivery

Start with [DESIGN.md](DESIGN.md), [PROTOCOL.md](PROTOCOL.md), and
[RESULTS.md](RESULTS.md). The runtime is in `src/core/memory-feedback/` and is
optional. This delivery includes a public **negative method result**; it does not
enable automatic semantic lifecycle changes in the default plugin.

Read [REASSESSMENT.md](REASSESSMENT.md) for the independent negative-result
review and current research, [SOURCE_CHECKS.md](SOURCE_CHECKS.md) for actual
public-artifact checks, and [V2_PROTOCOL_DESIGN.md](V2_PROTOCOL_DESIGN.md) for the
next experiment design (not yet executed). The source-audit counts in the original
results are strict proposition judgments, not verified harmful-update counts.

The exact integration baseline is the public fork's `feat/anchor-memory` commit
`0ddea892f1e362b4b937b2b38d23beb2a5ac4329`, with the SQLite recordIds repair included
in this PR. The measured baseline is that native source-text path, not an assertion
that every file is identical to the suggested upstream release tag.

Run from `MemoryCore/`, Node >=22.16 (native SQLite), the normal npm dependencies,
and Python 3.10 with `requirements.txt`. The recorded run used CUDA torch 2.5.1+cu121
and Qwen/DeBERTa weights already present locally. Install models into user-selected
directories; never silently download a replacement model under the same name.
Qwen: `Qwen/Qwen3-4B-Instruct-2507`; NLI:
`cross-encoder/nli-deberta-v3-base@6c749ce3425cd33b46d187e45b92bbf96ee12ec7`.
Use a fresh output directory for each run. CPU-only torch cannot serve this GPU runner.

```bash
python benchmarks/topic3-be/download.py /tmp/topic3-data
python benchmarks/topic3-be/adapters.py --adapter persona --source /tmp/topic3-data --output /tmp/topic3-run/data
node --import tsx benchmarks/topic3-be/prepare.ts /tmp/topic3-run/data/tasks.json /tmp/topic3-run/native
python benchmarks/topic3-be/model.py score --model /path/to/nli --input /tmp/topic3-run/native/prepared.json --output /tmp/topic3-run/scores.json --device cuda:0
```

Start the local model in a separate terminal, retaining its PID for shutdown:

```bash
python benchmarks/topic3-be/model.py serve --model /path/to/Qwen3-4B-Instruct-2507 --output /tmp/topic3-run/model-calls.jsonl --device cuda:0
```

Wait for `{"ready": true, "port": 18779}`. Then:

```bash
node --import tsx benchmarks/topic3-be/run.ts /tmp/topic3-run/native/prepared.json /tmp/topic3-run/scores.json /tmp/topic3-run/results
python benchmarks/topic3-be/score.py --run /tmp/topic3-run/results --gold /tmp/topic3-run/data/gold.json --output /tmp/topic3-run/summary.json
node --import tsx benchmarks/topic3-be/verify-results.ts /tmp/topic3-run/native/prepared.json /tmp/topic3-run/results/results.jsonl /tmp/topic3-run/reopen.json
node --import tsx benchmarks/topic3-be/public-lifecycle.ts /tmp/topic3-run/native/prepared.json /tmp/topic3-run/public-lifecycle.json
```

The last command is a manually located **known-target development** transition:
enjoying/listening to book podcasts -> stopping them entirely. It checks actual
native lifecycle persistence/readback without implying B discovered that target.
It is separate from the 36-task paired main experiment and its feedback does not
enter the frozen policy. Stop only your own server after completion.

`summary.json` reports pass/fail per task/mode and full failed-generation costs.
`results.jsonl` retains exact records, source identities, selections, verifier
receipts, historical annotations, native reads and fallback reasons. `policy.json`
contains the frozen feedback state. Answers are read only by `score.py`.
Provide `--audit /path/to/source-audit.json` for source-audit metrics; omit it and
those metrics are null. Audit rows need `id`, `relation`, and an explanatory
`rationale`. The recorded audit was by the coding assistant, not independent humans.
QA labels alone cannot supply these relations or global stale recall.

Checks:

```bash
python -m unittest discover -s benchmarks/topic3-be -p 'test_*.py'
npm test
npm run build:plugin
```

Public inputs, raw results, native databases and model caches are deliberately not
committed. This matches the repository artifact policy. The report includes compact
structured results, per-task outcomes, hashes and the reproducible selection. No
private harness or mirror credential is required. Local delivery evidence is also
provided separately as an archive; database files and model weights are excluded.
