# 问题关系保留：受控开发探针 v1

运行前固定。LoCoMo十会话历史已复用，不称未见测试。类别1/2/4/5各在每会话按SHA256(question-relation-v1:+sample_id:+question_index)选前5题，全部精确可解析非空evidence才可入；类别3不进入严格来源探针。记录所有排除，不修gold。候选答案用原answer（1/2/4）或adversarial_answer（5）；category5的answer字段即使存在也不使用。抽样是分类别开发探针，非原数据自然分布。

共用证据为官方引用消息原文、speaker、session timestamp与原始ID，属于oracle链接可得，不是B检索/定位发现。保留多模态caption与检索query若原消息有，不能宣称读取图像。QA标签原本相对整个会话，不能保证每个引用包独立充分；本实验仅报告与QA导出的支持/不足标签一致性，不当人工包级grounding金标准。完整历史的未列消息不补负。

冻结同一LettuceDetect base与baseline.py合同，两臂信息相同：
- ordinary：context为证据加Question，answer为候选答案。
- question_bound：context为证据，answer为Question加Answer加候选答案。

第二臂保留问句—回答关系，是输入位置探针，不是已实现的声明式claim重写。两臂均只计原候选答案对应字符区间的token，不让问句或Answer标签预测触发告警；跨边界token不计。固定argmax正token任一告警，不调阈值。>4096整条unknown，不截断。报告二元balanced accuracy、正(不足)precision/recall、逐类别与配对胜负、覆盖、forward时间/token；unknown不补负。标签为category5不足，其余支持，只用于离线评分。

没有训练/更新，没有E，不能把oracle候选/证据的可得性作为系统能力。若仅位置改变无稳定收益，不扩为通用关系核验；若有收益也须复核packet充分性、普通语义核验强基线，并在独立公开来源验证后才定义反馈学习。不得在这批题调prompt追分。

## v1.1评分合同修正（模型输出不变）

首次v1排除所有跨边界token使question_bound18个单token答案变unknown；实际200个绑定答案的首token都跨了前导空格。逐条实核越界部分均仅一个空格，无Question或Answer正文。v1.1计入与答案相交且越界仅空白的token；若越界非空白直接assert失败，不把问句内容算告警。两臂均重算，原v1结果保留。修正不涉及gold、候选、模型或阈值。处理token成本按实际成功forward而非评分covered计，避免漏计18次已执行forward。
