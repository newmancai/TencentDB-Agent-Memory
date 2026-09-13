# 原生长对话验证：整段矛盾分数不适合作为更新反馈

2026-09-13。本轮关闭的是“旧整段/新整段直接用通用 MNLI 矛盾概率产生更新信号”这一具体配置，不是否定 B、逐对定位或所有 NLI 方法。没有修改 E，没有在当前数据调阈值。

## 实测结果

54 个已有 LongMemEval 开发检查点，另 6 个无既定参考对单列。真实 MemoryCore L0 写入 8,747 条历史用户消息；原生 FTS top8 与相同写入池最近8条比较。两臂各432候选，参考旧消息分别触达39/54与26/54。

| 指标 | FTS | 最近8条 |
| --- | ---: | ---: |
| 固定0.7告警 | 34 | 11 |
| 其中既定参考对象告警 | 3 | 1 |
| 其他尚未标注候选告警 | 31 | 10 |
| 超长未知 | 1 | 4 |

两版既有助手银标分别认为20和17个参考对发生更新，FTS均全部触达，但0.7只触发其中2个；0.5触发4个。最近8条没有触达这些变化参考对象。因此在这个受控样本中，继续扩大候选池不能解决主要漏检。参考对象不是所有有用记忆，不能把31个其他告警直接计作误报。

为检查这些其他告警是否其实有用，对全部34个FTS告警做两份独立助手盲审，只给旧句与后续句，不给分数、参考对象身份或QA标签：

| 银标审查 | 支持更新 | 支持逻辑冲突 | 不支持 | 未决 |
| --- | ---: | ---: | ---: | ---: |
| A | 3 | 0 | 29 | 2 |
| B | 3 | 0 | 28 | 3 |

33/34分类相同，三个支持更新对象相同。保留那一个“不支持/未决”分歧，不通过裁决制造更好结果。3/34只是当前告警的助手审查支持率，不是人类gold精确率，也不是经校准的置信度。

## 失败机制与边界

独立诊断按任务顺序看前8个两版银标都认为变化且低于0.7的参考对。例子包含团队4→5人、收藏17→25、设备使用6→9个月、画从沙发上方移到床上方。它们经常改变当前用途，却不推翻过去时点陈述；使用时长自然增长尤其不构成历史矛盾。整段混合多个属性可能增加干扰，但本轮没有消融证明这一因果解释。

另一端，高分告警经常比较不同收礼人、不同兴趣、不同旅行或可并存计划。矛盾分数本身不证明对象、属性和适用范围相同。漏检与不受支持告警共同指向监督目标错位，而不只是阈值不合适。

关闭当前默认候选路线：不继续扩大E、不降低阈值追这54条、不按失败例补数字或工具词。重启条件是明确区分历史真值、当前用途变化、同对象范围，并在新协议中有证据表明这些区别可稳定判定。不能由这54条推断全部B已达上限。

## 成本、验证与限制

两臂候选并集800个关系请求，795执行、5超长；96,266输入token、8.082秒forward。参考oracle额外1次、106token、8.411毫秒，单独记账且未进入任何候选池。加载1.996秒。FTS查询p50 5.276毫秒、p95 9.514毫秒。forward不含分词，查询不含写入/加载，不称完整服务成本或商业时延。

逐一只读核验54个SQLite库：8,747条原文、角色、顺序时间戳完全匹配输入；无当前/未来消息，候选原文回读及oracle隔离通过。时间戳是保序合成值，不是实际事件日期。验证记录见results/verification.json。

所有LME oracle题历史已用，本54条是development reuse。检查点曾用has_answer辅助选择，不是自然流随机抽样；仅用户L0、FTS配置，不是完整混合检索或L1。既有变化标签与新告警审查都是助手银标。数据复用与标签限制禁止未见泛化或高置信商业结论。

## 复跑

在MemoryCore目录运行，OUT须为新目录，SOURCE是原公开longmemeval_s_cleaned.json；PR中保留既定pair选择与逐项模型回执，原始对话从公开来源获取。

```sh
python benchmarks/topic3-b-long-v1/prepare.py "$SOURCE" benchmarks/topic3-b-long-v1/results/selection.json "$OUT"
node --import tsx benchmarks/topic3-b-long-v1/native.ts "$OUT/tasks.json" "$OUT/native"
python benchmarks/topic3-b-long-v1/relations.py "$OUT" --model "$MODEL"
python benchmarks/topic3-b-long-v1/score.py "$OUT" benchmarks/topic3-be-v7/results/replay/current/source-review.json benchmarks/topic3-be-v7/results/replay/current/source-review-second.json
python benchmarks/topic3-b-long-v1/verify.py "$OUT"
```

模型为FacebookAI/roberta-large-mnli revision 2a8f12d27941090092df78e4ba6f0928eb5eac98，PyTorch2.5.1、Transformers4.57.6、FP32。固定0.5/0.7均报告。仅重算分数时可用results/relations.jsonl替代重新模型推理，原生候选仍需重建。本研究不新增反馈学习收益或生产回退证明。
