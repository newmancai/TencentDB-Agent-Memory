# B反馈对象重置：回答相对可见证据的支持

2026-09-13，已完成来源适配和冻结专门 detector 的开发基线；尚无本项目学习收益。最新结果见 [RESULTS](RESULTS.md)。上一原话均值信号缺少定位监督；本路线使用公开人工span标注，检验反馈能否指向回答中确有证据问题的部分。**这是回答grounding反馈，不是记忆根因归责，也不自动是事实判错。** E不参与。

## 已实际核验

[RAGTruth官方固定版本](https://github.com/ParticleMedia/RAGTruth/tree/c103204b9ce28d6bbad859304bf30de72b8ed8fe)提供2965个source、17790个回答；14289处span均满足`answer[start:end] == text`。按官方`quality == good`训练/评估口径保留17617，另外173个截断/错误拒答保留排除记录，不当干净负例。

训练14942回答/2515来源，测试2675回答/450来源；source ID交集0，规范化精确source_info内容交集0。后者不排除近似重复或相关来源，不当完整去污染证明。任务来自QA989、Data2txt1033、Summary943个来源，不是长对话轨迹。

全部标注中1928个`implicit_true`、1642个`due_to_null`，都按官方保留。内容在外界可能为真但当前来源未提供，仍可违反严格source-grounding合同；null也不能自动变成false。完整[独立审核](SUPERVISION_REVIEW.md)核对论文和官方代码，发现官方公开评估脚本仅实现回答级非空标签P/R/F1；之后若自建span指标，必须另定义，不能冒称官方span复现。

## 可运行适配

下载`dataset/response.jsonl`与`dataset/source_info.jsonl`到SOURCE（固定URL/SHA256在results/source-manifest.json）。执行：

```bash
python prepare.py --source SOURCE --out ADAPTED
```

`observations.jsonl`只含ID、source分组、split、原始生成context、完整answer和来源类型；`labels.jsonl`单独存人工span/标注元数据。当前使用完整原prompt作为context，保留来源及原生成任务条件；没有把annotator meta、gold spans或quality字段放进推理输入。内部适配可替换context为实际给模型的指令和记忆片段、answer为实际回答；source ID对齐不意味着能确定导致错误的具体记忆条目。

原始下载和适配正文留本地`.local-evidence/topic3-b-grounding-audit`；PR仅含可复跑代码、数据摘要和协议说明。本轮冻结基线启动过本地 GPU，已退出；未写 MemoryCore/production。

## 边界和下一比较

必须保留与普通任务生成的区别：编程Agent新写出的代码不必曾在记忆中出现，“新内容”不自动是幻觉。此严格grounding合同只能约束声称依据已提供证据的部分，不能全覆盖正常编程创作。将来迁移时需界定哪些回答断言受来源约束，并用独立标签检验；本数据不自动补齐此条件。

下一先核验可复用的专门grounding detector及其训练/测试来源，再在官方隔离来源上建立冻结强基线；不从弱Qwen/字符串基线重新绕一圈。可借鉴[LettuceDetect](https://github.com/KRLabsOrg/LettuceDetect)公开的token级实现，但其已训练能力只能归于上游；未经实际运行不能引用其宣传分数为本项目结果。新方法必须与同一detector冻结路径比较反馈驱动更新，不能只用模型替换宣称自优化。

所选B学习对象应有限且临时，例如基于先前人工核验反馈更新候选反馈的接纳策略；每次更新只可用先前开发反馈，测试来源冻结。冻结基线协议和开发结果已完成；反馈学习的具体参数/成本协议仍待确定。若只是又一次概率变软而没有更好的定位/误报/覆盖代价，不包装成新语义能力。

原题公开长对话Runner、开关/回退及研究PR已保留；本新组件本身尚不满足公开长对话方法验证或自优化，goal active。[总交付入口](../B_DELIVERY_REVIEW.md)。
