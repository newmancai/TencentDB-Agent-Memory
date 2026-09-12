# 对话反馈监督复盘：不要让局部标签要求带偏主任务

2026-09-13。上一五特征学习无主指标收益后，本轮联网并独立审查三类对话监督，实跑LoCoMo/DialFact来源合同审计。没有新模型实验，没有反馈质量收益。

## 核心修正

B的可核验对象不必是任意字符span。它可以是**针对当前问题的一条明确回答主张及其证据关系**。回答只写一个日期、对象或“是”时，脱离问题核验这段文字会丢失主体和关系；消息中确实出现该日期，也不代表它回答了当前问题。这是下一步要检验的输入语义假设，不是已经获得的结果。

长对话数据缺任意生成片段gold，不意味着必须放弃长对话、换成短对话分类。应让实验单位与公开标签支持的粒度一致，并显式保留未标注、证据不足和冲突的区别。此前RAGTruth保留为专门detector和span级强参照，不继续堆概率特征。

## 来源实核

|来源|可用监督|不能据此声称|
|---|---|---|
|[LoCoMo](https://github.com/snap-research/locomo)|长会话QA、类别、对话证据ID；可验证原问题的回答与证据对齐|未列消息都是负例；任意回答span有金标准；category5的evidence支持adversarial_answer|
|[DialFact](https://github.com/salesforce/DialFact/tree/386831c2c6dc01375a082fb08d159a3b04a8e073)|对话回答的SUPPORTS/REFUTES/NOT ENOUGH INFO，事实/个人话语类别|完整长程记忆轨迹；局部offset或自然反馈学习|
|[FaithDial](FAITHDIAL_REVIEW.md)|原回答的BEGIN标签、人工编辑的参考回答|编辑diff是错误span；后继编辑用户话语是自然反馈；长会话主验收|
|[BEGIN](https://github.com/google/BEGIN-dataset)|当前回答对给定knowledge的整回答归属标签|完整历史或任意span标签；长知识文档等于长对话|

FaithDial独立审查发现BEGIN针对original_response或其缺省response，不能贴到编辑答案；用户后继话语也可能被编辑。平均约9条双方发言，不为追求定位标签另开这条短对话主线。它仍可用于之后独立的回答级迁移对照。

DialFact固定commit386831c：valid10436/test11809条，历史0–10条发言；全量均有evidence，非证据检索现实可见性证明。valid/test context_id交1637，但精确history正文只交1，说明裸ID不可直接作为跨split会话身份；不能据ID交集就宣称1637条泄漏，也不能只看正文交1证明完全去污染。extra evidence metadata可能标记gt_evidence_added，若适配必须剔出runtime。仅审计了标签与长度，未做预测或逐例调法。

## LoCoMo 的具体陷阱

本地官方来源SHA见 results/dialogue-source-audit.json：10会话、每会话369–689条发言，1986题，1982题有evidence；2815个原始引用2806个精确定位，9题有未精确定位引用。保留原文不静默改gold，未解析项作为alignment unknown，不能作为不存在或不支持。无重复dia_id。

**446道category5均带evidence和adversarial_answer，其中444道没有普通answer、2道两字段并存。** [官方评分](https://github.com/snap-research/locomo/blob/main/task_eval/evaluation.py#L173)对这类期望无信息/未提及；所以不能统一把evidence当支持候选答案的正标签。96道category3允许开放推断，也不能与严格来源grounding混为一个指标。其他类别应按原QA语义与时间戳解释，不能仅凭答案字符串在历史出现便认定支持。

上述9个未精确引用包括合并多ID、格式异常和不存在ID；此轮只审计，不修复或改题。1982这个数字只表示字段非空，绝非1982个完整正支持标签。

## 下一条有界假设

先用既有公开长对话QA单位检验“问题关系是否在反馈核验时被保留”：比较同一证据、同一候选答案下的普通grounding强基线，与显式保留主体/关系/时间范围的核验。不能只把短answer当完整claim，也不能把问句本身当事实证据。候选可用官方参考/对抗答案进行受控判定方法验证；这不是本系统实际生成轨迹，更不等于线上自优化。

运行前必须确定：标签对应完整历史还是当前注入证据；若使用gold evidence构造受控证据包，明称oracle证据可得，不把其可见性算B发现收益；category3单列；category5保持不足信息语义，不改成世界事实false；未解析引用不补负。LoCoMo历史已被本项目复用，不能按新脚本分组就宣称未见泛化。先看是否存在值得学习的关系错误，之后才定义从先前受控反馈更新的有界策略，并与同信息普通核验比较。

这一路线尚未实现/运行。若实核现有长对话标签不能支撑该判定合同，应停止这条具体适配，不能再以不存在的span gold或合成唯一主集继续。E不扩展，当前goal与公开长对话/独立验收要求保持。

## 复跑本轮审计

```bash
python audit_dialogue_sources.py --locomo LOCOMO_JSON --dialfact DIALFACT_REPO/data --out AUDIT_JSON
```

脚本只用标准库；发布统计和未解析引用，不发布正文。DialFact下载来自官方git，LoCoMo复用现有原始文件。没有模型、GPU、MemoryCore或production动作。
