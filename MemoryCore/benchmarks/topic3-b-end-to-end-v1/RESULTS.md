# B End-to-End Synthetic Holdout v1 结果

固定前序target prompt、值编译规则和精确scope gate，在4个未用于组件开发的合成项目完成
20次独立Codex调用，0失败、0重试：

| 阶段 | 结果 |
|---|---:|
| target binding | 4/4 |
| assertion value update | 4/4 |
| 匹配任务adaptive | 4/4 |
| 匹配任务frozen | 0/4 |
| 冲突项目adaptive安全检查 | 4/4 |

匹配任务adaptive相对frozen为4胜0负0平。冲突项目由结构化scope gate在调用前omit，
四项均输出`unknown`，没有跨项目注入。整份trace replay通过：24 decision、4 feedback、
16 assertion、24 outcome，24条learner-ready、0 pending。

成本为284883 input、77696 cached input、521 output token，墙钟149.575秒。所有评分是
目标集合或JSON字段精确比较，无LLM judge；原始prompt、事件、输出、stderr、usage和trace
保存在`.local-evidence/topic3-b-end-to-end-v1/run-v1/`。

这首次给出当前新架构的正向合成开发证据：在oracle候选构造、明确纠正、结构化scope与
强Codex组件下，反馈能形成更新assertion，并改善新的匹配任务而不泄漏到明确冲突项目。
它仍不是自然反馈学习：候选集合是oracle构造，任务是高可判定配置查询，scope字段已结构化，
样本仅4个holdout。不能用4比0替代真实业务、自然语言候选生成或production验收。

精确scope规则已满分，当前不训练bandit与它争同一批合成题。下一有效问题是自然反馈下
能否生成完整候选集合并保持unknown，而不是继续扩充相似合成配置案例。
