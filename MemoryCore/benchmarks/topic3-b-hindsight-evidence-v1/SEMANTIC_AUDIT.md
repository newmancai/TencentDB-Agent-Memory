# 新增检索候选不自动成为可信反馈

2026-09-13。FTS5后见信息实验后的固定10来源抽审，无新模型实验、无策略学习、无E。抽样脚本sample_audit.py已复跑，packet及身份映射逐项一致。

## 抽样与盲审范围

每个会话在QA top10相对Q top10有新增候选的题中，按SHA256(hindsight-audit-v1:+题ID)最小取一题，再取排名最高的新增候选。选择不使用参考证据标签。抽样代码在阅读文本前确定；这是来源均衡诊断，不是候选总体随机样本，不能估总体precision。

审阅者收到问题、受控已确认答案、候选speaker/text，以及独立列出的前后各一条消息和session日期。图片、caption等非检索文本剔除。分别判断candidate_only和with_neighbors，full/partial/none/conflict。full要求完整问答关系；partial需说明支持哪一部分；none不代表答案为假；conflict必须有明确反驳。

Root先保存判断再读取映射和独立判断。独立agent仅读packet，未读gold mapping/root判断。Root此前可能见过部分历史题，不能称全新来源双盲。两者均为助手语义判断，不是官方grader或独立人类标注。

## 观察与分歧

| 审阅者/可见上下文 | full | partial | none | conflict |
|---|---:|---:|---:|---:|
| Root/候选单句 | 1 | 3 | 6 | 0 |
| 独立/候选单句 | 0 | 5 | 5 | 0 |
| Root/邻接上下文 | 1 | 3 | 6 | 0 |
| 独立/邻接上下文 | 1 | 5 | 4 | 0 |

单句与邻接各8/10标签一致。保留全部分歧，不强行投票改gold，不把partial与full相加称可靠率。

* audit-02：候选支持Gina有舞蹈奖杯，没说明Finding Freedom、团队或第一名。独立审认为背景前提算partial，Root认为未支持答案内容而判none。这是**背景相关与答案支持**的合同分歧。
* audit-03：邻句只说John与未明同行者登顶；没有同事身份，也没明确hiking/mountaineering。独立审判partial，Root判none。缺失的限定关系能否省略，会直接影响反馈错误归属风险。
* audit-05：候选是John推荐NYC的原话，Root单句判full；独立审要求受话人Tim也有证据而判partial。邻接Tim的发言补齐后双方full。邻接确能补人物关系，但该1例不是普遍收益证明。
* audit-08/09：双方认同partial。分别只支持完整活动清单中的跑步/工作坊、以及两辆车中的旧Prius损坏。把partial一律拒绝会丢掉有用证据，把它当整答确认也会过度背书。
* audit-10：双方认同只有Dave hard work部分被支持，未覆盖Calvin及determination。该候选不在官方参考引用中，说明“未列为参考”不能直接作负标签。
* audit-01/04/06/07：双方均未建立目标关系。错误机制包括另一人的同词事件、无关DIY、称赞对方工作而非自己的压力、另一人的返程计划而非目标人物活动日期；邻接没有补救。没有明确conflict，不能据此失效旧记忆。

揭示映射后，10项只有3项列为官方参考：05/08/09。此计数不是precision，既不否定未标注10的局部价值，也不意味着08/09能单独支持整答。

## 对B设计的实际影响

关闭“把排名最高新增候选直接作为整答正反馈”的解释；也不能以扩大邻接窗口代替语义核验。后见词面增量仍成立，当前问题是怎样转成可消费监督。

下一反馈单位应是**带限定关系的答案子主张—证据对应**。至少分开记录：支持答案哪个成分、主体/对象/时间限制是否建立、只是支持问题背景还是支持答案值、剩余部分是否仍未知。缺信息时不发整答正确标签，不把unknown当记忆过时。

这不是新增复杂运行时系统的理由。下一先固定上述语义口径，在另一批开发题比较普通同信息语义核验与子主张反馈；独立审核必须按相同合同。只有能稳定产生有用且可核验的局部反馈，才继续做先前反馈学习→后续问题收益；目前尚未实现该模型比较。不得据这10例补人名/日期词或调prompt后仍把它们称验收。

[Root原判断](semantic-audit-results/root-review.json)、[独立原判断](semantic-audit-results/independent-review.json)、[分歧比较](semantic-audit-results/comparison.json)、[离线映射](semantic-audit-results/mapping.json)。正文packet留本地，可从公开源和保存的lexical回执重建：

```sh
python sample_audit.py --source /path/to/locomo10.json --receipts /path/to/receipts.jsonl --out /path/to/audit
```

持续目标未完成，B学习与独立最终验收仍缺；新结果本地未推送，远端PR#2仍43ad0db。无模型/GPU/生产操作。
