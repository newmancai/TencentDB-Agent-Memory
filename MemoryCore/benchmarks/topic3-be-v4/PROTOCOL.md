# B source-ID and proposition-support ablation v4

Before outputs, 2026-09-12. Development reuse; no new holdout, autonomous discovery,
learning, lifecycle mutation or QA claim. Select ranks16:24 per v2 stratum/hash,
same exclusions and privileged source pairing. Keep missing pairs. All500 oracle
targets are historically used. Runtime receives no QA, answer, type or support flag.

One common direct draft uses losslessly segmented old/later sources and selects
source IDs instead of copying quotes. Two second-pass arms see the identical
draft and evidence: ordinary review versus proposition-support review. All use
same JSON schema, Qwen3-4B, greedy, max256 tokens. Review order alternates. Compare
reviews at same call budget; charge the shared draft to both logical arms and
report actual calls separately. No retries or post-output prompt edits.

Relation changed = supported replacement of a matched current-valued attribute;
same = compatible addition or clearly different subject/attribute/scope;
unknown = uncertain alignment. Historical facts can survive current-value changes.
Member additions can change an explicitly established current aggregate.

Host checks ID existence and reconstructs original spans, NOT semantic support.
Independent source-only assistant silver is recorded before reading predictions;
report uncertainty/disagreement. Score raw relation and contract-valid feedback
separately. Include all errors and tokens. Primary test: support review improves
over ordinary review, not just over the one-call draft. IDs are a shared interface
repair, not a novel B benefit. No new model training from these labels.
