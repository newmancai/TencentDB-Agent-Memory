# B Oracle Attribution Intervention v1

## 问题

在反馈对象、作用范围和权威都由 harness 正确提供时，一条已验证、当前适用的记忆
assertion 是否能改善下一项匹配任务？这是 B 路线的第一项判伪实验，只测 memory
action 的使用价值，不测自动 target/scope 识别、状态学习或生产接入。

## 固定设计

- 8个全新合成开发项目，每项包含一条明确用户纠正和一个后续匹配请求；不使用旧
  CUPID题目、最终验证集或reference答案。
- 每个项目建立两个隔离执行槽，按固定散列随机分配 `include/omit`，因此同一项目
  两臂各出现一次、执行顺序随机；记录完整动作的 propensity `0.5`。
- 两臂候选集合完全相同。`include`只注入该项目的oracle assertion；`omit`不注入，
  其他提示、模型、reasoning、输出schema和checker完全相同。
- 固定 `gpt-5.6-sol`、reasoning `medium`、Codex CLI `--ephemeral --ignore-user-config
  --ignore-rules`、只读空目录。每次调用为新会话，禁止工具、浏览和文件访问。
- 输出固定为 `{project, setting, value}` JSON；若可见证据没有 established value，
  必须输出 `unknown`，不允许猜测。deterministic checker只比较三个字段，不使用LLM judge。
- 每次调用失败或超时保留，不重试。保存prompt、Codex JSONL事件、最后消息、stderr、
  usage、墙钟时间、decision/outcome trace和checker结果。

## 解释边界与退出条件

该实验故意让 target/scope/authority 成为oracle，回答的是“正确记忆进入prompt是否有
任务价值”。`include`胜出不等于系统已经学会发现或绑定反馈，也不代表自然分布收益；
`omit`看到的信息更少，不能把结果包装成同信息表示学习。

开发判定预先固定：

- `include`没有明显优于`omit`：停止该任务域，不训练binder或gate；
- `include`在至少7/8项成功，且配对净胜至少6项：允许进入下一阶段scope替换；
- 介于两者之间：只检查明确的执行/解析故障，不改任务、值、prompt或模型追分；若无
  执行故障则视为证据不足并停止。

所有记录先通过 Phase 0 replay；缺candidate/action/propensity或因果链接时，本实验无效。
