# Anchor

**Reliable Memory for Agents**

Anchor is an experimental memory feedback layer for TencentDB Agent Memory. It helps an agent keep useful facts while preventing one-off instructions—such as a reply format for a single ticket—from becoming permanent behavior.

The implementation works with ordinary task evidence. It does not require users to score, like, or manually correct memories.

> Status: development preview. The feature is opt-in and has not been enabled for production writes.

## Why Anchor exists

A weak extraction model can turn this conversation:

```text
Production remains blocked. A staging pilot is approved through 2027-03-31.
For this ticket only, reply as REVIEW|vendor|decision|expiry.
```

into a durable memory that mixes business facts with a temporary response protocol. The facts remain useful. The protocol can interfere with later tasks.

Anchor keeps the L0 source, reviews the L1 candidate against that source, and gives the candidate one of four outcomes:

- `retain`: keep supported long-term memory;
- `project`: copy independently supported fact sentences from the source;
- `quarantine`: keep the source available while withholding active behavior;
- `deferred`: leave complex update or merge work for later review.

## How it fits MemoryCore

```text
L0 source messages
  → Qwen L1 extraction
  → evidence-scoped admission
  → existing MemoryCore dedup
  → final-draft admission
  → active L1 or review queue

L1 recall / memory search
  → exact record and version capture
  → prompt exposure acknowledgement
  → task-bound tool observations
  → objective outcome validators
  → targeted intervention
  → unadjusted / adjusted task comparison
```

The online projection path uses deterministic source checks and adds no model call. Ambiguous semantic cases can be routed to an asynchronous reviewer.

## Initial results

All numbers below are development results. They are reported with their sample size and should not be read as a commercial product ranking.

| Evaluation | Baseline / unadjusted | Anchor / adjusted |
|---|---:|---:|
| LongMemEval feedback precision | 43.33% | Used to reject the lexical invalidation baseline |
| LongMemEval false invalidations | 34 | Automatic lexical invalidation disabled |
| Qwen3-4B cross-family strict exact | 2/4 | 4/4 |
| Qwen3-4B semantic facts | 4/4 | 4/4 |
| Severe regressions | 0 | 0 |
| Full lifecycle tokens | 13,995 | 13,578 (-2.98%) |
| Mixed-claim component cases | 10 active protocol fragments | 0; action 14/14, content 14/14 |
| Saved real Qwen candidate replay | 1 active protocol fragment | 0; facts preserved 3/3 |

The `2/4 → 4/4` end-to-end gain came from instruction-scope admission. The newer mixed fact/behavior projection is supported separately by 14 component cases and a read-only replay of a saved Qwen candidate.

## Code map

| Path | Purpose |
|---|---|
| [`src/core/self-supervision/evidence-scoped-admission.ts`](../../src/core/self-supervision/evidence-scoped-admission.ts) | Source and scope checks; safe fact projection |
| [`src/core/self-supervision/final-draft-admission.ts`](../../src/core/self-supervision/final-draft-admission.ts) | Post-dedup review of the exact write draft |
| [`src/core/self-supervision/recall-shadow-adapter.ts`](../../src/core/self-supervision/recall-shadow-adapter.ts) | Exact retrieval identity, budget, and exposure evidence |
| [`src/core/self-supervision/tool-execution.ts`](../../src/core/self-supervision/tool-execution.ts) | Task-bound observations from real tool results |
| [`src/core/self-supervision/execution-feedback.ts`](../../src/core/self-supervision/execution-feedback.ts) | Objective outcomes and failure-stage localization |
| [`src/core/hooks/auto-recall.ts`](../../src/core/hooks/auto-recall.ts) | Recall intervention and shadow capture |
| [`src/core/tools/memory-search.ts`](../../src/core/tools/memory-search.ts) | The same exact exclusion for explicit search |
| [`src/core/record/l1-extractor.ts`](../../src/core/record/l1-extractor.ts) | Admission integration around extraction and dedup |

## Verify locally

Requirements are the same as MemoryCore: Node.js 22.16 or newer and installed npm dependencies.

```bash
cd MemoryCore
npx vitest run
npm run build:plugin
```

The clean fork snapshot passes 18 test files and 173 tests. The plugin build produces six files (about 1.22 MB).

Run the zero-model mixed-claim benchmark:

```bash
node --import tsx \
  research/anchor/scripts/run_mixed_claim_projection_benchmark.ts \
  /tmp/anchor-mixed-claim-result.json
```

Saved run plans and machine-readable outputs are under [`results/`](results/). The end-to-end scripts require the PAST/Hermes task environment and a local OpenAI-compatible model endpoint.

The professional Chinese report is available as [`Anchor_技术报告.pdf`](report/Anchor_技术报告.pdf), with [HTML](report/Anchor_技术报告.html) and [Markdown](report/Anchor_技术报告.md) sources kept alongside it.

## Design references

Anchor follows public patterns found in commercial and open memory systems:

- source or episode retention;
- user, project, session, and task scope;
- separation of facts, episodes, and behavior rules;
- update history, invalidation, and user control;
- deterministic checks on the synchronous path, with expensive review reserved for ambiguous cases.

See [`notes/`](notes/) for the Anthropic, OpenAI, Google, AWS, Mem0, Zep/Graphiti, Hindsight, Letta, LangGraph, and A-MEM review.

## Current limits

- The latest end-to-end slice contains two source families and four target outcomes per arm.
- Repeats used a fixed local model and seed, so they are consistency checks rather than independent statistical samples.
- Sentence-level projection quarantines facts that cannot be safely separated from a temporary protocol.
- Conflict resolution, multi-source updates, TTL, and durable production rollback remain future work.
- No production Memory record was written, deleted, or down-ranked during these experiments.

## License and attribution

Anchor is developed as a feature branch of [TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory). The upstream repository is licensed under MIT; the original copyright and license are preserved at the repository root.
