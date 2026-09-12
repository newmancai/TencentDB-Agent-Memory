# Topic3 B 研究交付审阅入口

[CUPID适用标签边界审计](topic3-b-contextual-feedback-v1/SCOPE_AUDIT.md)：排除12旧persona后新2开发persona/16会话盲审。同factor4均部分可迁移，不同factor12中4支持/5不支持/3未决；supported仅至少一条，不是整段。root预选4用途/迁移均4/4一致，非官方gold。其中3跨用途支持是当前请求已明示的实例要求，不能计新增信息。源码同factor允许前后偏好变化，关闭factor相等即反馈适用标签的训练捷径。下步固定候选处理具体要求/范围/强度，保留请求单独、冻结、无标签、受控纠正更新参照；未实现学习，不扩E。脚本重建三文件一致，无模型/生产，goal active。


[CUPID固定历史视图对照](topic3-b-contextual-feedback-v1/VIEW_RESULTS.md)：排除此前10 persona后新2开发persona/6题、12调用；用户原话相对完整历史输入63053→16866（-73.25%）、生成33.993→21.154s（-37.77%）。匿名助手审查3胜1负2平，但12输出均partial；root两题四输出3/4覆盖一致、2/2偏好一致，保留严格排他要求争议。100词指令超限5/6→1/6，硬token截断均0。固定表示非反馈学习，非等暴露信息；不升默认。不再单靠过滤角色，下一检验当前请求下反馈适用范围与强度，勿本6题追prompt或扩E。模型退出，goal active。


本PR提供可开关的B旁路接口、公开数据适配、可复现研究和失败路线知识库。**没有证明可观且稳定的B反馈学习收益，不建议作为商用默认策略。** E保留为旧实验辅助，不作为B成功的替代指标。原持续研究目标仍未完成。

## 最新补充研究

- [CUPID局部反馈与独立审查](topic3-b-contextual-feedback-v1/LOCAL_BASELINE_RESULTS.md)：公开长交互适配，16例真实推断及审查分歧；不是高置信gold或学习增益。
- [原话强基线](topic3-b-contextual-feedback-v1/RAW_BASELINE_RESULTS.md)：原话719/摘要1432 token，不宣称等质量成本优势。
- [原生原话记录](topic3-b-contextual-feedback-v1/NATIVE_RAW.md)：16事件82条L0消息真实写读，明确现有checker-failure接口不能直接代表自然反馈。

- [共享查询残差学习](topic3-b-query-feedback-v1/RESULTS.md)：704验证题对基线10胜10负，无净收益。
- [当前重排反馈](topic3-b-reranker-feedback-v1/RESULTS.md)：100开发题更新未超过普通重排，不能算跨轮B学习。
- [MemoryArena反馈合同审计](topic3-b-memoryarena-audit-v1/RESULTS.md)：五配置701序列，六个源码探针；识别监督揭示、评分与回执合同问题，未运行新的Agent质量评测。用于避免把宿主反馈或检索收益误归于B。

## 建议先审这四处

1. [B运行时接口及使用说明](../src/core/memory-feedback/README.md)：`selectAnswerFeedback`临时选择反馈；关闭、读失败、非法选择及超时返回宿主已有baseline，无记忆写入句柄。
2. [原生集成边界](topic3-b-answer-feedback-v1/NATIVE_INTEGRATION.md)：真实L0写读与保存模型回执重放；不是在读回文本上重新运行模型，更不是oracle候选的自主发现。
3. [自然反馈对照](topic3-b-natural-feedback-v1/RESULTS.md)：真实用户行为标签、受控线性头学习、廉价TF-IDF与冻结语义/温度强参照。
4. [路线知识库](B_RESEARCH_LEDGER.md)：实验假设、失败机制、停止范围、重启条件。其他benchmark目录保留为研究证据，不要求按时间逐一阅读。

## 本次同步的审阅顺序

新增研究集中在两个目录，不需要逐个历史实验按时间阅读：

1. [后见反馈迁移结果](topic3-b-hindsight-evidence-v1/TRANSFER_RESULTS.md)：610先前反馈到821后续问题，实际有界状态更新；普通缓存、无答案控制和反馈别名均未超过基线。这里最接近本题B自优化验收，也直接显示目前尚缺净收益。
2. [后见信息强基线](topic3-b-hindsight-evidence-v1/LEXICAL_RESULTS.md)：1438题，公开答案受控揭示后all@10从49.51%到75.66%；证明信息增量，不能作为未来学习收益。
3. [反馈语义与表示限制](topic3-b-hindsight-evidence-v1/PARTIAL_RESULTS.md)：独立语义抽审及20题真实生成，精确子串/ID并未解决错误归属。停止当前提示/表示变体。
4. [普通语义核验基线](topic3-b-grounding-v1/SEMANTIC_RESULTS.md)与[反馈路由](topic3-b-grounding-v1/ROUTER_RESULTS.md)：先区分模型能力改善，再看学习是否增加价值；路由验证79/90低于普通80/90。

这些新增实验不改MemoryCore/src运行时；研究旁路的内存回退检查不等于完整Gateway故障验收。脚本、固定协议、逐例回执和学习状态各在相应目录，压缩JSONL可用gzip解压。完整语料、模型与含原文的辅助状态留本地并可按公开源重建。

## 核心结果与不应外推的结论

| 实验 | 观察 | 能支持什么 |
|---|---|---|
| [公开长对话PersonaMem](topic3-be/RESULTS.md) | 18persona/36题，评估三臂均10/24 | 该B+E配置没有答案质量收益；不是自然反馈或主动核验的普遍失败 |
| [EvolIF回答反馈](topic3-b-answer-feedback-v1/RESULTS.md) | 新评估两对话20检查点，四臂均1个完整正确集合 | few-shot形式不能解决当前适用性；oracle候选与checker不等于运行时自主发现 |
| [正确前态局部诊断](topic3-b-local-update-v1/RESULTS.md) | 模型20/38，候选出生信息规则36/38 | 候选构造本身携带答案线索，不能把规则收益算作B创新 |
| [自然反馈学习](topic3-b-natural-feedback-v1/RESULTS.md) | WildChat205事件，冻结→学习macro-F1 39.77→42.61%，17胜12负，区间跨零 | 有参数更新，尚无稳定分类学习收益；大部分Brier降低已有普通温度参照解释 |
| [原话概率差](topic3-b-natural-feedback-v1/RAW_SIGNAL_RESULTS.md) | LMSYS226开发，真实/无关差分AUC0.454/0.454，语义0.828 | 关闭整段均值负反馈识别配置，不否定论文逐token自蒸馏 |

新增路线也要分开归因：普通语义模型更强、得到可信答案后检索更好，都不等于反馈驱动策略更好。现有路由和关联状态均实际发生更新，但尚未超过对应强参照。

这些表的分母、来源和指标不同，不合并为总胜率。用户表达反馈、反馈事实正确、错误由记忆引起是三层断言；目前自然反馈行为集仅验证第一层的分类，不能作后两层真值。公开长对话提供方法验证，没有真实内部编程业务结论。

## 按题目交付物核对

| 交付物 | 当前证据 | 未完成/限制 |
|---|---|---|
| 调研与设计 | [设计](topic3-be/DESIGN.md)、[复盘](topic3-be/REASSESSMENT.md)、知识库及各协议 | 新路线建议不是已实现收益 |
| 公开长对话Runner及基线 | [运行入口](topic3-be/README.md)、EvolIF等结果与脚本 | 主结果为负；LMSYS/WildChat较短，不能单独替代长对话主验收 |
| B实现与对比 | B临时选择器、反馈策略模块、四臂/受控监督对照 | 选择器本身不学习；另有离线反馈头/浅树/关联状态更新，但没有稳定净收益；原生示例用oracle候选 |
| 关闭与强制失败回退 | `answer-feedback.test.ts`、`lifecycle.test.ts`；原生回执与旧108回退核验 | 宿主必须实际消费返回的baseline；未宣称默认Gateway已启用 |
| 适配与内部移植 | [适配器](topic3-be/adapters.py)、[迁移审查](topic3-b-answer-feedback-v1/PORTABILITY_REVIEW.md) | 内部需提供真实观察、候选及可信判定，公开集标签不能复制成内部真值 |

原题允许负结果；因此这些材料可以作为研究PR审阅。用户另外要求的可观B收益或充分路线闭包持续探索仍在进行，不能因负结果材料齐备就宣布整个目标完成。

## 验证与复跑

运行时最近一次变更已通过17项B/生命周期合同测试、B模块独立类型检查与插件构建；原生开发10及评估80保存回执与Python一致。旧176库测试/108回退等属于旧B+E提交，保留其范围，不把历史数量当最新全库复测。本次同步增加研究脚本与结果，未修改src运行时；不重复运行未变化的运行时测试并冒称新验证。新增脚本的真实实验、语义审核和局部合同证据见各报告。

```bash
# 在MemoryCore目录执行运行时关键合同
./node_modules/.bin/vitest run src/core/memory-feedback/answer-feedback.test.ts src/core/memory-feedback/lifecycle.test.ts
./node_modules/.bin/tsc --noEmit --ignoreConfig --target es2022 --module nodenext --skipLibCheck src/core/memory-feedback/answer-feedback.ts
```

公开数据、固定版本、依赖和各Runner命令在对应README/PROTOCOL/RESULTS中。自然反馈原始文件通过[适配入口](topic3-b-feedback-audit/README.md)下载；仓库保留ID级预测、聚合分数及部分模型回执，完整下载语料、模型权重和运行数据库留本地。GPU计时不含加载等部分已逐项注明；没有production Memory操作。

## 继续研究的约束

目前停止的是已测配置：整段概率差、反复prompt/子主张schema、六特征浅树路由、top1绑定+固定RRF融合。没有证明全部B方向到达上限。每条路线的失败机制与重启条件见知识库，不把小样本负结果升级为普遍不可能。

下一方法需要解释**反馈能学到什么可迁移信息**，并有超越普通同信息参照的检验。已知答案帮助找回本题证据、记住旧题关联，都不足以独立满足这个条件。新方向不得据已用LoCoMo/LongMemEval误例调参后称未见验收；还需明确独立公开来源、可信观察来源，以及MemoryCore完整基座对照和适配范围。
