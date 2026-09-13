# STALE implicit-update binding v1

Frozen before model calls on 2026-09-13. This is a bounded component study of the
next unresolved B question: can a later user observation be bound to an older
memory as an implicit supersession, including propagated conflict, without
over-updating unrelated state?

## Public source

- dataset: `STALEproj/STALE`, CC BY 4.0;
- dataset revision: `617c51dc200b5ab09970834144c7e51c77959af0`;
- Hugging Face converted parquet SHA-256:
  `b432e28f13505096f87ad1cad0e5725fb8ea18297b125a4ca78d4b6f34160d53`;
- official code commit: `ea7d391103a151927cd29d2f01d87597a782bdcb`;
- source shape: 400 expert-reviewed scenarios, 200 T1 direct/co-referential
  conflicts and 200 T2 propagated conflicts. The official benchmark also has
  three downstream probes, but this component run does not score those probes.

STALE is generated/synthetic expert-reviewed data, not natural user feedback or
production traffic. Prior local work inspected only its metadata; this run is a
new method-validation use, not a held-out business claim.

## Selection and labels

Within each conflict type, sort by
`SHA256("topic3-b-stale-binding-v1:" + uid)` and take four: eight positive pairs
total. Their hidden `explanation`, conflict `type`, probing queries and haystack
never enter model input.

Create one negative for each selected old observation before inference:

- the four T1 old observations receive the next T1 selected row's later
  observation in cyclic order;
- the four T2 old observations receive the reverse-index T1 selected row's later
  observation.

The main agent audited the actual eight negative pairs before calls: subscription
vs stamina, stamina vs room light, room light vs decor preference, decor preference
vs subscription, blanket possession vs decor preference, local file storage vs
room light, belongings insurance vs stamina, and neighbor relationship vs software
subscription. In each pair both observations can remain true. The audit, rationale
and pair IDs are saved.
No negative is selected or changed after seeing model output.

Gold actions are `supersede` for the eight original expert-reviewed pairs and
`retain` for the eight audited cross-attribute pairs. `ask` is allowed for safe
runtime behavior but scores incorrect here because all sixteen labels are fixed.

## Model and output contract

Sixteen isolated Codex calls use `gpt-5.6-sol`, reasoning effort `medium`, one pair
per call, no retry. The model sees only chronological `old_observation` and
`later_observation` plus the fixed decision instructions. It must return:

```json
{"action":"supersede|retain|ask","evidence_quote":"...","reason":"..."}
```

`supersede` requires a non-empty exact substring of the later observation;
`retain/ask` require an empty quote. Malformed output, nonzero exit, or invalid
span is retained as a failure.

## Baselines, metrics, and exit

Report overall and class accuracy, T1/T2 positive accuracy, confusion counts,
exact-span validity, calls, token usage and wall-time p50/p95. Fixed baselines are
`always_supersede` and `always_retain`; a no-tuning surface baseline predicts
supersede whenever the two observations share any lowercase alphanumeric token
after a fixed English stopword list.

The component passes only if all hold:

- overall at least 14/16;
- positive supersession at least 7/8;
- T2 propagated supersession at least 3/4;
- negative retention at least 7/8;
- every predicted positive supersession has a valid exact later-observation span.

Pass permits designing a candidate-only implicit-update adapter. It does not
authorize durable promotion or a learned gate. Failure stops this prompt/model
configuration without repairing the same sixteen examples.

Commands:

```bash
PYARROW_PYTHON=/path/to/python-with-pyarrow
$PYARROW_PYTHON stale_binding.py prepare --parquet STALE.parquet --out NEW_RUN
python stale_binding.py infer --out NEW_RUN
python stale_binding.py score --out NEW_RUN
```
