# Topic3 B 研究交付审阅入口

**用户已在初版交付完成后明确恢复后续复盘与研究优化；恢复范围不包含旧30B下载、旧prompt追分或production写入。当前新主线是 [B公开集组合协议](topic3-b-public-suite-v1/README.md)：B负责记忆决策，E只提供闭环回执；历史入口仍保留 [STALE时态失效研究](B_STALE_RESEARCH_REVIEW_2026-09-13.md) 与 [最终复盘与交接](B_FINAL_HANDOFF_2026-09-13.md)。下文历史“下载中”仍已失效。**

**最终五项交付的统一入口是 [B+E完整交付总报告](B_COMPLETE_DELIVERY_2026-09-13.md)，机器可读索引是 [delivery-summary.json](topic3-b-delivery-v1/results/delivery-summary.json)。当前状态为`pass_with_mixed_method_evidence`：五项材料通过，Trigger/ValidMem为正向方法验证，CUPID自然反馈主结果仍为负，产品级长期收益未证明。**

用户最新校正：[停止本地扩展，改用Codex强对照](topic3-b-contextual-feedback-v1/CODEX_BASELINE_SWITCH.md)。30B下载与未完成规则迁移已停止，保留部分成本，不报质量结论；下方历史“下载中”状态已失效。

[CUPID可计量强基线准备与半程实跑](topic3-b-contextual-feedback-v1/STRONG_BASELINE_RESULTS.md)：新2开发persona/6题排除24；4B六调用13561输入771输出21.967s，无超限/错误，质量未审。固定30B-A3B revision0d7cf239下载中，尚未运行。GPU分片代码与gold隔离独立审查通过，30B部署未验证。模型升级只诊断普通能力，不算B学习；下一两臂齐全匿名审，再冻结同基座检验同反馈更新增益。无E/生产，goal active。

[CUPID隔离能力诊断](topic3-b-contextual-feedback-v1/CAPABILITY_RESULTS.md)：新2开发persona/6题，本地Qwen6调用12700输入669输出19.235s；每题独立助手无gold推断匿名5胜0负1平，覆盖local2full/assistant4full，交叉两题排序2/2、覆盖3/4。助手预算/模型调用未可比计量，非同算力/B学习收益。首次单助手6题有跨变体曝光，评分前排除并保留，改6全新逐题任务；本地不重跑。实际输入正文实核一致。表面专属、其他任务偏好及新交互要求处理改善，不能全归咎信息缺失。下一可计量可复现的更强普通基线后再学具体反馈误用，勿新6调prompt/挑模型；session5253 exit0，goal active，无E/生产。


[CUPID参考→反馈可观察性复核](topic3-b-contextual-feedback-v1/REFERENCE_FEEDBACK_LIMITS.md)：四题六个过强参考限定条款级标记，不删题/改gold。原12 reviewed对unlabelled4胜4负4平保持；其余8仅诊断对unlabelled/feedback均2胜3负3平，故无收益不能全归咎参考问题。独立核算一致。reference覆盖缺项≠可见用户要求遗漏≠违令，不能直接训练partial为确定纠正；仍保留同题其他源文错误。下一能力诊断需新persona、输入隔离、区分可见要求/范围强度/参考覆盖，不声称独立助手同算力。未选模型/运行新推断，无GPU/E/生产，goal active。


[CUPID审查片段四臂](topic3-b-contextual-feedback-v1/FRAGMENT_RESULTS.md)：新4开发persona/12题48调用，reviewed对frozen5胜4负3平、对unlabelled4胜4负4平、对feedback4胜3负5平，助手语义意见；full2/4/5/5不能单独算收益。330132输入7102输出234.420s，reviewed1硬截断保留，生成较旧纠正+7.72%。root3可判题三参照均一致，另1未决。停止当前两示例全历史画像ICL措辞迭代，未否定所有B；联网CICL与correct-example效用论文复核记录ICL_ROUTE_REVIEW。下步改变可测要求级行为或能力对照，不在12追分/扩E。session59924 exit0，goal active。


[CUPID纠正示范编译](topic3-b-contextual-feedback-v1/COMPILATION_RESULTS.md)：旧2开发例实际2调用6266输入241输出7.892s，核心修复2full，但具体消息引用0/2、完整可接纳0/2，第二例新增受众/不适用范围误述。独立教师选连续原句并附用户ID，宿主构造容量2 reviewed_fragment_not_complete_gold状态；第二片段烹饪限定仍不完整。结构通过非语义真值，篡改片段拒绝不写。无新任务对照/学习收益；关闭自动接纳完整修复配置，保留局部示范路线，勿旧12追分/扩E。session46002 exit0，goal active。


[CUPID纠正示例四臂实跑](topic3-b-contextual-feedback-v1/LEARNING_RESULTS.md)：2旧开发受控纠正示例、新4persona/12题，48调用235461输入6220输出198.742s。feedback对frozen3胜4负5平、对unlabelled4胜5负3平（助手语义意见）；full0/1/2不等总体成功，root4题排序一致3/4与2/4。feedback输入103354对普通30094、无纠正100186，100词超限12/12；均无硬截断/失败。研究旁路ICL状态非权重训练/原生fallback。关闭当前旧草稿+纠正配置收益主张，未关闭B；下一核验正确局部示范能否替代缺陷画像，勿旧12追prompt/变体，不扩E。模型session62457 exit0，goal active。


[CUPID适用标签边界审计](topic3-b-contextual-feedback-v1/SCOPE_AUDIT.md)：排除12旧persona后新2开发persona/16会话盲审。同factor4均部分可迁移，不同factor12中4支持/5不支持/3未决；supported仅至少一条，不是整段。root预选4用途/迁移均4/4一致，非官方gold。其中3跨用途支持是当前请求已明示的实例要求，不能计新增信息。源码同factor允许前后偏好变化，关闭factor相等即反馈适用标签的训练捷径。下步固定候选处理具体要求/范围/强度，保留请求单独、冻结、无标签、受控纠正更新参照；未实现学习，不扩E。脚本重建三文件一致，无模型/生产，goal active。


[CUPID固定历史视图对照](topic3-b-contextual-feedback-v1/VIEW_RESULTS.md)：排除此前10 persona后新2开发persona/6题、12调用；用户原话相对完整历史输入63053→16866（-73.25%）、生成33.993→21.154s（-37.77%）。匿名助手审查3胜1负2平，但12输出均partial；root两题四输出3/4覆盖一致、2/2偏好一致，保留严格排他要求争议。100词指令超限5/6→1/6，硬token截断均0。固定表示非反馈学习，非等暴露信息；不升默认。不再单靠过滤角色，下一检验当前请求下反馈适用范围与强度，勿本6题追prompt或扩E。模型退出，goal active。


本PR提供可开关的B旁路接口、公开数据适配、可复现研究和失败路线知识库。**没有证明可观且稳定的B反馈学习收益，不建议作为商用默认策略。** E保留为旧实验辅助，不作为B成功的替代指标。原持续研究目标仍未完成。

## 代码收敛状态

2026-09-13按产品代码与研究证据分层重构：MemoryCore生产侧只保留回答反馈、依赖候选和E生命周期三个显式旁路；因果trace/replay、scope、target与candidate编译迁至`benchmarks/support/memory-feedback`。`core/index.ts`恢复上游原样，不再向稳定Core API扩散实验类型。运行时实现从13文件收敛为4文件，生产实现约620行；历史实验脚本和结果继续作为可复现证据保留，不混作产品运行时代码。

结构依据是[Codex仓库的Core与API面约束](https://github.com/openai/codex/blob/main/AGENTS.md)和[TencentDB Agent Memory的独立MemoryCore/轻量Adapter边界](https://github.com/TencentCloud/TencentDB-Agent-Memory)。Anthropic公开的Claude Code仓库主要提供插件、示例、安装与问题跟踪材料，因此本次不把它表述成Claude Code核心源码级重构依据。

本次重构不改变策略结论或默认开关。57项相关测试、独立TypeScript检查、插件构建及SQLite host trace重放均通过。

## 最新补充研究

- [Trigger真实host留出结果](topic3-b-public-suite-v1/TRIGGER_RESULTS.md)：固定32开发/140留出，`gpt-5.6-sol`通过Codex MCP真实调用隔离MemoryCore L1。冻结v3完整通过130/140对base 112/140，21胜3负116平；相关簇bootstrap差值`[+5.98,+19.13]pp`、sign `p=0.00235`。负例静默41/66→59/66，正例触发73/74→72/74，工具调用144→94；是公开微任务正向方法验证，不是长编程任务/自然反馈学习/高置信产品指标。关闭、正常、强制bridge失败三模式均通过且store隔离；Codex CLI 0.153.4的MCP路径仍标为under development。
- [B公开集组合协议](topic3-b-public-suite-v1/README.md)：固定近期 H6、AMB、ValidMem 与 Trigger Bench revision。H6完成30任务/90 variant的标签隔离适配和六类 checker 四状态烟测；AMB完成34任务/196正式session适配及关键合同审计，实际失败回执形成的B候选在同任务重放1/1改善但仍无跨任务收益。ValidMem v1.1全量466例/1,393记忆完成适配和Codex评测：固定开发60例选择type-aware策略后，一次性406例留出从普通374/406提高到387/406，15胜2负389平，case级`p=0.00235`；按26个batch聚类的bootstrap区间为`[+0.25,+7.39]pp`，但batch符号检验`p=0.125`。Trigger Bench完成真实host留出并在相关簇检验下保持正向，详见上一条。两者均是方法验证，不是自然反馈学习或高置信产品收益。完整口径见[ValidMem结果](topic3-b-public-suite-v1/VALIDMEM_RESULTS.md)、[Trigger结果](topic3-b-public-suite-v1/TRIGGER_RESULTS.md)与[近期数据集复盘](topic3-b-public-suite-v1/DATASET_SELECTION_REVIEW.md)。H6上游受控strategy与Codex自由编辑action space不能直接混算。
- [B+E编码产品就绪度](B_E_PRODUCT_READINESS_2026-09-13.md)：初版研究交付满足，稳定B+E质量收益与Codex/Claude Code产品对标未满足。新增四臂顺序编码任务runner，主指标为各产品内部MemoryCore相对clean增量；尚未运行，不报产品成绩。
- [STALE时态失效研究](B_STALE_RESEARCH_REVIEW_2026-09-13.md)：直接最终绑定13/16失败，两阶段桥接13/16失败；全新留出集的candidate-only依赖扩展15/16通过（正例8/8、T2 4/4、负例7/8）。新增接口只提名待核验记忆，关闭/失败为空增量且永不写记忆；小样本方法验证不改变公开长对话负收益或商用结论。
- [STALE候选池检索](topic3-b-stale-universe-v1/RESULTS.md)：另200行固定BM25，真实新会话用户文本找旧会话recall@8为96%、T2 94%；归一化M_new仅61%/53%。支持下一步在raw session top-8上验证，不等于MemoryCore生产检索或答案收益。

- [CUPID局部反馈与独立审查](topic3-b-contextual-feedback-v1/LOCAL_BASELINE_RESULTS.md)：公开长交互适配，16例真实推断及审查分歧；不是高置信gold或学习增益。
- [原话强基线](topic3-b-contextual-feedback-v1/RAW_BASELINE_RESULTS.md)：原话719/摘要1432 token，不宣称等质量成本优势。
- [原生原话记录](topic3-b-contextual-feedback-v1/NATIVE_RAW.md)：16事件82条L0消息真实写读，明确现有checker-failure接口不能直接代表自然反馈。

- [共享查询残差学习](topic3-b-query-feedback-v1/RESULTS.md)：704验证题对基线10胜10负，无净收益。
- [当前重排反馈](topic3-b-reranker-feedback-v1/RESULTS.md)：100开发题更新未超过普通重排，不能算跨轮B学习。
- [MemoryArena反馈合同审计](topic3-b-memoryarena-audit-v1/RESULTS.md)：五配置701序列，六个源码探针；识别监督揭示、评分与回执合同问题，未运行新的Agent质量评测。用于避免把宿主反馈或检索收益误归于B。

## 建议先审这四处

1. [B运行时接口及使用说明](../src/core/memory-feedback/README.md)：`selectAnswerFeedback`临时选择反馈；关闭、读失败、非法选择及超时返回宿主已有baseline，无记忆写入句柄。研究用trace/replay不属于生产公共API。
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
| 调研与设计 | [完整总报告](B_COMPLETE_DELIVERY_2026-09-13.md)、[深度复盘](B_DEEP_RESEARCH_RETROSPECTIVE_2026-09-13.md)、知识库及各协议 | 产品收益边界仍保留 |
| 公开长对话Runner及基线 | [CUPID协议与runner](topic3-b-delivery-v1/PUBLIC_LONG_DIALOGUE_PROTOCOL.md)、[结构化结果](topic3-b-delivery-v1/results/public-long-dialogue.json) | 交付通过，feedback对frozen 3胜4负5平，负结果保留 |
| B实现与对比 | B旁路模块；Trigger真实host 130/140对112/140；ValidMem 387/406对374/406 | 是方法验证；自然反馈学习、跨任务产品收益未证明 |
| 关闭与强制失败回退 | [sidecar四态](topic3-b-delivery-v1/results/runtime-contract.json)与[Codex MCP三态](topic3-b-public-suite-v1/results/trigger-runtime-contract.json) | 默认Gateway未启用，生产宿主仍需自己的故障注入 |
| 适配与内部移植 | [公开套件适配器](topic3-b-public-suite-v1/README.md)、[移植说明](topic3-b-delivery-v1/PORTING.md)、[PR #2](https://github.com/newmancai/TencentDB-Agent-Memory/pull/2) | 内部必须提供真实观察、候选和可信checker，公开gold不能复制成内部真值 |

原题允许负结果；因此这些材料可以作为研究PR审阅。用户另外要求的可观B收益或充分路线闭包持续探索仍在进行，不能因负结果材料齐备就宣布整个目标完成。

## 验证与复跑

当前重构已通过10个文件57项相关测试、B入口独立类型检查、插件构建及SQLite host trace重放。原生开发10及评估80保存回执与Python一致；旧176库测试/108回退等属于旧B+E提交，保留其范围，不把历史数量当最新全库复测。新增脚本的真实实验、语义审核和局部合同证据见各报告。

```bash
# 在MemoryCore目录执行运行时关键合同
./node_modules/.bin/vitest run src/core/memory-feedback/*.test.ts __tests__/memory-feedback-replay/*.test.ts src/core/self-supervision/openclaw-recall-turn-bridge.test.ts
./node_modules/.bin/tsc --noEmit --target es2022 --module nodenext --moduleResolution nodenext --strict --skipLibCheck --types node src/core/memory-feedback/answer-feedback.ts src/core/memory-feedback/dependency-candidate-adapter.ts
npm run build:plugin
```

公开数据、固定版本、依赖和各Runner命令在对应README/PROTOCOL/RESULTS中。自然反馈原始文件通过[适配入口](topic3-b-feedback-audit/README.md)下载；仓库保留ID级预测、聚合分数及部分模型回执，完整下载语料、模型权重和运行数据库留本地。GPU计时不含加载等部分已逐项注明；没有production Memory操作。

## 继续研究的约束

目前停止的是已测配置：整段概率差、反复prompt/子主张schema、六特征浅树路由、top1绑定+固定RRF融合。没有证明全部B方向到达上限。每条路线的失败机制与重启条件见知识库，不把小样本负结果升级为普遍不可能。

下一方法需要解释**反馈能学到什么可迁移信息**，并有超越普通同信息参照的检验。已知答案帮助找回本题证据、记住旧题关联，都不足以独立满足这个条件。新方向不得据已用LoCoMo/LongMemEval误例调参后称未见验收；还需明确独立公开来源、可信观察来源，以及MemoryCore完整基座对照和适配范围。
