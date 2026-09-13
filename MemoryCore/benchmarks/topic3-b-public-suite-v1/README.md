# B 主线公开集组合协议（E 只负责闭环）

本目录把近期公开资源按能力缺口组合使用，不把不同分母合成一个总分。主问题始终是：**一次反馈或任务结果，何时应形成什么记忆、绑定到哪个动作和范围、在后续哪一个决策点使用，才能减少重复失败而不过度干预？** E 只提供可追溯的 checker / verifier 回执，不替代 B，也不因任务通过就反推某条记忆必然正确。

当前完成第 0 轮数据固定和两级 AMB 单题方法烟测。H6 对六类 trap 各抽一个 variant，验证 baseline / bad 均失败、good / no-trap 均通过；AMB 完成34任务、196正式语料 session、58个 harm condition 的结构审计，并单独验证 failure-attribution 多解合同。第一层四臂中 clean / 无关记忆失败，oracle 选中的原始/结构化反馈通过。第二层去掉公开历史选源，只用任务可见target/scope、第一层 clean 的真实 artifact 与 E checker failure 自动形成候选：E-only 重放失败，B+E 重放通过。详见 [`AMB_FA_RESULTS.md`](AMB_FA_RESULTS.md)、[`AMB_OBSERVED_LOOP_RESULTS.md`](AMB_OBSERVED_LOOP_RESULTS.md) 与 [`results/amb-fa-observed-loop.json`](results/amb-fa-observed-loop.json)。后者闭合了实际 E→B→E，但仍是同任务 n=1，不是自主检索或稳定净收益。

## 统一闭环

```text
决策前 B：候选记忆 → target/scope/validity → omit/include/verify/ask → delivery site
       ↓（记录实际暴露、动作和 propensity；此时不知道结果）
编码动作 / 工具调用
       ↓
结果 E：本地 checker / tool readback → success/failure/unknown 回执
       ↓（绑定 decisionId、checker hash、时间、成本）
B 更新：candidate → verified/disputed/superseded；unknown 不自动晋升
```

现有 `benchmarks/support/memory-feedback` 已具备 decision、claim、assertion、outcome 和 replay 合同；本目录只负责公开集适配，不另造第二套运行时。近期 MemGuard 的“将 verifier 信号作为持久生命周期元数据，而非一次性过滤器”与这条路线一致，但其论文结果只算相关工作，不能当作本项目复现结果。[论文](https://arxiv.org/abs/2608.21867) / [代码](https://github.com/whyyyyy123/MemGuard)

## 数据集分工

精确 revision 和启用状态在 [`suite.json`](suite.json)。

| 数据 | 在本项目中的角色 | 能回答 | 不能回答 |
|---|---|---|---|
| [H6 Failure Gate](https://huggingface.co/datasets/joshuaswarren/h6-failure-gate-tasks) | 第一主集，B timing + E checker | 已知失败记忆在 turn-start 与 pre-action 的因果差异、重复失败、no-trap 误触发 | 自然多轮学习、跨项目泛化、最终完成率必然提升 |
| [Agent Memory Bench](https://github.com/GiulioDER/agent-memory-bench) | 第二主集，执行式 read/lifecycle 路径 | present / absent / superseded / contradictory / adjacent 条件下的任务结果 | 当前版本尚不能单独证明从 agent 自身反馈学习 |
| [ValidMem](https://huggingface.co/datasets/Zhou11Alex/ValidMem) | B 生命周期诊断 | current/history、supersession、expiry | 编码任务完成与真实反馈闭环 |
| [AutoMemoryBench](https://huggingface.co/datasets/Multilingual-Multimodal-NLP/AutoMemoryBench) | 大规模状态合同审计 | required / admissible / prohibited 的容量与边界压力 | 真实代码执行；许可元数据未明确前不进入主结论 |
| [ISETrace Memory Queries](https://huggingface.co/datasets/HazeLocus/ISETrace-Memory-Queries) | L1 抽取与证据对齐 | 完成轨迹上的 exact-span 检索、跨项目表述泛化 | 在线决策因果；轨迹已完成且全量并非人工复标 |
| [Trigger Bench](https://huggingface.co/datasets/wallfacers/agent-memory-trigger-bench) | B 触发安全烟测 | 何时不应写、不应更新、不应触发 | 端到端质量主结论 |
| [AgentArtifactCorpus](https://huggingface.co/datasets/searchsim/AgentArtifactCorpus) | 训练/分析语料候选 | 真实 AGENTS / CLAUDE / rules 形态 | 不能作带结果标签的主评测集 |

## H6 证据口径

公开数据固定为 `joshuaswarren/h6-failure-gate-tasks@20017969711c7c72c649d9e4d70a8df730ec6176`：30 个 TypeScript 任务、六类 trap 各 5 个、12 pilot / 18 main、每任务 3 个 variant。数据集声明的 inventory hash 为 `687615b5f7ff46977d268a03e30018070f7d0bec9d01e04da2d0c723e59a5b27`。

上游证据必须分三层读：第一次注册的 timing 因一项不可分类结果为 `NOT_ESTIMABLE`；固定新种子的第二次注册报告 pre-action 相对 turn-start 的重复失败绝对下降 35.56 个百分点，`p=0.0019`，因此 timing `SUPPORTED`；但 turn-start failure 对 success memory 的 content 假设被拒绝，任务通过率增量也未成立。参见固定 tag [`h6-study-2026-08`](https://github.com/joshuaswarren/remnic/tree/h6-study-2026-08/docs/research/failure-gate) 和[数据卡](https://huggingface.co/datasets/joshuaswarren/h6-failure-gate-tasks)。这些是上游结果，不是我们的独立复跑；公开后的模型还存在污染风险。

H6 的 episode-1 history 是用已知 bad/good strategy 构造并冻结的控制历史，所以它首先检验**同一记忆内容的投放时机**，不是自然的“模型失败后自主学会”。本项目后续会把两种协议分开：

1. `controlled_replay`：复现同内容、不同 delivery site 的 timing 因果；
2. `observed_loop`：episode 1 必须来自 agent 的实际动作和 checker 失败，只有 action fingerprint 与失败回执同时匹配才产生候选记忆，再在未使用的 variant 上评分。

第二种更接近 B 主线，但样本会因 episode 1 未落入 trap 而减少，必须原样报告 eligible 分母，不能补造失败历史。

## AMB 审计结论

固定 `GiulioDER/agent-memory-bench@e0859d1ca757f65747b4d32e21f158d55c595879` 当前含34个可执行任务和196个正式 corpus session；另外的 plant / oracle-memory JSONL 是条件构造或诊断材料，不混入 base manifest。官方 `official-003` 是26任务、317 admitted cell、每 cell 一次 repetition 的 bulk-ingest read-path null，且其 preregistration 晚于开跑；它既没有测 write path，也不能当成本项目负结论。

最新的 `fa-dedup-key` 更适合 B：历史会话记录 `order_id` 单键去重导致丢失1,214个真实订单，并明确不替未来 agent 选择 replacement key。记忆提供的是**被结果证伪的动作约束**，不是答案；checker 同时接受两种不同正确 key，排除了“背唯一参考答案”。上游相关5项合同测试已通过。它目前仍只有1题、bare 仅3次校准，先作 failure-attribution 方法样例，不能独立支撑主结论。

本项目独立方法烟测与这一预期一致：clean 和固定无关记忆均再次选择 `order_id` 单键而失败；同源 raw feedback 与仅保留 target/scope/prohibited action/outcome/unresolved 的 compiled memory 均通过。compiled 相对 raw 的注入量与本次调用成本更低，但 n=1、无可控 seed，差值只作描述。两条 relevant 臂还是 evaluator-oracle source selection，下一步必须把“真实 E 失败回执 → B 候选形成 → 未见 variant 使用”接起来。

复盘后的 observed-loop 已完成前半段：runner 读取任务可见target/scope、已评分 clean artifact 与 checker verdict，确定性封装为临时候选，不读公开历史答案；同任务新重放由失败变通过。这个结果去掉 oracle 选源，但尚无未见 variant，也没有从多个候选中自主检索。H6 上游使用受控 `apply_strategy` 工具，在实际动作执行前按 fingerprint 发 advisory；Codex CLI 四臂是自由编辑代理，不能把两种 action space 直接混作严格复现。后续先在 pilot 明确自由编辑 diff 与固定 strategy fingerprint 的对齐规则，主集才运行，不因赶进度改坏 H6 协议。

本机用隔离 Python 3.12 重放时，corpus、plants、data-safety 三项审计均通过；另外30项 capability/lifecycle/task-scope 测试与5项 `fa-dedup-key` 合同测试通过。全任务102项 do-nothing/naive/informed replay 在进入 checker 前被宿主 Git 2.25 阻断，因为上游使用 `git init -b`；这记为环境阻断，不记任务失败，也不修改上游 harness 绕过。后续实跑应使用 Git ≥2.28 或上游声明的容器。

## 三轮推进协议

### 第 1 轮：H6 action-site gate

- 固定 agent、模型、预算、候选动作和 prompt；pilot 不用于改 prompt。
- 至少比较 `NO_MEMORY`、`TURN_START_FAILURE`、`PRE_ACTION_FAILURE`；`TURN_START_SUCCESS` 分离内容效应，`BOTH` 只作机制诊断。
- 主指标：task-level repeated-failure rate；次指标：task pass、steps、token、agent/checker latency、no-trap false-trigger。
- `controlled_replay` 与 `observed_loop` 分表，不合并；Codex/Claude 无可控随机种子时记录独立 repetition id，并明确“不可复现 seed”。

### 第 2 轮：AMB + ValidMem 生命周期

- AMB 用执行 checker 判断 E 结果，比较 clean / E-only / B+E，而不是只比较是否检索到文本。
- ValidMem 专门测 verified / superseded / expired 在 current 与 history 查询下的状态转移；69 个空 ground-truth expiry case 不过滤。
- 同时报告 L1 写入/更新与 L0 检索/注入，避免把生命周期正确误算成答案收益。

### 第 3 轮：跨项目与误触发

- ISETrace 用未见项目的 exact span 测 candidate evidence 对齐；Trigger Bench 测无反馈、弱反馈、相反范围下的保守性。
- AgentArtifactCorpus 只用于诱导有限规则候选，所有选择在开发分区完成；最终验证不把语料中的规则文字当 gold。
- 若前两轮仍无净收益，交付负结果与失败归因，不扩 E 来掩盖 B。

## 指标与置信度

- `repeated_failure_rate`：选择与已验证失败 fingerprint 相同的动作，且 checker 证明同类失败的 task-level 比例。
- `task_pass_rate`：checker return code 为 0 的比例；这是 E 结果，不等于 B 归因。
- `memory_delta`：同一 backend、同一 task/repetition 下 `B+E - E-only` 的配对差；模型之间不直接相减。
- `target_binding_precision`：被激活记忆中 target 与实际待执行动作精确对齐的比例。
- `false_trigger_rate`：no-trap 或 scope 不匹配时仍触发 gate 的比例。
- `cost`：L1 抽取/更新与 L0 检索/注入分别报告 input/output tokens、注入字符或 token、p50/p95 latency；checker 时间单列。

单次确定性 checker 对当前任务合同的通过/失败是高置信 E 回执；“失败由某条记忆导致”只有在 pre-decision trace、实际暴露 span、action fingerprint 和 checker failure class 全部对齐时才可称较高置信归因。端到端重复实验仍用于估计模型随机性与策略净收益，不能被一次 checker 取代。

## 复现第 0 轮

```bash
git clone https://huggingface.co/datasets/joshuaswarren/h6-failure-gate-tasks /tmp/h6
git -C /tmp/h6 checkout 20017969711c7c72c649d9e4d70a8df730ec6176

python3 h6_adapter.py prepare --source /tmp/h6 --output /tmp/h6-adapted
python3 -m unittest test_h6_adapter.py
python3 h6_adapter.py smoke --source /tmp/h6 --output /tmp/h6-checker-smoke.json

# 为 runner 重建一个不含评测标签的工作区；可选 --strategy 仅供 evaluator 应用动作
python3 h6_adapter.py materialize --source /tmp/h6 \
  --case-id h6-task-01-v1 --state baseline --output /tmp/h6-workspace

python3 amb_adapter.py prepare --source /tmp/agent-memory-bench --output /tmp/amb-adapted
python3 amb_adapter.py materialize --source /tmp/agent-memory-bench \
  --task-id fa-dedup-key --output /tmp/amb-workspace

# 不加 --execute 时只验证并物化四臂协议；实际调用需本机已配置 codex CLI
python3 amb_failed_approach_runner.py --source /tmp/agent-memory-bench \
  --output /tmp/amb-fa-dry-run
python3 amb_failed_approach_runner.py --source /tmp/agent-memory-bench \
  --output /tmp/amb-fa-run --execute

# 从上一次已评分 clean failure 形成 observed candidate；不读公开历史/gold
python3 amb_failed_approach_runner.py --source /tmp/agent-memory-bench \
  --observed-from /tmp/amb-fa-run --output /tmp/amb-fa-observed --execute
```

两套 `tasks.json` 只含 agent 可见任务、工作区/语料合同和 checker 接口；`gold.json` 才含 bad/good、trap、fact terms、相关 source 和 reference。适配层不绑定 MemoryCore 存储实现，后续内部数据只需提供同等的 workspace、pre-decision trace、E receipt 和 evaluator-only labels。
