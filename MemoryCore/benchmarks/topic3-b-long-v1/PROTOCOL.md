# 长对话原生候选覆盖与冻结关系诊断

2026-09-13，运行前固定。使用既有v7的60个LongMemEval开发任务，其中54有既定参考old/later对，6无参考对单独记not_applicable；不根据本轮输出删样本。所有LME oracle题历史已用，不称未见泛化。incoming时点此前由has_answer辅助选择，是受控检查点，不是自然告警率采样；本轮候选池和查询不得使用gold或old ID。

原生MemoryCore L0写入incoming之前全部用户消息，保留原文和来源ID，按公开日期及对话次序排列；不含当前消息、未来、assistant、QA问题/答案或has_answer元数据。使用开源FTS conversation-search top8，查询就是incoming原文；对照为同一已写入池的最近8条。两臂相同候选条数上限。FTS基座不改、不增加向量索引；此为L0用户历史配置，不冒称完整混合检索或L1抽取。

先报告54个参考旧对象在两候选池中的触达，及按已有两版assistant银标分层的触达。参考对象不代表全部有价值记忆。既有144个目标span不自动扩展成所有检索对象的gold。

随后冻结RoBERTa-MNLI rev2a8f12d和阈值0.5/0.7，不学习新阈值。对实际候选旧原文/当前原文评分，额外单独计算参考old的oracle关系诊断，只作区分候选与模型损失，不能混入检索池或当线上成本省略。512token上限，禁止截断，过长unknown。输入不含日期改写、模型生成命题或标签。分数含义是文本矛盾倾向，不是旧记忆确定过时；时间更新与逻辑矛盾不等价。

指标：reference recall@8、known-target银标changed/same/unknown上的告警分布、conditional target触发、其他无标签告警数、超限、写入数、查询延迟、NLI全输入与成本。其他未标注告警不能直接算FP。若此证据不足以证明高置信，将如实说明，不把候选触达当最终反馈precision。E无新动作；任务失败回退/生产验收继续沿用既有实现边界，不由研究实验代替。
