# Public executable-receipt B→E experiment

Ordinary successful tool actions can reveal that a remembered field has changed without
the user explicitly correcting memory. This experiment maps observable receipts to scoped
record identities, preserves superseded history, and tests subsequent reads. It is a research
sidecar; it does not enable a production policy or establish general natural-language confidence.

See [protocol](PROTOCOL.md) and [results](RESULTS_AND_CHECKPOINT.md) for the comparison,
unknown labels, held-out-domain limitations and incomplete semantic challenge.

## Reproduce

The native API base is public `newmancai/TencentDB-Agent-Memory`, branch `feat/anchor-memory`,
commit `0ddea892f1e362b4b937b2b38d23beb2a5ac4329`, plus the separately identified SQLite
`recordIds` filter repair. It is not an experiment runnable by adding this directory to the
unmodified MemoryCore tag. Install the repository's normal Node dependencies first.

Obtain official `https://github.com/microsoft/STATE-Bench.git` at revision
`5644b1838d96bc4483da29642d058ecaa6f80f7f`. Its MIT-licensed TRAIN trajectories and executable
environments supply the data. Follow that repository's Python dependency instructions.
Use a fresh output directory; native.ts appends results and is not an overwrite/resume runner.
Run from MemoryCore, replacing `/path/to/...` with local locations:

```bash
python research/memory-battle/anchor-receipt-v1/prepare_replay.py --upstream /path/to/STATE-Bench --output /path/to/receipt-output
python research/memory-battle/anchor-receipt-v1/evaluate.py /path/to/receipt-output --split development
python research/memory-battle/anchor-receipt-v1/evaluate.py /path/to/receipt-output --split calibration
python research/memory-battle/anchor-receipt-v1/evaluate.py /path/to/receipt-output --split external_domain
python research/memory-battle/anchor-receipt-v1/evaluate_reads.py /path/to/receipt-output
node --import tsx research/memory-battle/anchor-receipt-v1/native.ts /path/to/receipt-output/external_domain-feedback.jsonl /path/to/receipt-output/external-native-fallback.jsonl
python -m unittest discover -s research/memory-battle/anchor-receipt-v1 -p 'test_*.py'
npx vitest run --config research/memory-battle/anchor-receipt-v1/vitest.config.ts
```

For the cost summary, run
`python research/memory-battle/anchor-receipt-v1/summarize_costs.py /path/to/receipt-output`.
This reads actual retained temporary stores and separates B CPU time, native verification time
and storage bytes; it does not estimate production latency from replay timing.

The replay manifest exposes any difference from recorded upstream tool responses. Runtime and
oracle JSONL are separate: only the scorer reads full state snapshots. Native JSONL contains
actual temporary database paths, persistence checks, changed-field reads and fallback checks.
No API key or model is required for this receipt experiment. It is not the official STATE-Bench
leaderboard harness or a new agent rollout.

## Port to internal multi-turn coding conversations

- Replace `prepare_replay.py` with an importer emitting the same scoped, ordered tool-event
  contract. Keep tool results as runtime evidence and test/outcome labels in a separate evaluator.
- Replace domain-specific mappings in `ReceiptAdapter` in `receipts.py`. Define which returned
  fields prove an executed change, entity identity, branch/worktree scope and operation mode.
  A proposed patch, command exit code or generated answer alone does not prove every intended
  file or business state changed. Unsupported evidence must remain unhandled.
- Reuse `FeedbackLedger` identity/history handling and `readControlled` with native stores.
  The evolving auxiliary structure is the active version view. The adapter itself is fixed;
  this does not demonstrate learned policy parameters. Capacity is bounded at 2048 history
  records and 4096 event IDs; capacity rejection commits none of the event and permits retry.
  Callers must honor capacity statuses and fall back instead of treating rejection as completion.
- Replace oracle comparison and subsequent-read labels with independently observable assertions
  for the internal environment. Joined/derived fields missing from the oracle remain unknown.
  Separate branch scopes and chronological evaluation before measuring commercial transfer.

The current reader assumes one dedicated store per task scope, as used in this experiment.
It is not a multi-tenant Gateway integration. Base and evolved stores are separate; disabling
the capability and auxiliary read failures use the original base store. Physical deletion,
TTL inference, task-failure causal attribution and unknown-API discovery are outside this result.
