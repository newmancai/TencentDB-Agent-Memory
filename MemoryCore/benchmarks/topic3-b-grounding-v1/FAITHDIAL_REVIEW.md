# FaithDial 的 B 适用边界

只读官方论文、HF schema/loader/数据卡及 GitHub critic 代码，未下载全集或运行模型。核验版本：GitHub `25671c6e3aa7d667943b7744a2b91507e7187f83`；HF `7a414e80725eac766f2602676dc8b39f80b061e4`。

**BEGIN 不能直接贴到 edited response 上。** 官方 [FaithDialProcessor._load / _convert_label，L109–143](https://github.com/McGill-NLP/FaithDial/blob/25671c6e3aa7d667943b7744a2b91507e7187f83/models/critic_data.py#L109)明确把 BEGIN 配给 `original_response or response`；只有训练分支另把编辑后的 `response` 加作 Entailment。Hallucination 优先于 Entailment，其余返回 None，不是“一切非 Entailment 都为幻觉”。[HF 数据卡](https://huggingface.co/datasets/McGill-NLP/FaithDial/blob/7a414e80725eac766f2602676dc8b39f80b061e4/README.md)解释 original_response 为空代表该原回答被视为 faithful，但仍可能做语法/拼写编辑；因此空字段不表示漏标，也不能根据非空字段就把原回答全判幻觉。官方训练条件甚至会为某些 original_response 为空且 response 非空的项添加另一条 Entailment，若复现须按代码说明，不应擅称每个样本严格一对正负。

**没有可直接使用的局部 offset gold。** [官方 HF loader](https://huggingface.co/datasets/McGill-NLP/FaithDial/blob/7a414e80725eac766f2602676dc8b39f80b061e4/FaithDial.py)暴露 `dialog_idx,response,original_response,history,knowledge,BEGIN,VRM`，BEGIN/VRM 是字符串列表，未提供对应回答或知识的字符位置。局部断言抽取只能另作预测候选，BEGIN 是整条原回答的标签；不能据它给回答内每个句子正标。编辑 diff 也不是 goldspan：编辑包含去除无据信息、增加有据事实、改写、语法修正和对话合作性修复。

**它是经过编辑的多轮对话，不是自然延迟反馈，也不足以充当长对话主协议。** [论文 §2.2.1–2.2.2](https://arxiv.org/html/2204.10757v3#S2.SS2)明确同时编辑 wizard 和后继 seeker，使新历史连贯；§4.1 报告 wizard 84.7%、seeker 28.1% 被修改。后继用户句因此不能默认解释成真人对最终编辑答案的实际反应，更不能把旧 original_response 与编辑后的后继句组成自然反馈因果对。总量 50,761 utterances/5,649 dialogues，平均约 9 条双方 utterance（约 4–5 轮问答），不是 50K 长度的一条对话。本次未计算长度尾部分布，不声称没有较长个例；现有证据不足以承担多会话长期记忆验证。

**可用之处是整回答 grounding 的监督迁移或正负排序，非直接局部定位。** [论文 §5.1](https://arxiv.org/html/2204.10757v3#S5.SS1)的 critic 就是知识—回答二分类，官方实现输入不包含完整 history。可以在保留会话上比较冻结 detector 与训练反馈形成的有界接纳头，保持相同 knowledge/original response、候选与成本；把 edited response 作为受控训练参考时，应对所有学习基线提供相同信息，并保留原/编辑成组、防止版本跨划分泄漏。不能把“编辑版本被设为 Entailment”冒称逐条独立验证的事实真值。

对当前 B 的结论：值得作为**回答级跨来源 grounding 对照**，不应为了换数据立即把目标改成整题并宣布原局部反馈问题已解决。如果当前实验必须有断言—证据定位 gold，它不能直接补齐；若使用，先明确只验证回答级告警接纳。后续反馈驱动学习、原文片段质量和公开长对话仍须分别验证，不能用该数据的编辑历史或模型成绩替代，也不需要扩展 E 写入管理。
