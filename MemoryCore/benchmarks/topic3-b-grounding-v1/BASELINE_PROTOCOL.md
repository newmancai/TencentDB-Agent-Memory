# 冻结专门检测器开发联调

首次推理前固定：模型KRLabsOrg/lettucedect-base-modernbert-en-v1，revision bbd77832f52f9bd87546a3924c032467921f5c34；代码合同参考LettuceDetect2096ed28f3b662a62b4406795da3d6fbc5490063。实际config为22层/768维base，模型卡Large字样不采信。

官方RAGTruth train中每个任务类型按SHA256(`grounding-baseline-v1:`+source_id)选择前50来源，共150，保留其全部good回答；不看标签挑例。这是已用于上游训练的数据开发联调，不称未见验证。本轮不读取测试预测、不拟合策略头。上游模型卡说明训练集RAGTruth，但没有逐记录训练manifest，不能独立证明精确训练暴露。

输入为原prompt和完整answer双序列，与v1格式相同。固定4096总token上限；不裁掉来源后继续沿用完整来源标签，超限整条unknown并报告。正常输入不裁剪、不分块、不重写prompt。offset直接以原answer为准，sequence_ids==1且end>start才是回答token，排除SEP。相邻预测1的回答token合为span；置信度取其最大值，0/1由argmax（平局0），固定基线不调门槛。记录token概率与原字符offset，后续反馈学习可复用分数，不能先看测试再选规则。

评估响应级非空P/R/F1（与官方意义相同），以及自行定义的字符集合重叠micro P/R/F1；字符指标不是官方word/span F1。unknown单列覆盖；不把unknown算干净负例，同时报告全队列阳性覆盖与未知阳性数。按三任务报告。implicit_true/due_to_null不删。成本为实际token与forward p50/p95/合计，加载等不含项明确标记。

只有基线合同和来源内能力成立后，才定义有界接纳学习与普通阈值强参照；不得把冻结上游模型的能力算本项目自优化。原题长对话与反馈驱动更新仍待完成。
