# 有界反馈接纳实验 v1（运行前确定）

问题：既有 detector 已输出具体候选片段，先前人工核验反馈能否改善有限核验预算下的候选排序？E不参与，不将该对象解释为记忆根因。

排除已使用150来源，从官方train各任务按 SHA256(grounding-feedback-v1:+source_id) 排序选前100来源：前50为feedback，后50为validation。两个集合各150来源、互不重叠；使用全部good回答，不依据标签抽样。上游仍可能已训练这些来源；这是开发机制筛查，非泛化验收，官方test保持未用。

输入与冻结baseline完全相同，复用baseline.py推理。候选为固定argmax产生的连续正token span，不借gold发现候选。每候选计算token概率mean/min/max/std及log1p字符长度五特征。反馈标签定义为预测span中至少50%字符落入原gold区间；标签只用于feedback组拟合StandardScaler+LogisticRegression(C=1,max_iter=1000)，默认固定参数，无搜索。该50%是新候选核验任务定义，不是原官方span指标；同时用连续字符precision报告边界损失，防止二元标签遮掩过宽跨度。

比较：上游全部候选、mean概率排序、max概率排序、反馈学习排序。后三者在相同validation候选池保留前25%/50%（向上取整），tie用id/start稳定排序；同预算并无额外模型调用。报告候选核验正确率、字符precision和全gold字符覆盖，拒绝候选不当干净负例。各任务分开报告，不只报总体。学习成本包括feedback组所有人工标注回答数量（来自公开标签，不声称免费线上核验），拟合时间另记。

主比较为50%预算下学习vs mean概率；source分组bootstrap 2000次，种子20260913，复用已冻结排序和接纳集合估计候选precision差异区间。max与25%为参照，不依据结果换主指标。validation不拟合、不调阈值、不反向分数。发现负结果则关闭此五特征接纳头配置；不据本validation补特征。即使正结果，也必须再做未观察来源与公开长对话的方法验证。

评分前独立协议审查补充：预算仅为候选数，不称等人工成本；另报告所选字符量与长度p50/p95。全gold分母含零候选回答。bootstrap仅刻画本次冻结接纳集合，非重新排序整个策略的泛化区间。
