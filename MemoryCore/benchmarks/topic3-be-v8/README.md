# Reproduce the B attribution diagnostic

Read PROTOCOL.md, CONTEXT_PROTOCOL.md and RESULTS.md first. This evaluates an
attribution component on external RAG failures, not MemoryCore failure recovery.
MemTraceBench data and provenance: https://huggingface.co/datasets/zjunlp/MemTraceBench
(MIT). Seven pinned RAG graphs total approximately180MB; no full6GB download.

From MemoryCore, use fresh directories and a Python environment containing the
existing benchmark model dependencies plus numpy. Native steps need the existing
package dependencies, `tsx`, and SQLite; do not use degraded storage.

```sh
python benchmarks/topic3-be-v8/download.py /tmp/v8-data
python benchmarks/topic3-be-v8/prepare.py /tmp/v8-data /tmp/v8-data/adapted
npx tsx benchmarks/topic3-be-v6/native.ts /tmp/v8-data/adapted/native-input.json /tmp/v8-data/native
python benchmarks/topic3-be-v8/score_model.py /tmp/v8-data/adapted/tasks.json /tmp/v8-data/native/records.json /tmp/v8-data/model --model /path/to/Qwen3-4B-Instruct-2507
python benchmarks/topic3-be-v8/evaluate.py /tmp/v8-data
python benchmarks/topic3-be-v8/score_model.py /tmp/v8-data/adapted/tasks.json /tmp/v8-data/native/records.json /tmp/v8-data/model32 --model /path/to/Qwen3-4B-Instruct-2507 --max-input-tokens 32768 --resume-context-failures /tmp/v8-data/model/results.jsonl --last-token-only
python benchmarks/topic3-be-v8/evaluate.py /tmp/v8-data model32
```

The second model invocation reuses successful scoring receipts exactly and only
computes previous context-limit failures. It requires the corresponding first
invocation with unchanged tasks, native records and prompts. Do not reuse receipts
from other model versions/protocols; exact output reproduction across GPU kernels
is not promised. Both original and completed results remain distinct.

For CPU-only metric replay, without models/data downloads:

```sh
python benchmarks/topic3-be-v8/replay.py /tmp/fresh-v8-replay
python -m unittest discover -s benchmarks/topic3-be-v8 -p 'test_*.py'
```

To port to internal programming sessions, supply the same query, actual injected
context, answer, operation identity and checkpoint fields from real logs. Replace
the MemTrace graph adapter and offline feedback/reference provider. Reuse
model_input, feedback fitting/ranking and scoring contracts; don't copy benchmark
error labels to newly run MemoryCore traces. A test failure can identify an event
but does not itself prove memory blame. Internal source availability, task intent,
multi-cause failures, sensitive trace access and genuinely useful repairs still
need validation. No internal data or private harness is required by this release.
