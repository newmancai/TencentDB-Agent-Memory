# RAGTruth：B 回答 grounding 对象与官方口径

只读核验官方论文及仓库 commit `c103204b9ce28d6bbad859304bf30de72b8ed8fe`，未跑模型；逐条数据计数、offset 和 source 分组由主线程另报。结论：该标签适合验证“回答相对当时提供的证据，哪里有无据或冲突断言”的 B 反馈质量，不能直接充当世界事实真值、用户满意度或记忆故障归责。

## 必须保留的三项标签语义

- `implicit_true`：README 称内容正确但上下文未提及；论文 §3.4 更审慎地描述为可能真实的上下文外信息。严格 RAG 合同仍将其标为 hallucination，不能为了提高模型成绩删掉。可以另报这个切片；若业务允许外部常识，必须事前定义另一合同，不能混称复现官方口径。
- `due_to_null`：标记把未知 JSON 值解释为否定的无据断言，论文按 evident baseless information 处理。`null`/`None` 不等于 `false`/`No`。这是回答处理可见证据的错误，不证明源数据错误或检索遗漏。
- `quality` 是回答质量元数据。README 将 `incorrect_refusal` 定义为已有相关上下文却错误拒答，`truncated` 为意外截断。二者不能被改成无 hallucination 的干净负例，也不能把拒答问题自动归为记忆故障。

依据：[固定 README L23–25](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/README.md#L23)、[论文 §3.4](https://arxiv.org/html/2401.00396v2#S3.SS4)。论文 Appendix C Table 10 单列两种 span metadata，Appendix D Table 11 明确 unknown/negation 区分；它们并非应默认删除的坏标注。

## 实际公开评估代码的口径

[prepare_dataset.py L34–40](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/baseline/prepare_dataset.py#L34)对 train/test 一律只保留 `quality == 'good'`。其 L48–58 按 source_id 划内部开发集，每个任务随机取 50 个 source；尽管注释写 10%，实际代码是固定 50，不能机械照搬注释。相同 source 的不同模型回答应始终成组。

[dataset.py L112–115](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/baseline/dataset.py#L112)把全部 labels 的原文 span 放进训练输出列表，没有过滤 `implicit_true` 或 `due_to_null`。[predict_and_evaluate.py L85–90](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/baseline/predict_and_evaluate.py#L85)按 gold/predicted 列表是否非空算 response-level precision/recall/F1，并按三个任务分报。这个文件没有实现 word/span 定位指标，不能把自己的字符重叠或 exact-span 分数叫官方代码分数。脚本推理允许最多 10 次重试，任何新对照必须统一解析/重试预算并计入成本，不能只拿最终成功结果与单次调用比较。

## 对本项目的可移植约束

B 输出的最小对象是 `answer_id + 原回答span + 检查过的source集合 + unsupported/conflict/unknown`。标签提供的是回答 span，不是天然的最小 source 支持集或记忆条目归责；定位输出若只回传离线 gold span，属于 oracle 候选条件下关系判断，不能称自主发现。应在完整可见回答上评价定位/覆盖，或明确单列候选覆盖上限；两类试验不可混报。当前 gold、annotator meta、quality 和特殊标签不得进入运行输入。`quality` 过滤用于事前评分队列，并另报被排除数与覆盖范围。

必须忠实传入实际提供的完整 source（或如实记录共同裁剪）。若只给检索 top-k 子集，遗漏支持后产生的告警属于该子集下缺证据，不可沿用“完整 source 无据”的标签解释；同理不能据 RAGTruth 判断 MemoryCore 检索故障。基线和 B 应共享同一回答、source、候选范围、调用预算与失败处理，训练与测试按 source_id 隔离，而不是按六种模型回答 ID 随机拆分。官方数据是 QA/Data2txt/Summary 的来源—回答样本，不是多会话记忆轨迹。

因此这一步可以重新明确 B 的可验证反馈对象，但仍只是组件台阶，不能代替原题的长对话与自优化要求。唯一顺接目标应保持同一 grounding 对象：先固定源隔离的监督反馈选择/校准头，并与同信息静态 detector 比较保留来源上的定位、误报、覆盖及成本；成功后，将相同接口接到长对话中实际检索证据和回答的日志上，以会话隔离且只用此前已核验反馈更新这个小策略头。新增头只改变临时反馈选择，不要求 E 删除/改写记忆。若只证明离线分类，或只在原固定样本重放正确，就分别报告监督组件与接口证据；不能宣布长对话学习收益。该后续仍需真实运行与独立反馈正确性验证，RAGTruth 本身不补齐它们。
