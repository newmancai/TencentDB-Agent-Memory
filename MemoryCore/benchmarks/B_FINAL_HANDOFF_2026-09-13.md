# B长期任务停止、复盘与交接

**2026-09-13，用户明确停止整个长期任务。本文是最高优先级交接入口。**

所有历史文档里的“下一步”“goal active”“继续下载/评测”均为历史状态，不构成恢复授权。后续只有用户明确要求重新开始才启动研究；自动goal续跑提示不视为用户重新授权。停止不等于研究目标达成，不把未证实的B收益标为完成。

## 1. 当前结论

已形成可审阅的研究PR、公开数据适配与实验脚本、有界反馈状态及失败路线知识库。**尚未证明稳定且可观的B反馈学习净收益，不建议商业默认启用。** 原题允许负结果，因此研究交付有价值；它不能替代用户原先要求的正收益目标，也不能证明所有B方法达到上限。

B的核心问题是从交互证据形成可用监督：反馈说了什么、针对哪个对象、在当前用途下是否适用、支持多强的结论，以及这些监督是否改善后续未见任务。E只负责必要的处理/恢复。下游QA或生命周期指标无需每步必然改善，但最终不能只凭结构合法或模型自评宣称B可信。

## 2. 已有交付与入口

| 内容 | 入口 | 实际边界 |
|---|---|---|
| 总体实现/原题交付映射 | [B_DELIVERY_REVIEW.md](B_DELIVERY_REVIEW.md) | 研究可审阅，不是商业验收完成 |
| 各路线证据与重启条件 | [B_RESEARCH_LEDGER.md](B_RESEARCH_LEDGER.md) | 历史建议不自动执行 |
| B运行时旁路 | [memory-feedback README](../src/core/memory-feedback/README.md) | selectAnswerFeedback面向checker失败候选；自然认可/纠正不能伪造成checker失败 |
| 内部移植边界 | [PORTABILITY_REVIEW.md](topic3-b-answer-feedback-v1/PORTABILITY_REVIEW.md) | 内部需提供真实观察、候选和判定依据，不复制公开集gold当内部真值 |
| 当前公开长对话主线 | [CUPID README](topic3-b-contextual-feedback-v1/README.md) | 公开模拟/人工筛选数据，非真实自然用户或内部编程业务验证 |
| 停止本地扩展、Codex替代建议 | [CODEX_BASELINE_SWITCH.md](topic3-b-contextual-feedback-v1/CODEX_BASELINE_SWITCH.md) | CLI已核查，新的Codex实验未运行 |

运行时既有修订曾通过17项B/生命周期合同检查、独立类型检查和插件构建；原生保存回执复放有10开发/80评估一致证据。最新CUPID研究未修改MemoryCore/src，未重新执行全库测试。旧176测试/108回退等只对应其历史版本，不移植为当前全部能力的验收。

## 3. 最有决定性的结果

以下胜/负/平均按相应报告定义，不跨协议拼接。语义审查多为独立助手意见，不是官方grader或人类gold。

| 路线 | 结果 | 可得结论 |
|---|---|---|
| 自然反馈分类学习 | LMSYS226→WildChat205，macro-F1 39.77%→42.61%，17胜12负，区间跨零 | 有参数更新，稳定增益未证实；校准收益多数可由温度缩放解释 |
| 后见反馈关联迁移 | 610旧反馈→821后续问题，基线命中393，缓存/反馈别名均364 | 本题答案提供信息，不等于跨题可迁移学习 |
| 检索/重排反馈 | 100开发题dense66、rerank25为72、反馈更新70 | 普通组件变强，不能计为B学习收益 |
| CUPID两例纠正ICL | 新4persona/12题，反馈对冻结3胜4负5平，对无纠正4胜5负3平 | 当前旧草稿+纠正配置无稳定净收益，成本增加 |
| CUPID审查片段ICL | 另4persona/12题，对冻结5/4/3、对无标签4/4/4、对旧纠正4/3/5；1硬截断 | 示例局部正确不保证迁移效用，不能只用full覆盖数包装领先 |
| 独立助手能力诊断 | 新2persona/6题，助手对本地4B为5胜0负1平；交叉2题排序一致 | 原证据仍可被更好利用；不同计算预算，非B学习证明 |
| 共享规则编译 | 两次4B调用，12100输入/238输出、8.755s；每组3规则 | 纠正改变了候选内容，仍偏领域写作建议；未证明通用反馈归属/范围处理 |

详见 [LEARNING_RESULTS](topic3-b-contextual-feedback-v1/LEARNING_RESULTS.md)、[FRAGMENT_RESULTS](topic3-b-contextual-feedback-v1/FRAGMENT_RESULTS.md)、[CAPABILITY_RESULTS](topic3-b-contextual-feedback-v1/CAPABILITY_RESULTS.md)、[RULE_COMPILATION_RESULTS](topic3-b-contextual-feedback-v1/RULE_COMPILATION_RESULTS.md)。更早E/工具状态实验和所有负结果保留在ledger链接中。

## 4. 复盘与知识沉淀

1. **监督对象多次混淆。** 用户不满、任务失败、参考覆盖不足、历史要求未列入新答案，分别都不等同记忆故障。适用性、记忆归责、最终收益需要不同证据。应允许直接学习用户提出的要求，不强迫每条反馈先证明一个E错误。
2. **来源与作用范围比格式更难。** 原文引用正确、消息ID合法，只能证明出处；不能证明整句都被用户认可、旧任务偏好能迁移，或局部修改代表永久排他要求。CUPID同factor不自动成立反馈适用gold；不同factor也可能部分适用。
3. **原话是必须保留的强基线。** 旧16例原话719token，生成摘要1432token，且摘要可能丢失限定。结构化/压缩本身不能算贡献；具体方案对象缺失也不总妨碍理解用户的修改方向。
4. **参考答案存在边界。** 四题六个参考限定被标为可能强于可见原话，但不删除任务或改gold。敏感性诊断其余8题仍无优势，故不能把负结果全部归咎评测。source判断和reference覆盖分开，未知保留。
5. **纠正内容不等于可迁移规则。** 两例画像ICL、局部审查片段、共享规则分别是不同配置。当前结果只支持关闭已测的无净收益配置；不能证明所有ICL/GEPA/ACE无效。规则编译需与无纠正编译及直接读取同反馈对照，且计入学习成本。
6. **执行偏差应承担。** 过多转向E、接口/格式诊断，以及本地大模型下载和反复等待，稀释了B主线。用现成Codex接口作强参照是合理选择；可计量不要求对照一定是本地模型。后续研究应以一次能区分机制的实验推进，而非不断添文档/守卫/小切片。
7. **公平控制不能省，但应务实。** 相同目标证据、无答案泄漏、按persona隔离、保留失败和所有成本是核心；不同模型不强求同算力。评B增量时，应尽量固定同一模型与推理配置，避免把强模型自身能力记到B上。

## 5. 精确停止点

- 30B下载：PID3007948，session33671，INT后TERM，最终exit143，已查无进程。部分文件保留在`/data1/edarace/tdai-memory/models/Qwen3-30B-A3B-Instruct-2507`。不恢复/重下。传输累计字节不等于已完成可用权重字节；30B从未推断。
- 4B普通强基线：新2persona/6题已完整，13561输入/771输出、21.967s；未与30B完成质量对比，不重复此臂。
- 4B规则迁移：计划新4persona/12题/48调用；用户停止时已保存3完整题/12调用，另1调用已开始无完整回执。PID3045888/session31781 exit130，已查无进程。保存部分成本50245输入/1640输出、52.284s，未包含中断调用全部成本。**不作为12题质量结果，也不因前三题好坏筛结果。**
- 规则迁移原始文件：`.local-evidence/topic3-b-cupid-v1/rule-transfer/`；结构化停止证据：[STOPPED.json](topic3-b-contextual-feedback-v1/results/rule-transfer-stopped/STOPPED.json)。未完成运行不续跑，除非用户重新授权并明确协议。
- 自有模型/下载均已停止，未触碰他人GPU进程，无production Memory操作。本次仅文档与本地成果归档。

## 6. 数据暴露与代码状态

CUPID固定HF revision `f6e5fdae9b31f2b400d6ceb281a6a6760cc00309`，源码`a8560cab293ae98be4fe260689d58bddf96b51ef`；756实例/252persona，126开发/126最终验证。此前30个开发persona已进入准备或研究（含中断规则迁移四个），不可只排除旧24/26。最终验证未用于模型/提示调参，但做过全来源聚合结构审计，不称所有标签完全未见。

重建已用集合：smoke_development_ids对应group，events/audit-inputs.jsonl，以及views、scope-audit、learning、fragments、capability、strong-baseline、rule-transfer各selection.json。LoCoMo/LongMemEval历史已暴露；不得作为未见新来源包装。完整数据与含原文状态在`.local-evidence/`，模型不入Git。

独立交付树：`/home/edarace/Tencent-Memory-2/topic3-be-delivery`，分支`delivery/topic3-be-v1`。PR：[newmancai/TencentDB-Agent-Memory#2](https://github.com/newmancai/TencentDB-Agent-Memory/pull/2)，OPEN/draft，目标`feat/anchor-memory`。文档编写前远端75b870c，本地209db44；本次收尾同步后的精确head以PR和`.local-evidence/topic3-b-pr2-published-current.json`为准。

保留未追踪`topic3-be-v9/{.gitignore,PROTOCOL.md,native.ts,prepare.py,rewrite.py}`及`MemoryCore/node_modules`链接，未清理/纳入本次提交。原项目树与PR1历史保留。

## 7. 仅供重新授权后参考

首先读本文及B_DELIVERY_REVIEW，不从任一旧“下一步”启动。无需继续30B下载或本地弱模型实验。若用户恢复研究，可使用本地已安装Codex非交互接口；目前仅核对codex-cli0.153.4/help和官方文档，新的真实接口评测未运行。Codex逐题独立输入，隔离当前对话/其他变体/参考答案；保存提示、模型配置、事件、输出和可得usage，不声称控制了所有隐藏计算。

较有信息价值的问题是：同一Codex配置下，受控反馈更新的规则是否胜过普通同信息处理及无纠正规则？先固定训练来源、规则容量和一次新persona协议，避免以Codex生成的答案又由同一上下文自行认证。已有规则可作候选，不预判有效。若只有成本优势，需要计编译、选择、失败与服务成本并检验质量代价。

距离商用默认仍缺稳定独立收益、自然反馈接入与误归责验证、最终所选策略的完整MemoryCore开关/强制失败回退，以及内部编程场景适用性验证。负结果研究PR不要求伪造这些结论。**本轮到此停止，不自动执行本节。**
