# AMB 实际失败回执重放：去掉 oracle 选源

## 结果

上一轮四臂只能证明 oracle 选中的相关反馈有信息价值。本轮直接取任务可见target/scope、其中 `clean` 臂的真实 agent artifact 和隐藏 checker 失败回执，形成 `observed_failure_candidate_not_durable`，不读取 AMB 历史 session、fact terms、reference 或正确实现。

| 臂 | B 输入 | checker | 输入 / 输出 token | agent 耗时 |
|---|---|---|---:|---:|
| `e_only_replay` | 不向 agent 暴露已有 E 回执 | 失败：仍按 `order_id` 单键丢 2 单 | 107,973 / 1,345 | 42.45 s |
| `observed_failure_replay` | 1,659 字符的失败 artifact + SHA + checker verdict + unresolved | 通过：7/7、无重复、顺序正确 | 115,857 / 2,651 | 75.02 s |

配对方向是 `1 win / 0 loss / 0 tie`。连同上一轮已评分 clean，本题两次独立无记忆调用均重复同类失败；相关回执重放通过。agent 的命令只读取和修改隔离工作区，没有搜索父目录或 benchmark/oracle/reference。

这是比上一轮更接近 B 的闭环：

```text
真实 agent 动作 → E checker failure
                 ↓
     B 候选（artifact + target/scope + outcome，未决 replacement）
                 ↓
       新隔离重放 → E checker pass
```

## 改进与剩余边界

已经去掉：公开历史中的 oracle source selection、人工选择 relevant session、人工编写 replacement key。候选由 runner 确定性封装任务可见target/scope、实际失败产物和实际 E verdict；agent 仍需从当前文件推导替代实现。

尚未去掉：evaluator 仍显式指定前一轮 run 目录；只有一个同任务重放，没有候选池检索、未见任务迁移或持久 MemoryCore write path。每臂一次且 Codex 不暴露 seed，所以不能称稳定收益。B+E 比 E-only 多 7.30% 输入、97.10% 输出和76.74% agent 时间，说明本次成功有明显推理代价，不能只报通过率。

本轮两次调用合计223,830输入、3,996输出、1,479 reasoning token。连同前一四臂及一次已披露的废弃调用，AMB方法验证累计实际7次、833,656输入、13,826输出、4,819 reasoning token。

结构化结果见 [`results/amb-fa-observed-loop.json`](results/amb-fa-observed-loop.json)。下一步不应继续在这一个任务上追加重复；应把同一“实际失败 artifact + E receipt”候选合同迁到 H6 pilot，先解决自由编辑 action 与其受控 strategy fingerprint 的对齐，再在 main split 上测未见 variant、false trigger 和配对区间。
