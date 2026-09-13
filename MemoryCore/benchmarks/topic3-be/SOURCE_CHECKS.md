# Public source and verifier checks

Checked on 2026-09-12. These are source-availability and contract diagnostics,
not replications of upstream quality results. No model calls were made.
The original v1 predictions and gold were not changed.

| Source | Pinned revision | Scope actually read |
|---|---|---|
| LongMemEval-cleaned | `98d7416c24c778c2fee6e6f3006e7a073259d48f` | oracle JSON: 500 questions, 78 knowledge-update; full s/m listed, not run |
| PersonaMem-v2 | `ed956dea41521fc4499acbc63f966e0fd3c053ba` | text benchmark: 5,000 rows / 200 personas plus one 32k history |
| HaluMem | `cb04336aa1b732d4b24f5186c552456b4099806e` | first complete user from HaluMem-Medium.jsonl only |
| LongMemEval-v2 | `f152293e235517d504809563c833d7190b8c713b` | 451 questions and one complete trajectory |
| MemTraceBench | `2a12240b36330aab5f40207c078eba0a2cc41194` | one RAG/LongMemEval graph with annotations |
| Supersede | `677993d3713c265329ac935262d3c08cbfa4cd63` | reward.py and one released training episode |
| VerMem | `4782751c79faa08421a27c23b4d02c591bc3357d` | public Python archive, particularly local_verifier.py |

## Label meanings

[PersonaMem-v2 text benchmark](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/blob/ed956dea41521fc4499acbc63f966e0fd3c053ba/benchmark/text/benchmark.csv):
3,431 same/self, 522 others, 1,047 updated/self. All 1,047 updated rows have a
preference beginning with `Do not remember`. This describes this table, not all
preference reasoning in the project.

[HaluMem-Medium](https://huggingface.co/datasets/IAAR-Shanghai/HaluMem/blob/cb04336aa1b732d4b24f5186c552456b4099806e/HaluMem-Medium.jsonl):
first user: 65 sessions, 718 memory points, 142 `is_update` points. The first two
updates add detail/goals; the flag is not a supersession label. These counts are
not extrapolated to the full dataset.

[LongMemEval-v2 schema](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2/blob/f152293e235517d504809563c833d7190b8c713b/SCHEMA.md):
86 dynamic-environment and 41 dynamic-environment-abs questions in the checked
question file. Task histories are not automatically one continuous world state;
the inspected schema supplies no per-memory invalidation labels.

## Executed Supersede matcher probes

The pinned [official reward.py](https://github.com/Vrin-cloud/supersede/blob/677993d3713c265329ac935262d3c08cbfa4cd63/src/supersede/reward.py)
was loaded directly without model/environment dependencies. Its `answer_matches`
returned the following:

| Answer | Gold | Actual result | Semantic issue |
|---|---|---|---|
| I do not live in Boston | Boston | true | negation still matches |
| Old value was Boston. Current value is unknown | Boston | true | historical mention matches current answer |
| Bob | Alice and Bob | true | incomplete conjunction matches |

Source SHA256:
`3cc03c858613a3055a67c4d019d61990258bdd492f49a1ff96d44c3f5ea8a249`.
These counterexamples refute general semantic reliability, not the paper's paired
score or an estimated benchmark error rate.

## Downloaded file checksums

| File checked | Bytes | SHA256 |
|---|---:|---|
| LongMemEval-cleaned oracle | 15388478 | 821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c |
| PersonaMem-v2 text benchmark | 42426457 | 95f2a8a324aab7baf2af937feae12731369e2abf7cad5ab3e170594cb25a3e52 |
| HaluMem first user | 1576966 | 8a12a384cc70661aa30892a1ca9c8e7c956bde94f59305e457723708e48aa465 |
| LongMemEval-v2 questions | 286186 | 0a3ae5ebea938c24d7800e1e0b0828e08ae1646f939a53853b2b8cdc08e292b7 |
| MemTraceBench checked graph | 7094948 | e7181b8c46ec7aa58a9c5a1886032f54d3f42aad62eb02b00b9861f60cdd630b |

Privileged gold, source-evidence labels and annotated faulty operations remain
outside runtime inputs. See [REASSESSMENT.md](REASSESSMENT.md) for conclusions
and [V2_PROTOCOL_DESIGN.md](V2_PROTOCOL_DESIGN.md) for the proposed next protocol.
