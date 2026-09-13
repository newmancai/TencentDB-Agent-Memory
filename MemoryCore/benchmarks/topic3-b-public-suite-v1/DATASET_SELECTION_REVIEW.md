# 近期公开数据集选择复盘（2026-09-13）

结论不是“数据越多越好”，而是用彼此正交的公开合同补齐 B 主线：H6 测失败记忆投放时机，AMB 测编码任务执行和实际 E 回执，ValidMem 测生命周期，Trigger Bench 测该不该读写以及不该相信什么。四个分母、指标和结论分开报告；公开集只作方法验证，不包装成内部业务指标。

## 本轮纳入

| 数据 | 截止版本 | 为什么现在纳入 | 当前完成度与边界 |
|---|---|---|---|
| [ValidMem](https://huggingface.co/datasets/Zhou11Alex/ValidMem) | `786d5cd9...`，v1.1，2026-08-26 | 466例/1,393记忆，同时覆盖事件替换、时间过期、current/history；恰好检验 B 状态是否把“可见”误当“仍有效” | 全量适配，标签隔离，保留69个空ground-truth到期例；尚未运行模型，不能报CRR/EAR |
| [Agent Memory Trigger Bench](https://huggingface.co/datasets/wallfacers/agent-memory-trigger-bench) | `f64b9214...`，2026-08-30 | 172个Codex/Claude/OpenCode CLI微场景，以真实操作trace和最终store判断读写触发；含注入、实体混淆、过时、secret、环境冲突 | 全量适配，90正/82负，46预置store、2工作区；尚未接MemoryCore host实跑，上游成绩不是本项目成绩 |

ValidMem 的 `tasks.json` 只给出当前日、问题、打乱后的选项，以及按上游四个引用列表合并并按创建时间排列的 store；`gold.json` 才保存 ground truth、superseded/expired/irrelevant 身份和正确选项。标准化 `expiresDay` 是上游明确建议使用的源字段，不是本项目从答案反推的标签；冲突实体、替换关系等 evaluator 注释不暴露。源数据有1例只有正确选项、没有干扰项（`TC-B-0185`），不临时删除；正式结果需同时报告包含全量466例和排除此例的敏感性结果，避免一个必然命中样本抬分。

Trigger Bench 的 `tasks.json` 只包含用户 prompt、初始记忆和可选工作区文件；正负 trigger、模块名、内容包含/排除规则都在 `gold.json`。正式评测必须用隔离 store，按实际 read/write trace 和 turn 后 store 判定，不能只让模型输出“我会查记忆”。

## 下一批而非当前主线

| 数据 | 价值 | 暂不混入当前总结果的原因 |
|---|---|---|
| [ISETrace Memory Queries](https://huggingface.co/datasets/HazeLocus/ISETrace-Memory-Queries) | 6,597个已完成软件工程轨迹查询，答案是可定位 exact span；适合 L1 证据抽取和跨项目检索 | 它检验已完成轨迹的证据找回，不直接给在线反馈更新因果；仅500条完成双模型+人工验证。待 Trigger/ValidMem host 协议稳定后单列接入 |
| [AutoMemoryBench](https://huggingface.co/datasets/Multilingual-Multimodal-NLP/AutoMemoryBench) | 5,760 case、120,960 probe，适合大状态容量压力 | 许可元数据未明确，先审计再使用，不能为扩大数字直接进主结论 |
| [AgentArtifactCorpus](https://huggingface.co/datasets/searchsim/AgentArtifactCorpus) | AGENTS/CLAUDE/rules 形态可用于有限规则候选诱导 | 是训练/分析语料，不是带客观结果回执的主评测 |

## 明确排除或降级

- [Agent Memory Compaction Trajectories](https://huggingface.co/datasets/rmems/agent-memory-compaction-trajectories)（2026-09-01）有2,044条最新压缩轨迹，但数据卡明确标记原始未清洗，训练与再分发权利仍待解决；只列相关工作，不下载进主协议、不训练。
- [Memory-augmented SFT](https://huggingface.co/datasets/huyxdang/adaption-agent-memory-augmented-v1)（2026-09-12）有27,934行，但无清晰许可元数据，数据卡自报质量B且相对质量变化为负；不因“更新更近”替代公开验证集。
- [Mnemosyne Lifecycle Benchmark](https://huggingface.co/datasets/solsticestudioai/mnemosyne-memory-lifecycle-benchmark)只有40场景，数据卡称25/40对受测系统不具区分性且许可元数据不清；与ValidMem重叠后不再增加主线信息量。

## 进入模型实验的顺序

1. 先用 ValidMem 全量建立普通“全部注入”与 lifecycle-aware 两臂；按 A/B/C 分报 accuracy，A 报 CRR、B 报 EAR，69个空证据例不删除。记录 L0 注入 token、选择时延 p50/p95；若有 L1 状态写入/更新，另表成本。
2. 再把 Trigger Bench 接到一次一store的 host runner：报告 trigger recall、false-trigger rate、wrong-op/wrong-report、trap safety 和实际 store readback。开关关闭时回普通 Codex 路径；读写异常必须回退且不污染下一例。
3. 只有前两步的 labels/trace/回退合同稳定后，再接 ISETrace，作为 exact-span 证据抽取表，不与编码任务通过率或生命周期准确率求平均。

这套顺序能区分三类失败：记忆内容不对、记忆已经失效、以及根本不该触发。若仍无净收益，可以给出可定位的负结果；继续堆相似QA数据只会扩大样本数，不会增强B的因果解释。
