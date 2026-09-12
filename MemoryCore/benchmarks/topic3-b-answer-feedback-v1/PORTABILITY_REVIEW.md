# 当前回答反馈集合：最小MemoryCore可移植接入审查

2026-09-13。未读取正在运行的评估输出，未改提示、模型或代码。依据已读的 `src/core/memory-feedback/{index,process,policy,lifecycle}.ts` 与answer-feedback-v1任务接口。

**最小旁路应与`processFeedback`并列，放在共同回答和checker回执已经得到之后、宿主消费反馈之前。** 新B产生的是该回答可报告的反馈集合，既不调用`FeedbackMemory.publish`，也不改变`memory.search`结果。它不是`changed`的一种别名；旧的E历史替换链保持原合同。

## 最小必要改动

增加一个小型纯选择入口，例如 `selectAnswerFeedback`，由 `memory-feedback/index.ts`导出。入口接受：

- `enabled`；共同冻结的`observation`（回答ID、回答文本及错误标记、可见用户历史、候选ID/规则/checker回执）；
- 调用方已提供的`baselineFeedback`；
- 可选的受控训练状态加载器及状态签名；
- `selector(observation, state, signal)`回调和有界timeout。

返回 `{feedback, useBaseline, status, elapsedMs}`。`feedback`只包含候选ID及可选原文来源引用，不授予持久写入权限。不需要给此入口baseStore或auxiliaryStore句柄。

关闭时直接返回原样baseline，且不调用state loader/selector/checker。开启后加载失败、状态签名不符、selector异常/超时、unknown、截断输出、重复/越界ID或选中checker非false的项，均回原baseline。有效空集合是成功选择，必须区别于unknown。超时结果只能被忽略，不能迟到覆盖已返回集合。

`baselineFeedback`必须是宿主既有的同预算普通反馈输出；若宿主原来没有反馈则为空。不能默认以“所有历史checker失败”充当安全基座，那会把已撤销/别话题要求重新告警。也不要在失败时偷偷额外跑一次昂贵direct模型，掩盖回退成本。哪种基线由具体实验先固定并共同取得。

## 可以复用与不应复用

复用`processFeedback`的 `enabled`优先短路、超时/异常返回`useBaseline`约定和已有测试形态；复用 `SourceRecord` 的recordId/version/owner/sourceId思想绑定实际读取的原文对象。原文校验需基于宿主实际快照，而非把隐藏active_topic当来源。

不能复用 `Candidate`作为新任务的全部合同：它要求later source、oldQuote/newQuote且服务于旧span替换。当前B需要“回答+候选集合”，并不总有新旧事实替代。也不能复用 `FeedbackPolicy` 的四桶changed/same统计，它学习的是核验changed率，不是可报告反馈集合。最初只消费已冻结的训练示例状态即可，不需新学习器或E账本。

可将 Python `readout`对终末ACTIONABLE、known candidate IDs、checker eligibility、输出截断的规则移植成宿主解析函数。`verified_actionability`只允许出现在明确的训练示例状态中；当前observation不得携带labels、currently_applicable、active_topic或oracle有效栈。签名应区分模型/提示/候选合同，避免读取另一实验状态。

## 与实际MemoryCore连接的最小证据

只导出新函数还不等于原生接入。benchmark host应在隔离MemoryCore实例中把原始用户消息正常写入并读回，记录真实recordId/version/sourceId；由这些实际原文构造history/候选，并将B返回集合消费成**临时回答反馈**。不必安装Gateway hook或修改默认召回。

当前answer-feedback-v1候选来自oracle规则值集合且跨topic去重，必须保留这项能力对照标记；写入MemoryCore并不能把它升级为自主抽取。`first_observed_turn`不总是当前要求的有效来源，只能据实际记录表链接首次出现，不夸称已定位当前因果出处。

## 一次可重复验证应交付什么

1. 一个隔离native读写演示回执：原始记录ID/version、读回正文一致、选择输入候选ID、最终反馈集合；相同回答及相同baseline用于所有开关路径。
2. 少量合同测试：off不调用加载/模型；合法子集与合法空集；unknown/坏输出/超时/坏状态回到逐项相同baseline；迟到结果不能发布。超时测试使用受控Promise，不需重跑模型。
3. 一份无写入副作用的前后证据：基座内容、可见版本、search结果及auxiliary记录数不因反馈选择而改变。这里验证的是本新入口不写，不做重复全库哈希。
4. 把已保存模型输出通过同一解析/选择入口重放，确认Python研究计数与宿主输出集合一致；对输出失败样本按明确基线计回退结果，另报原始B结果，不能用回退掩盖失败成本。

这些证据足以称“B反馈集合有可移植的可选宿主入口并完成关闭/失败回退合同”。只有宿主实际消费它并有对照结果后，才可声称改善回答；只有真实发现候选被测后，才可声称非oracle定位。无须创建新E权限、持久失效或检索优化流程。
