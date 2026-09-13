# 可核验证据归属反馈 v1

运行前固定：LoCoMo排除上一200 QA，类别1/2/4/5各按SHA256(attribution-feedback-v1:+sample_id:+index)选6题，共24开发题。仅精确引用可解析；使用被引用完整session，原speaker/date/消息字段保留。十会话已有历史暴露，不称独立泛化。QA候选/链接为oracle；此实验测给定对象下的反馈，不称自主发现。

同一Qwen3-4B-Instruct-2507，两臂同证据、相同JSON输出合同与256新token上限，greedy；按题交替臂顺序。direct普通支持审核，attribution要求先核对引用陈述属于谁/哪个事件，再核对它能否支持问题下候选。双方都允许普通相对时间推断，并区分不足与冲突；不把问句当证据。无示例/训练，无特殊样例规则。

输出{relation:supported|insufficient|conflict,evidence_ids:[合法消息ID],explanation:字符串}。JSON必须完整，代码围栏可剥单层；不从推理正文捞JSON，不修坏引用。输出截断/非法字段/重复或未知引用使整条unknown。合法JSON/引用是结构完整性，不是高置信。无E/持久动作。

输入>4096 Qwen token整条unknown，完整session不裁剪。报告覆盖、QA代理二元支持一致性、冲突/不足分布、合法引用率、原始解释、实际输入/输出token与时间。QA代理不是packet标签，三类语义需独立审读，不将合法引用当推理正确。两臂共同covered配对；不以大量unknown包装收益。

新对照目的在于明确证据归属反馈是否比普通审核更可核验，不保证最终QA或E更好。不得依据24题改prompt或为得到正结果改gold；若仅输出结构变化，不能称质量/学习收益。下一是否学习须由实际反馈质量与成本决定。
