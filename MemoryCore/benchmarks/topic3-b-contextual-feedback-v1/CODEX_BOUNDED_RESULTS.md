# Codex 有界反馈规则诊断结果

用户在最终停止交接后明确恢复一次非长期任务。本单元已按 [固定协议](CODEX_BOUNDED_PROTOCOL.md) 完成并停止：一个此前未使用的开发 persona `234+real_estate_agent`、三个任务、四臂十二次独立 Codex 调用；没有继续30B下载、本地模型、第二个persona、最终验证集、MemoryCore运行时或production操作。

## 执行与隔离

明确固定`gpt-5.6-sol`、reasoning `high`、codex-cli0.153.4。每次调用使用新的ephemeral会话、忽略用户配置和项目规则、只读空工作目录。12/12均返回成功，0重试、0超时；事件各只含一个`agent_message`，没有命令或工具调用。全部输出76–93词，0项超过100词。

Codex事件usage合计326531输入、123904缓存输入、2689输出，其中894 reasoning输出；十二次调用墙钟合计166.931秒。按臂如下。输入口径包含Codex agent自身上下文，不能当成仅有数据prompt的token数，也不据此推断账号账单。

| 臂 | 3次输入 | 缓存输入 | 输出 | reasoning输出 | 墙钟秒 | 最终词数 |
|---|---:|---:|---:|---:|---:|---|
| frozen | 76952 | 28288 | 610 | 144 | 36.433 | 81/86/89 |
| rules_unlabelled | 77408 | 31872 | 668 | 219 | 45.857 | 88/83/90 |
| rules_feedback | 77354 | 31872 | 661 | 226 | 43.651 | 76/81/93 |
| feedback | 94817 | 31872 | 750 | 305 | 40.990 | 88/84/87 |

直接反馈臂比frozen多17865输入token（23.22%）；纠正规则臂只多402（0.52%）。但规则编译还必须单列既有4B成本12100输入/238输出、8.755秒，且没有跨更多调用摊销的实证。

## 匿名源文审查

Root先只读A/B/C/D匿名包并写入审查，再打开私有映射。审查关注用户原话中的对象、当前用途、时间变化、引用和不确定性；reference只单列覆盖。它是助手语义意见，不是官方grader或人类gold。

| 任务 | 匿名排序层级 | 解封后的臂排序 | reference覆盖 |
|---|---|---|---|
| 470ba153612736a1344d56b7 | C=D > A > B | rules_feedback=frozen > feedback > rules_unlabelled | 四臂full |
| b130d9da2a80709fbe7e1b0c | B > A > D > C | rules_unlabelled > feedback > frozen > rules_feedback | rules_unlabelled full；其余partial |
| dd84c2805da4b11ef6268b3a | D > C > B > A | feedback > rules_feedback > frozen > rules_unlabelled | 四臂full |

`rules_feedback`对`frozen`为1胜1负1平，对`rules_unlabelled`为2胜1负，对直接`feedback`为1胜2负。第二题的同一用途历史出现了从“专业、功能和市场信息”到“家庭情感、生活方式和社区”的变化；无纠正规则臂在该题最好，而纠正规则臂最差，说明当前两例规则并未稳定改善范围/变化处理。第三题直接反馈最好，第一题纠正规则与无需旧经验的强基线并列。

## 结论与停止状态

本次首次实跑证明Codex对照链路可执行、可保存事件与usage，并显示压缩规则能显著降低相对直接反馈的推断输入量。质量上没有稳定净收益：纠正规则未胜过frozen，也未胜过直接反馈；对无纠正规则的2胜1负只是一个persona三题的局部迹象，不能支持B收益或商用启用。

该有界单元到此停止，不因负结果追加persona、调规则、换模型或改prompt。完整任务、提示、事件、回执、匿名包、盲审和私有映射保留在`.local-evidence/topic3-b-cupid-v1/codex-bounded-v1/`。Git只保存协议、runner和结构化汇总。长期任务没有恢复；如需新实验，必须作为另一个明确、有限的新任务单独授权。
