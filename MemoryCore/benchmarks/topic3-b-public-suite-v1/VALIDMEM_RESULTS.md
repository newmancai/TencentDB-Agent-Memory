# ValidMem Codex 生命周期评测结果

结论：固定开发后，`type_aware_policy` 在406个一次性留出case上把答案正确率从374/406（92.12%）提高到387/406（95.32%），配对15胜2负389平，提升3.20个百分点。case级McNemar双侧精确`p=0.00235`；按26个batch聚类的10,000次bootstrap区间为`[+0.25,+7.39]`个百分点，但batch符号检验仅`p=0.125`。因此本结果通过公开集上的生命周期方法验证，尚不足以宣称高置信产品收益。

结构化结果见 [`results/validmem-codex-holdout.json`](results/validmem-codex-holdout.json)，完整calls/cases/prompt/events留在本地`.local-evidence/topic3-b-public-suite-v1/validmem-codex-*`，其SHA写入结果JSON。

## 固定协议

- 数据：[ValidMem v1.1](https://huggingface.co/datasets/Zhou11Alex/ValidMem) revision `786d5cd9...`，466例；tasks/gold哈希固定，模型不见生命周期标签。
- 相关实现：[MemFSM](https://github.com/zhoushuo119-creator/MemFSM) revision `4bf195721890f1a3d4e31a5631838963586cdb08`。type-aware臂只采用其公开、可由输入字段执行的规则：无显式到期日的`project-status`年龄超过14天后视为过期；不复制上游逐例结果或gold。
- 模型：`gpt-5.6-sol`、reasoning medium、Codex CLI 0.153.4。开发集按固定hash在A/B/C各20例，留出为其余406例；两者零交集并合计466。
- 两臂看见完全相同的1,193条记忆记录、问题和选项；基座自行理解时间，启用臂增加冻结的生命周期规则。每例输出choice和实际选择的memory ID，随后才由隔离gold评分。

## 开发与留出

第一次开发运行中普通54/60，显式日期策略55/60，但仅1胜且CRR/EAR不变。重复开发运行中普通54/60、显式策略54/60；新增type-aware策略57/60，相对普通3胜0负，EAR从15/20升到18/20。只有type-aware进入留出，显式策略停止。

| 留出指标 | 普通基线 | type-aware | 差异 |
|---|---:|---:|---:|
| Overall accuracy | 374/406（92.12%） | 387/406（95.32%） | +13题，+3.20pp |
| Part A | 150/150 | 150/150 | 0 |
| Part B | 147/176（83.52%） | 159/176（90.34%） | +12净题，+6.82pp |
| Part C | 77/80（96.25%） | 78/80（97.50%） | +1净题，+1.25pp |
| CRR（A：正确且不选superseded） | 150/150 | 150/150 | 已达天花板 |
| EAR（B：正确且不选expired） | 147/176 | 159/176 | +12 |
| 非法memory选择 | 0 | 0 | 0 |

15个改善中13个是`implicit_temporal`、1个`boundary_cases`、1个混合`superseded_but_new_expired`；2个回归也都是`implicit_temporal`，原样保留。它说明固定TTL提供了有效但不完美的归纳偏置，不说明规则已普遍正确。

源数据唯一无干扰选项的`TC-B-0185`在留出中，两臂都正确。排除它后，普通373/405、启用386/405，仍为15胜2负，结论不变；主结果仍保留全量case，没有换子集。

## 代价与置信度

| 留出成本 | 普通基线 | type-aware | 相对变化 |
|---|---:|---:|---:|
| input tokens | 428,557 | 431,079 | +0.59% |
| output tokens | 15,940 | 17,779 | +11.54% |
| reasoning tokens | 5,402 | 7,327 | +35.63% |
| 总生成时延 | 513.98s | 585.98s | +14.01% |
| 批次时延p50 / p95 | 18.64s / 30.50s | 21.21s / 34.72s | 约+13.8% |

52次批调用全部return code 0、解析错误0，事件中只有52个最终agent message、command execution为0。batch=16降低了Codex固定上下文成本，但同一batch的case不完全独立：case级检验显著，batch级只有4个净正batch、0负、22平，符号检验不显著。聚类bootstrap方向为正，不等于多个模型或多个独立重复均已验证。若要主张高置信反馈，仍需至少做独立运行/不同batch排列以及Trigger/编码任务外部验证，不能用本次一次留出替代。

L0两臂各注入1,193条预建公开记忆；本实验没有L1抽取、写入或更新，所以L1明确记为未测。type-aware当前是prompt级方法臂，不是MemoryCore原生生命周期状态机，也没有建议升production默认。

## 决策

本配置不再在ValidMem留出上调参。它可以作为下一阶段旁路候选：在MemoryCore host中把type/created/expires元数据转换为可关闭的选择决策，再用Trigger Bench检查错误读写和过度触发，并回到AMB/H6的客观E回执验证是否减少编码任务重复失败。若原生化后无法保留收益或误触发上升，应回退并报告负结果。
