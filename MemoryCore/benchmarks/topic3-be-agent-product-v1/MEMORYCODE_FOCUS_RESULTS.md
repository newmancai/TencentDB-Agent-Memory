# MemoryCode quality-first focus and AI-infra results

Date: 2026-09-14. Evidence: `memorycode-focus-results.json`. This result uses public synthetic
MemoryCode data and Codex CLI `0.153.4` with `gpt-5.6-sol`, medium reasoning, isolated empty workspaces,
no tools, and complete raw event and usage receipts. It is method evidence, not a product success rate.

## Outcome

The first disjoint development set improved receiver-aware target accuracy from `7/10` to `9/10`, but
contained one regression (`3` wins, `1` loss, `6` ties). The regression was traced to a compiler mistake:
it treated a method prefix, suffix, required substring, and digit as mutually exclusive naming rules.

After one bounded mechanism correction, the second set was selected and committed before model calls.
It excluded all 24 earlier generation dialogues and all 10 first-set dialogues. On these 10 new update
dialogues:

| Metric | Raw full history | Focus + raw history | Paired result |
| --- | ---: | ---: | ---: |
| Primary receiver-aware target | 9/10 | **10/10** | **1 win, 0 losses, 9 ties** |
| Frozen literal-`self` target | 7/10 | 7/10 | extractor-sensitive |
| Frozen official-compatible active-rule mean | 88.67% | **91.78%** | secondary |
| Post-hoc receiver-aware active-rule mean | 89.44% | **97.00%** | 3 wins, 0 losses, 7 ties |

All `30/30` model calls were valid, with no retry, timeout, empty output, missing usage, or tool event.
The primary target delta bootstrap interval is `[0.00, 0.30]`; the exact two-sided sign-test value is
`p=1.0`. The post-hoc active-rule delta interval is `[0.00, 0.1533]`, with sign `p=0.25`. Therefore the
confirmation supports a directional, zero-observed-loss experimental result, not a statistically
high-confidence universal improvement.

The receiver-aware target extractor was fixed before second-set selection and calls. The receiver-aware
all-active aggregate was added after the run when inspection found that the pinned official extractor
penalized `self_g.attribute` while sometimes excluding a missing constructor from its denominator. It is
reported as a transparent deterministic sensitivity, not promoted over the frozen primary metric.

## Cold cost and reusable compiler state

The quality-first arm initially compiled the full history for every coding request and then sent the full
history again to the coding model:

| Second-set total | Raw full | Cold focus | Cold/raw ratio |
| --- | ---: | ---: | ---: |
| Input tokens | 257,843 | 518,542 | 2.011x |
| Non-cached input tokens | 189,747 | 384,398 | 2.026x |
| Wall time | 360.637 s | 615.355 s | 1.706x |
| Model calls | 10 | 20 | 2.000x |

The receipts separate the focus compiler from the coding stage. Persisting the compiler result by exact
history revision removes the compiler from an unchanged-history hot path. The already executed coding
stages used 260,138 input tokens, 208,938 non-cached input tokens, 349.318 seconds, and 10 calls. Relative
to raw full history, that warm path is `1.009x` total input, `1.101x` non-cached input, `0.969x` wall time,
and `1.000x` calls. Relative to cold focus, it removes 49.83% total input, 45.65% non-cached input, 43.23%
wall time, and 50% of calls.

This is exact stage decomposition from completed calls. The multi-request figures below are arithmetic
amortization, not a new repeated-load model run or dollar-price claim:

| Requests sharing one history revision | Input/raw | Non-cached/raw | Wall/raw | Calls/raw |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 2.011x | 2.026x | 1.706x | 2.000x |
| 2 | 1.510x | 1.563x | 1.337x | 1.500x |
| 5 | 1.209x | 1.286x | 1.116x | 1.200x |
| 10 | 1.109x | 1.194x | 1.042x | 1.100x |
| 20 | 1.059x | 1.147x | 1.006x | 1.050x |

The product implementation already places structured compilation at explicit feedback ingest and persists
accepted constraints with a monotonically increasing project revision. Ordinary coding runs read that
state without invoking the compiler. A new user observation changes the revision and therefore requires a
new bounded compilation; unchanged revisions reuse the persisted state.

## Rejected cost shortcuts

Two development-only checks were retained as negative results:

- `focus_compact` removed raw history from the second call. It reduced prompt transfer but changed the
  implementation to class-level state on the exposed 40-session task, moving the target from `1` to `0`.
  It was rejected before a new held-out set.
- `focus_cached` kept raw history and aligned both independent Codex CLI prompts to an identical long
  prefix. Quality tied `1/1`, but non-cached input remained `2.015x` raw; independent CLI processes did
  not demonstrate cross-call prefix reuse. It was also rejected before a new held-out set.

## Release decision

The result is sufficient for an **explicit experimental route**, not a default or commercial rollout:

- keep full raw history available to the coding model for the quality path;
- persist compiled guidelines by exact project/history revision and reuse them across unchanged-history
  coding requests;
- invalidate reuse whenever the history revision, compiler protocol, model, or reasoning configuration
  changes;
- preserve raw source, compiler output, code output, usage, and checker evidence;
- do not enable compact-history or independent-CLI prefix-cache variants;
- continue to describe the public gain as directional until a larger untouched confirmation or a
  same-condition open-source comparison supplies stronger evidence.

No removed “natural validation” count participates in this decision.
