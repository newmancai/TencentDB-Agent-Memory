# Topic3 B 研究交付审阅入口

本PR提供可开关的B旁路接口、公开数据适配、可复现研究和失败路线知识库。**没有证明可观且稳定的B反馈学习收益，不建议作为商用默认策略。** E保留为旧实验辅助，不作为B成功的替代指标。原持续研究目标仍未完成。

## 建议先审这四处

1. [B运行时接口及使用说明](../src/core/memory-feedback/README.md)：`selectAnswerFeedback`临时选择反馈；关闭、读失败、非法选择及超时返回宿主已有baseline，无记忆写入句柄。
2. [原生集成边界](topic3-b-answer-feedback-v1/NATIVE_INTEGRATION.md)：真实L0写读与保存模型回执重放；不是在读回文本上重新运行模型，更不是oracle候选的自主发现。
3. [自然反馈对照](topic3-b-natural-feedback-v1/RESULTS.md)：真实用户行为标签、受控线性头学习、廉价TF-IDF与冻结语义/温度强参照。
4. [路线知识库](B_RESEARCH_LEDGER.md)：实验假设、失败机制、停止范围、重启条件。其他benchmark目录保留为研究证据，不要求按时间逐一阅读。

## 核心结果与不应外推的结论

| 实验 | 观察 | 能支持什么 |
|---|---|---|
| [公开长对话PersonaMem](topic3-be/RESULTS.md) | 18persona/36题，评估三臂均10/24 | 该B+E配置没有答案质量收益；不是自然反馈或主动核验的普遍失败 |
| [EvolIF回答反馈](topic3-b-answer-feedback-v1/RESULTS.md) | 新评估两对话20检查点，四臂均1个完整正确集合 | few-shot形式不能解决当前适用性；oracle候选与checker不等于运行时自主发现 |
| [正确前态局部诊断](topic3-b-local-update-v1/RESULTS.md) | 模型20/38，候选出生信息规则36/38 | 候选构造本身携带答案线索，不能把规则收益算作B创新 |
| [自然反馈学习](topic3-b-natural-feedback-v1/RESULTS.md) | WildChat205事件，冻结→学习macro-F1 39.77→42.61%，17胜12负，区间跨零 | 有参数更新，尚无稳定分类学习收益；大部分Brier降低已有普通温度参照解释 |
| [原话概率差](topic3-b-natural-feedback-v1/RAW_SIGNAL_RESULTS.md) | LMSYS226开发，真实/无关差分AUC0.454/0.454，语义0.828 | 关闭整段均值负反馈识别配置，不否定论文逐token自蒸馏 |

这些表的分母、来源和指标不同，不合并为总胜率。用户表达反馈、反馈事实正确、错误由记忆引起是三层断言；目前自然反馈行为集仅验证第一层的分类，不能作后两层真值。公开长对话提供方法验证，没有真实内部编程业务结论。

## 按题目交付物核对

| 交付物 | 当前证据 | 未完成/限制 |
|---|---|---|
| 调研与设计 | [设计](topic3-be/DESIGN.md)、[复盘](topic3-be/REASSESSMENT.md)、知识库及各协议 | 新路线建议不是已实现收益 |
| 公开长对话Runner及基线 | [运行入口](topic3-be/README.md)、EvolIF等结果与脚本 | 主结果为负；LMSYS/WildChat较短，不能单独替代长对话主验收 |
| B实现与对比 | B临时选择器、反馈策略模块、四臂/受控监督对照 | 选择器本身不学习；原生示例用oracle候选，学习实验尚未构成商用反馈链 |
| 关闭与强制失败回退 | `answer-feedback.test.ts`、`lifecycle.test.ts`；原生回执与旧108回退核验 | 宿主必须实际消费返回的baseline；未宣称默认Gateway已启用 |
| 适配与内部移植 | [适配器](topic3-be/adapters.py)、[迁移审查](topic3-b-answer-feedback-v1/PORTABILITY_REVIEW.md) | 内部需提供真实观察、候选及可信判定，公开集标签不能复制成内部真值 |

原题允许负结果；因此这些材料可以作为研究PR审阅。用户另外要求的可观B收益或充分路线闭包持续探索仍在进行，不能因负结果材料齐备就宣布整个目标完成。

## 验证与复跑

运行时最近一次变更已通过17项B/生命周期合同测试、B模块独立类型检查与插件构建；原生开发10及评估80保存回执与Python一致。旧176库测试/108回退等属于旧B+E提交，保留其范围，不把历史数量当最新全库复测。当前收拢仅修改文档。

```bash
# 在MemoryCore目录执行运行时关键合同
./node_modules/.bin/vitest run src/core/memory-feedback/answer-feedback.test.ts src/core/memory-feedback/lifecycle.test.ts
./node_modules/.bin/tsc --noEmit --ignoreConfig --target es2022 --module nodenext --skipLibCheck src/core/memory-feedback/answer-feedback.ts
```

公开数据、固定版本、依赖和各Runner命令在对应README/PROTOCOL/RESULTS中。自然反馈原始文件通过[适配入口](topic3-b-feedback-audit/README.md)下载；仓库保留ID级预测、聚合分数及部分模型回执，完整下载语料、模型权重和运行数据库留本地。GPU计时不含加载等部分已逐项注明；没有production Memory操作。
