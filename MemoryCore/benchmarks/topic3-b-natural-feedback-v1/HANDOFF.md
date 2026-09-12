# 恢复入口

## 最新：PersonaMem合同已核验，真实原话诊断已准备

`PERSONA_FEEDBACK_CONTRACT.md`/`results/persona-contract.json`：v1全部20persona历史已暴露；v2实际5000题/200persona，无实际动作/概率/针对本系统回答的后续反馈字段，不能直接迁移自然SDPO。可做新受控实验但须有直接reward强基线，不能用gold生成句子后绕模型包装额外信息。本轮无模型。

下一按`RAW_SIGNAL_PROTOCOL.md`做原话信号能力诊断。`prepare_raw_signal.py`已实际生成`.local-evidence/topic3-b-natural-feedback-v1/raw-signal/tasks.jsonl`，LMSYS226/73，只有最后用户请求+实际历史回答+后续，与缓存语义同三条正文；无标签/WildChat。控制为不同会话一对一长度匹配，226独特donor、0同会话；不是反事实真反馈。先核对官方SDPO模板与teacher-forcing边界，固定token上限，再三路forward和排序比较；尚未实现打分或新学习，无进程待等。不把此开发组件代替长对话主验收，E不扩。

## 最新：开发盲审及上层路线审核已完成

`IDENTIFIABILITY_AUDIT.md`/`results/identifiability-audit.json`为本轮结果：按既定规则4事件/3会话，独立agent局部盲审再看全历史，主判断均未改变；3与作者标签一致，1为重述/纠正遗漏定义歧义。不是四例噪声率，更不是全历史模型干预结果。选择/输入重建一致。下方四例下一步已执行，不重复审查或按其补词。

`SDPO_REVIEW.md`核验原始交互自蒸馏论文及官方代码3b17d2a：后续原话可形成分布对照，无需先六分类；但token advantage不能直接移植为记忆动作reward。固定日志缺动作概率/反事实，不能重放同一用户反馈给另一个候选回答。停止当前六分类+校准主线；保留作为基线与负结果，不扩E或重训整LLM。

下一具体工作是核验公开长对话能否提供有界记忆消费动作→实际回答→针对该回答的受控反馈，并明确后续保留任务。可先检查已有PersonaMem来源/适配与历史暴露，不能默认复用已测18persona/36题当新泛化。若数据不支持，不启动模型，不以合成偏好smoke作为唯一主评测。新路线必须比较普通同信息ICL、后见单路评分、差分评分和匹配打乱反馈；此方案尚未实现/验证。

本轮没有模型实验、运行时变更、GPU/production/远端PR操作，goal active。

本轮全部结束，goal继续active。先读RESULTS.md/PROTOCOL.md；原始数据仍在`.local-evidence/topic3-b-feedback-audit/adapted`，本轮本地证据`.local-evidence/topic3-b-natural-feedback-v1`。模型/分类头仅本地；可公开的ID级预测及原始分数在results。

四类核心证据：TF-IDF建立廉价参照但差；语义预训练能力显著强于该参照；受控标签六维学习分类增益小且区间跨零；简单温度已取得大部分Brier下降。不要把校准有效泛化成高置信反馈发现，更不要把用户意见直接写成记忆故障。

session77206/65335/46025均exit0；431模型forward完成，无待运行任务，不重复启动。CPU原始JSONL读取失败发生在训练前，已修复物理行读取；无样本删除。保存头重载和输入/分数复核通过。他人GPU PID2042761保留。

下一只做开发源可识别性诊断：固定按LMSYS源顺序取每个NEG类别首次模型错例（冻结六分数可重算），先给独立审查者原局部输入、不暴露gold，记录其判断/可引用证据，再看完整历史与作者标签，区分上下文缺口、类型边界歧义和模型错误。少量诊断不是重标gold/准确率评估；不得据此改WildChat预测。目的是判断反馈单位是否应变化，不是再做一轮提示词选优。不要默认扩到E或直接启动更多模型。

远端PR#2仍未推送本轮；本地研究代码不是已发布PR，也没有完成公开长编程/商用验收。运行时未改，旧native合同测试不重跑。
