# Native Hindsight comparison runner

This runs the installed official Hindsight engine, with concise retention and
observations enabled. It is a configured local-model comparison, not a vendor
leaderboard result. Read [PROTOCOL.md](PROTOCOL.md) before interpreting results.
The first development case was stopped after repeat tool-envelope compatibility
errors. History/update consolidation and recall completed, native reflect did not.
See `STOP_RESULT.json`; no complete quality comparison is claimed. The current
Qwen3.5 XML function/parameter envelope is unsupported by the local JSON-only
translator. Fix that backend contract before attempting another native reflect run.
The user authorized stopping this route after the current negative results; no
remaining development cases were started.

## Dependencies

Use Python 3.11 with `hindsight-api-slim==0.9.2` and `pg0-embedded==0.15.1`.
The observed Python dependency inventory is in
`../competitors/hindsight/requirements-lock.txt`; it records the tested environment,
not a requirement to install every optional provider. The sibling `adapter.py`
normalizes native record IDs and source provenance without inventing versions.

Use separate model environments described in `../anchor-semantic-v1/README.md`:
Qwen3.5-9B uses transformers 5.3.0; the embedding service uses sentence-transformers
5.1.2 / transformers 4.57.6. Model and raw dataset files are not bundled.

## Run

Commands below run from MemoryCore. Replace model, runtime, output and Python paths.
The runner uses loopback ports 18735 (LLM), 18736 (embedding) and 65438 (PostgreSQL).
Do not overlap other inference experiments: cost counters cover the shared services.

```bash
python research/memory-battle/anchor-semantic-v1/model_server.py --model /path/to/Qwen3.5-9B --receipts /path/to/output/service.jsonl
python research/memory-battle/servers/qwen3-embedding-v0.1/server.py --model /path/to/Qwen3-Embedding-0.6B --port 18736 --device cuda:2 --batch-size 16 --max-sequence-length 8192
```

Run the services in separate terminals. The Qwen service uses GPU0/1; the embedding
service accepts a configurable device. These commands must use their corresponding
Python environments, not the Hindsight environment by accident.

On the tested Linux host, pg0 requires newer GLIBC than the host provides. The
optional helper starts it in an already cached Ubuntu22 image, without a GPU:

```bash
python research/memory-battle/anchor-hindsight-v1/start_database.py --manifest /path/to/output/database.json
python research/memory-battle/anchor-hindsight-v1/run.py /path/to/runtime.json /path/to/output/development --split development --limit 1
```

Use the Hindsight Python environment for these commands. The helper locates its
installed pg0 binary, or accepts `--pg0-binary`; `--image` overrides the cached
image. It never pulls an image automatically. The default container name is
`anchor-hindsight-runtime-20260908`. It creates a new temporary data directory,
binds PostgreSQL only to loopback, and records the exact container in the manifest.
The local database credentials are disposable `hindsight/hindsight`, not production.

The prefix run is a compatibility check, not a reportable comparison subset.
After it succeeds, omit `--limit 1` to continue the unchanged full development
split. Existing completed cases are skipped. An error stops further spending and
must be diagnosed; it is not a semantic score. `--resume-interrupted` only supports
interruption during initial history retention with unchanged model settings; later
phase reuse would risk exposing future evidence. `--resume-history-consolidation`
handles only the recorded history-only incomplete-round error, before any update
or B recall. Preserve interrupted-attempt costs. Native consolidation has a default
100-fact round limit; the runner drains successive rounds while pending decreases,
and stops on failed facts or no progress. Initialization attempts are also preserved.

Output includes native retention, both consolidation phases, recall, reflect,
source mapping gaps, operation timings and before/after service counters. All
operations must finish before quality scoring. The runtime input is the same raw,
timestamped `runtime.json` from the semantic adapter; no gold file is read here.

## Same-host B diagnostic scoring

The per-case `.b-candidates.json` files contain native derived facts retrieved
using the new observation before retaining it. Concatenate their JSON arrays for
the unchanged `../anchor-semantic-v1/infer.py` and `nli.py` runners, keeping the
same prompts, model settings and candidate count. This is a host-judge diagnostic,
not a feedback classifier implemented by Hindsight itself.

`evaluate_b.py runtime.json gold.json DEVELOPMENT_DIRECTORY predictions.jsonl
report.json --split development` scores those host outputs offline. Unlike the
raw-source evaluator, it follows `sourceDocumentIds` and reports source overlap,
no overlap and unknown provenance separately. A derived assertion sharing a
labeled source is not thereby proven to be the stale assertion. Do not compare
this coarser metric directly with raw-record exact localization as if identical.
Missing native cases remain in the full runtime split denominator; an unrelated
later reflect error does not erase an already completed B recall and judgment.
Report full native lifecycle status/cost separately from host-judge cost.

Run its focused checks with `python -m unittest discover -s
research/memory-battle/anchor-hindsight-v1 -p test_evaluate_b.py`.

Stop only this experiment's service processes and recorded container when finished:

```bash
docker stop anchor-hindsight-runtime-20260908
```

For internal data, replace the preparation adapter with authorized chronological
raw sources and stable source IDs. Preserve visibility boundaries and keep labels
outside this runner. The current one-bank-per-case evaluation and local loopback
services are not a production multi-tenant deployment.
