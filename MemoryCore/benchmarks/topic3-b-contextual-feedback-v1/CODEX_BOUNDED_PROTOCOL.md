# Codex 有界反馈规则诊断 v1

本协议来自用户在最终交接后的一次明确恢复授权，但不恢复长期任务。运行边界固定为一个此前未使用的 CUPID 开发 persona、其三个任务、四个推断臂，共十二次独立 Codex 调用。完成、失败或达到调用边界后即停止；不下载模型、不运行本地模型、不扩展到第二个 persona，也不触碰最终验证 split、MemoryCore 运行时或 production。

排除此前准备或研究已涉及的三十个开发 persona，包括中断 rule-transfer 的四个。其余开发 persona 按 SHA256(`cupid-codex-bounded-v1:` + group) 固定选首个，保留该 persona 的全部三个任务。完整 user-only 历史和当前请求在四臂间相同；reference、factor、type、group 和其他变体不进入推断。

四臂沿用冻结状态：

- `frozen`：没有旧开发经验。
- `rules_unlabelled`：读取由旧观察和草稿编译的三条规则。
- `rules_feedback`：读取由相同旧观察、草稿及受控纠正编译的三条规则。
- `feedback`：直接读取相同的两条旧观察、草稿及受控纠正。

已有规则不重编译、不改写、不按新题筛选。四臂使用明确固定的 `gpt-5.6-sol`、`high` reasoning、Codex CLI 0.153.4、只读空目录、忽略用户配置和项目规则、`--ephemeral --json`。每题每臂是新会话；提示要求不调用工具，只输出至多100词的偏好推断。Codex agent 自带系统行为无法与普通文本模型完全等同，报告中保留此限制。

运行保存逐题提示、JSONL事件、最后消息、返回码、墙钟时间和事件中可得 usage。单次调用失败也不重试。规则编译的既有4B成本12100输入/238输出token、8.755秒单列，不伪装为Codex推断成本，也不把隐藏计算或账号计费推断为已知。

生成后以固定散列把四臂匿名为A/B/C/D。审查先依据可见用户原话判断要求、对象、范围、引用和偏好排序，再单列reference覆盖；映射在审查完成前不使用。语义判断仍是助手意见，不是官方grader或人类gold。核心比较为`rules_feedback`分别对`frozen`、`rules_unlabelled`和`feedback`的胜/负/平/未决，并逐题保留理由。

该单元只回答“冻结的两例受控纠正规则，在同一Codex推断配置、一个新persona上是否显示增量迹象”。无论结果正负，不继续加样本、调规则、换模型或改prompt；一个persona不能证明稳定收益或商业可用。
