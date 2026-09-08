# Zero-explicit-feedback semantic experiment

This research adapter studies B feedback from ordinary user observations. It does
not deploy a general semantic invalidation policy. See `PROTOCOL.md`,
`NLI_V6_PROTOCOL.md` and the main B→E report for limitations and measured results.

## Dependencies and fixed inputs

Run Node commands from **MemoryCore**, with its dependencies installed (`tsx` must
resolve there). The code uses the published Anchor native writer/search/store,
not an unmodified upstream tag. Python entry points read local model files.

Tested environments, without implying other versions are equivalent:

| Use | Versions |
|---|---|
| Qwen3.5 service | Python3.11, torch2.5.1+cu121, transformers5.3.0, tokenizers0.22.2, accelerate1.12.0, safetensors0.8.0 |
| Embedding/NLI | Python3.11, torch2.5.1+cu121, transformers4.57.6, tokenizers0.22.2, sentence-transformers5.1.2 |

- Public dataset: [STALE](https://huggingface.co/datasets/STALEproj/STALE), revision
  `617c51dc200b5ab09970834144c7e51c77959af0`, file `T1_T2_400_FULL.json`.
- Qwen/Qwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`.
- Qwen/Qwen3-Embedding-0.6B; the experiment uses the existing local checkpoint.
- cross-encoder/nli-deberta-v3-base revision
  `6c749ce3425cd33b46d187e45b92bbf96ee12ec7` (Apache-2.0, English).

Downloaded data/model files are not bundled. `prepare.py` records the dataset
checksum and excludes ambiguous source alignments. It selects 48 public cases
by grouped deterministic hash order: 16 development, 16 calibration, 16 heldout.
Shared distractor sessions mean these are not fully source-disjoint samples.

## Execution order

1. `python prepare.py STALE_FILE ARTIFACT_DIRECTORY` emits `runtime.json`, separate
   `gold.json`, and `manifest.json`. The scripts are in this directory; paths below
   refer to them. The runtime format contains raw sources, order/timestamps, the
   actual new user turn and a later probe query. Gold is for offline scoring only.
2. For each permitted split, `embed.py runtime.json vectors.json --model MODEL_DIR
   --split SPLIT` computes real vectors. `node --import tsx
   research/memory-battle/anchor-semantic-v1/retrieve-hybrid.ts runtime.json
   vectors.json OUTPUT_PREFIX` creates isolated `/tmp` native stores and both
   `.fts.json` and `.hybrid.json` candidate files. No gold query selects candidates.
3. Start `model_server.py --model QWEN_DIR --receipts service.jsonl` with the Qwen3.5
   environment. The service binds loopback port18735 and currently shards across
   GPU0/1 with a 21GiB per-device limit. The sampled thinking experiment optionally
   loads `--generation-config generation-v5.json`; v6 explicitly overrides it.
4. `infer.py candidates.hybrid.json outputs.jsonl --model QWEN_DIR --split SPLIT
   --endpoint http://127.0.0.1:18735/v1 --prompts comparison-v6.json` runs direct
   and assertion proposals. Output is append/resume by `(id,arm)`; use a new output
   directory when changing protocol/configuration. Keep raw service receipts.
5. Run `nli.py candidates.hybrid.json nli.jsonl --model NLI_DIR --split SPLIT
   --device cuda:3`. For the combined lane add `--witnesses outputs.jsonl` and use
   a separate output file. `--device cpu` or another CUDA device is configurable;
   measured timings apply only to the tested execution, not all hardware.
6. `evaluate.py candidates.hybrid.json gold.json predictions.jsonl metrics.json`
   scores output rows. Combine the direct rows and the two NLI lane files when
   producing a shared report; raw assertion proposals are not the combined lane.
7. Finish calibration before heldout. `calibrate.py select metrics.json policy.json
   --arms direct nli assertion_nli` uses the predeclared grid/eligibility and refuses
   to overwrite a policy. Then run heldout with unchanged rules and use
   `calibrate.py heldout heldout.metrics.json policy.json --output final.json`.

For the saved naming convention, `summarize.py candidates.hybrid.json gold.json
ARTIFACT_DIRECTORY --split SPLIT --policy POLICY_FILE` performs steps6–7 with
explicit direct/NLI/combined lane selection. Development v6 reuses the unchanged
v3 direct output, supplied using `--generation PATH`; omit `--policy` in development.
The calibration command refuses to replace an existing policy.

Quote typography equivalence only aligns evidence; it is not semantic validation.
Unfinished thinking, unaligned assertions, overlong NLI pairs and missing outputs
are separate errors. Raw target agreement and calibrated acceptance must both be
reported; a rejected policy must not be advertised as successful zero-error memory.

## Internal-data adapter and scope

Replace preparation with an adapter emitting stable scoped source IDs, native
record/version identity, chronological observations and raw authorized text. Keep
gold/oracles in a separate evaluator. Do not reuse the public benchmark's known
change boundary or probe query as a live feedback-discovery signal. The public
semantic experiment tests selected change boundaries; it does not establish an
all-turn false-positive rate. NLI scores are not calibrated commercial probabilities.

MemoryCore raw records and Hindsight derived facts have different identity/provenance
granularity. Do not fabricate immutable Hindsight versions or count a whole source
document as exact target localization. The separate Hindsight runner retains raw
API results and provenance gaps. Receipt-driven E, native off/fault fallback and
bounded active views are implemented in the sibling `anchor-receipt-v1` directory.
This semantic experiment does not override those controls or operate on production.
