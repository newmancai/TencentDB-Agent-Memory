# 零显式反馈信号优化：依据、实现与下一步量化

更新：2026-09-07。

## 结论

反馈信号不再由“模型是否说成功”或“某个工具调用返回成功”直接生成，而采用四段式证据链：

`当前任务身份 → Memory 检索/暴露/使用 → 工具或环境局部结果 → 独立任务终态`

本轮完成第一段到第三段的最小确定性投影：工具观察可绑定 `taskRunId`，旧任务及未绑定回执
不会参与当前任务判断；局部字段回读与整项任务 outcome 分开；只有带客观 validator 的任务
终态才进入后续 Memory 归因研究。投影只给出最早的证据断点，不直接判定 Memory 内容有错，
也不直接生成 helpful/harmful credit。代码路径默认仍是 shadow-only，不执行 production Memory
写回、删除、降权或重排。

## 商业实践背书

- Anthropic 将完整 transcript/trace 与最终 environment outcome 明确区分：Agent 自称完成不等于
  环境中真实完成；建议组合终态检查、工具调用验证和其他 grader。代码式 grader 的优点是快、
  便宜、客观、可复现；模型 grader 用于开放语义，但更贵且需要人工校准。
  见 [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)。
- Anthropic 的 Agent 工程经验把工具/环境返回视为循环中的 ground truth，并强调只在结果可测地
  改善时增加复杂性。见 [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)。
- OpenAI 的生产模型指南要求先定义 outcome、成功条件、允许副作用、证据规则和输出形状，使用
  结构化输出校验，并以准确率、tokens 和端到端延迟共同 benchmark；复杂编排或更高 reasoning
  effort 只在 eval 显示增益时采用。见 [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)。

这些资料支持“真实终态、完整轨迹、结构化证据、分层 grader 和成本评价”这一方向；它们没有
公开证明单条 Memory 的 exact causal credit。因此本项目仍需自己的 exposure/version join 和
小规模干预对照，不能把商业背书写成已解决归因。

## 理论分析

1. **事件溯源。** 原始回执保持不可变，feedback 是可重算 projection。这样修正判据时不需改写
   历史，也避免模型结论污染事实层。
2. **时序与身份约束。** `taskRunId` 相当于 happens-before 边界。上一任务成功与当前任务没有合法
   join，必须忽略；这直接针对第一期 far case 的“读到历史回执但未执行当前动作”风险。
3. **选择性预测。** 证据不足输出 `unknown`，不强迫二分类。目标是在可判定覆盖率、错误反馈率
   和成本之间取得可校准的 operating point，表面覆盖率不单独作为优化目标。
4. **因果分解。** `相关 → 检索 → 暴露 → 使用 → 执行 → 终态` 是一条有序链。先定位第一条缺证或
   反证的边，可避免把执行器、工具或环境失败错误归责给正确 Memory。
5. **归因边界。** 观察相关性只产生候选；Memory utility 仍需同基础能力的 apply/no-apply 或
   Full/Mask 小对照。一次失败不能授权永久删除，一次成功也不能证明单条 Memory 有益。

## 本轮实现

- `src/core/self-supervision/tool-execution.ts`
  - 新增 `ToolExecutionContext { sessionId, taskRunId }`；兼容旧字符串调用，但旧调用显式记为未绑定。
  - observation ID 将任务身份纳入摘要，避免同 session/同 call ID 跨任务碰撞。
- `src/core/self-supervision/execution-feedback.ts`
  - 新增 `assessTaskEvidence` 零模型投影。
  - 分离 `executionStatus` 与 `outcomeStatus`。
  - 只有非 blind-judge 的客观 validator 与 outcome 一致时，才认为任务终态有权威证据。
  - 输出 `retrieval / exposure_or_use / tool_execution / downstream_or_unknown /
    non_memory_failure / insufficient_evidence`，只表示诊断阶段，不表示 exact fault。

聚焦测试为 24/24，全 `self-supervision` 测试为 160/160，插件构建通过。0 模型调用，0
production Memory 操作。

## 下一步量化

下一切片不继续刷候选分类分，而用第一期持久 trace 加少量新隔离任务，报告：

- 当前任务绑定完整率、旧/无绑定回执拒绝率；
- objective outcome 可判定覆盖率，以及 supported/refuted/unknown 分布；
- 阶段定位与人工 trace 复核的一致率、把非 Memory 故障误归责给 Memory 的比例；
- 应用/不应用局部范围修正后的完整任务成功、严重回归；
- 每项成功的在线 p95、tokens、模型调用、GPU seconds 与后台升级率。

确定性 projection 保持在线零模型；只有 `unknown` 且业务价值足够高的样本，才考虑异步弱模型
或强模型复核。即使模型分支无增益，当前结构化信号仍提供可审计、低成本的基础能力。
