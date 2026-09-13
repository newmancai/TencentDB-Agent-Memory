# AMB `fa-dedup-key`：B 信息干预 + E 执行闭环烟测

## 结论

固定同一公开任务树、Codex 模型与隐藏属性 checker 后，四臂得到：

| 臂 | 模式 | 注入字符 | checker | 输入 / 输出 token | agent 耗时 |
|---|---|---:|---|---:|---:|
| `clean` | 基座 | 0 | 失败：`order_id` 单键丢 2 单 | 91,692 / 1,202 | 38.34 s |
| `irrelevant_control` | 启用无关记忆 | 680 | 同样失败 | 76,047 / 1,139 | 44.18 s |
| `raw_feedback` | 启用原始失败反馈 | 579 | 通过：7/7、无重复、顺序正确 | 168,477 / 3,645 | 89.26 s |
| `compiled_failure` | 启用结构化失败记忆 | 476 | 通过：7/7、无重复、顺序正确 | 113,419 / 1,730 | 50.33 s |

这证明了一个很窄但关键的点：本题并非基座自然会做，也不是“随便塞一段记忆”就能过；与当前动作 target/scope 对齐的失败证据可以阻止同类错误。它是 B 的信息干预方法验证，E 只负责用执行结果闭环判定。

不能据此主张稳定收益。固定快照中只有一个 failed-approach 任务，每臂只有一次、Codex 不暴露 seed；相关 source 的选择和结构化编译都由 evaluator 确定，并非 MemoryCore 已自主完成写入、选择与演化。`compiled_failure` 相对 `raw_feedback` 少 17.79% 注入字符、32.68% 输入 token、43.61% agent 时间，只是 n=1 描述量，不作因果成本结论。

## 协议

- 数据：`GiulioDER/agent-memory-bench@e0859d1ca757f65747b4d32e21f158d55c595879`，快照中唯一的 `fa-dedup-key`。
- 粒度：每臂一个全新临时 Git 工作区；任务输入树 SHA-256 均为 `4af8318086d85df7824c248f92d719ee3c6ed8c747bd300de2e449c8bce56297`。
- Agent：`codex-cli 0.153.4`、`gpt-5.6-sol`、`medium`；相同任务提示与沙箱，只有记忆段不同。
- 对齐：`raw_feedback` 取该任务唯一相关 session 的最后一条用户失败观察；`compiled_failure` 只把同一观察编译为 target、scope、prohibited action、outcome 和 unresolved，不给 replacement key；无关对照由固定 hash 从 distractor 中选择。
- E：模型退出后才加载上游 checker；checker 按性质判定丢单、重复、伪造与顺序，且上游合同已证明至少两种不同正确实现可通过。
- 结构化逐臂结果见 [`results/amb-fa-codex.json`](results/amb-fa-codex.json)；原始 prompt、事件、artifact 与回执保存在 `.local-evidence/topic3-b-public-suite-v1/amb-fa-codex-v2/`，不进 Git。

## 失败与实际总成本

第一次 v1 的 clean 调用在 agent 完成后，因本地 runner 未把上游仓库加入 checker 的 import path 而无法评分。该结果没有进入四臂比较，也没有伪装成任务失败；修复 import 后用全新 v2 目录重跑全部四臂。废弃调用仍计 160,191 输入、2,114 输出、505 reasoning token。含废弃调用，本次实际共 5 次：609,826 输入（其中 563,584 cached）、9,830 输出、3,340 reasoning token。

## 相对端到端实验的置信口径

当前 checker 对“这个 artifact 是否满足这个固定任务合同”置信较高，因为结果可确定重放且不依赖单一参考答案。它不能直接回答“是哪条记忆导致成功”或“策略平均收益多大”：后两项仍需多个任务、不可见 variant、重复调用和配对置信区间。下一轮应在 H6 main split 上先跑 `observed_loop`：episode 1 真实失败及 action fingerprint 产生候选，episode 2 在未见 variant 上比较 E-only 与 B+E，并把 eligible 分母、no-trap 误触发及 L1/L0 成本全部原样报告。
