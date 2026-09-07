# LongMemEval B+E 实验结果（`be-lifecycle-v1.0`）

> 归属说明：MemoryCore SQLite FTS、L1 存储与 `executeMemorySearch` 是腾讯 `v2.0.0-beta.1` 原有能力；本期新增的是数据/provider 接入、反馈判定、阈值选择、软失效、指标与回退评测。以下“FTS 集成跑通”不表示我们实现了 FTS。

## 1. 实验设置

- 运行日期：2026-08-21；
- 数据集：cleaned LongMemEval Oracle 文件的全部 500 个实例；
- SHA-256：`821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c`；
- 随机种子：`20260821`；
- calibration/evaluation：140/360；
- Oracle candidate pool 选定阈值：`0.75`；
- 最低 calibration precision：`0.8`；
- 生命周期动作：per-query soft invalidation，不删除基座记录。

本轮包含两条实验路径：

1. Oracle candidate pool：隔离检索误差，直接验证 B+E 判定；
2. MemoryCore SQLite FTS：验证真实 MemoryCore 写入、检索和生命周期集成路径。

## 2. Oracle candidate pool 结果

| 指标 | Base | Adaptive |
|---|---:|---:|
| Feedback precision | — | 0.4333 |
| Feedback recall | — | 0.2549 |
| Stale exposure | 1.0000 | 0.7451 |
| Stale suppression | 0.0000 | 0.2549 |
| False invalidations | 0 | 34 |
| Active candidate misses | 0 | 34 |
| Mean injected token proxy | 249.59 | 227.49 |

forced-failure 模式在全部 360 个评估实例上，都返回了与 base 完全相同且顺序一致的候选。

### 2.1 反馈判定

Adaptive 在 held-out evaluation split 上产生 30 次正例预测：

- true positives：13；
- false positives：17；
- precision：`13 / 30 = 0.4333`；
- Wilson 95% 置信区间约为 `[0.274, 0.608]`。

这意味着当前结果不能支持“高置信反馈”主张。尽管 calibration split 的点 precision 达到 0.818，但 calibration 中只产生了 11 次正例预测，其中 9 TP、2 FP；其 Wilson 95% 下界只有约 0.523。该置信度分数没有稳定地泛化到 held-out 数据。

### 2.2 生命周期效果

策略将 stale exposure 从 1.0000 降低到 0.7451，即抑制约 25.49% 的 stale candidates；mean injected token proxy 从 249.59 降低到 227.49，约下降 8.9%。

但是，该变化同时造成：

- 34 次 false invalidation；
- 34 次 active candidate miss。

因此，注入量下降不能被解释为优化成功。对于错误失效代价较高的长程编程记忆，当前 precision 明显不足以支持默认启用。

## 3. MemoryCore SQLite FTS 集成结果

所有 canonical sessions 都作为 L1 episodic records 写入数据库，并按照 `taskId` 做作用域隔离。检索通过 MemoryCore 的 `executeMemorySearch` 执行，使用真实 SQLite FTS 路径。

没有任何候选阈值满足 0.8 calibration precision 安全边界；最佳候选 calibration precision 只有 0.4。因此 optimizer 选择弃权阈值 `1.0`。

| 指标 | Base | Adaptive |
|---|---:|---:|
| Feedback predictions | — | 0（完全弃权） |
| Stale exposure | 1.0000 | 1.0000 |
| Stale suppression | 0.0000 | 0.0000 |
| False invalidations | 0 | 0 |
| Active candidate misses | 0 | 0 |
| Mean injected token proxy | 673.28 | 673.28 |

forced-failure 同样在 360/360 个评估实例上与 base 完全一致。

### 3.1 这项结果意味着什么

完全弃权说明安全边界正确阻止了不可靠策略对真实候选执行失效动作。它证明了安全门和 fallback 设计有效，但不表示 Adaptive 能力本身有效。

真实 FTS 检索会返回更多“与查询相关但可能同时有效”的候选。当前词法 detector 无法可靠区分：

- 文本相关；
- 时间上发生变化；
- 同一 entity/property/scope 下真正互斥。

因此，真实检索路径进一步暴露了 v1 方法的概念性缺陷。

## 4. 总体解释

这是 v1 词法高置信检测器的**负结果**。

它可以降低部分 stale exposure 和注入大小，但 false invalidation 成本过高，不应默认启用。calibration precision 0.818 在 held-out Oracle 数据上下降到 0.433，说明当前 confidence score 没有得到可靠校准。

主要错误来源不是单纯的阈值问题：

- temporal-reasoning 和 multi-session evidence 中可能存在真实状态变化；
- 状态发生变化不意味着所有较旧候选都应该被抑制；
- 较旧事实可能仍在不同 branch、environment 或 task scope 下有效；
- 时间最新不能替代 entity/property/scope 对齐；
- FTS 会召回更多相关但同时有效的候选，使错误抑制风险进一步放大。

硬 precision boundary 在真实 FTS 路径中选择 abstention，避免了这些错误继续扩散。因此，本次负结果同时说明了两件事：

1. 当前更新检测方法还不够安全；
2. 开关、弃权和 fallback 骨架按照预期工作。

## 5. 发布建议

当前版本的安全发布建议如下：

1. 功能继续保持默认关闭；
2. 保留 query-level soft invalidation，不允许自动永久删除；
3. 保留 ordered base candidate fallback；
4. 下一版加入 entity/property/scope 对齐；
5. 编程场景加入 branch、environment、file、API version 等作用域；
6. 引入按 signal type 分桶的校准和置信区间门槛；
7. 在内部编程会话标签上校准后，才能考虑启用持久生命周期效果；
8. 永远不能把注入量下降单独解释为优化成功。

## 6. 下一步实验

建议下一版 `be-lifecycle-v2.0` 完成以下实验：

- 使用 LongMemEval-S 全历史，而不只使用 Oracle evidence pool；
- 按共享 conversation/history 分组切分 calibration/test；
- 增加 entity/property/value/scope/version 标签；
- 增加 `adaptive-shadow` 模式，在不改变注入的情况下收集决策；
- deployment gate 改用 precision Wilson CI 下界，并同时设置 coverage 下限；
- 分别报告 explicit correction、tool-grounded feedback、restatement 和 task failure；
- 增加 branch/environment/undo 的可复现 smoke 用例；
- 通过 Mem2ActBench 或内部成对 replay 验证 lifecycle 决策是否改善实际动作。

## 7. 原始结构化结果

- [`results/longmemeval-oracle-v1.json`](./results/longmemeval-oracle-v1.json)：Oracle candidate pool；
- [`results/longmemeval-oracle-memorycore-fts-v1.json`](./results/longmemeval-oracle-memorycore-fts-v1.json)：MemoryCore SQLite FTS 集成路径。

运行方法、字段和指标定义参见[《B+E Benchmark：高置信反馈与记忆生命周期》](./README.md)。完整方法调研参见[《多轮长编程任务中的高置信反馈与记忆生命周期（B + E）》](../../deliverables/01-research-and-design/research-b-e.md)。
