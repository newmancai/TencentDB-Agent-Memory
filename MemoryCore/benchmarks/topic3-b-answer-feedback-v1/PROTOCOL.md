# B回答反馈：共同轨迹与待检验机制

2026-09-13，开发阶段。先产生未经B干预的完整回答历史，所有后续B方法消费同一份轨迹；不在不同回答上比较判断器。E不执行更新。

## 数据与回答

公开EvolIF，HF revision `47115ae2af4830948f3f15697221a1acca6078a7`，dialog_1的全部50轮作为已用开发数据。不是未见评估。读取器只把`user_query_verified`送入生成器，此前实际生成的assistant回答完整加入历史；`instructions/active_topic/style`不进模型。不同于之前只有用户指令流的定位实验。

固定本地Qwen3-4B-Instruct-2507，greedy，输入上限32768 token，每轮生成上限512 token。不按正确与否提前结束，也不丢弃失败轮。达到生成上限单列，不能自动归责为遗忘。达到输入上限则记录剩余不可观察轮并停止该流，不能静默裁历史。无用户反馈注入，无示例，不根据结果修改回答器。

## B边界

给定正确规则的确定性checker是强基线，不是待证明的创新。给定原始要求的违反判断只能是oracle组件能力，不能宣称发现了记忆问题。当前公开数据没有回答真值，须生成上述共同回答再执行公开checker；checker定义之外的语义质量、自然用户不满、记忆因果归责均不据此推导。

待冻结的正式机制必须说明：反馈比整体pass/fail增加了什么可用信息、学习更新什么有界状态、与同信息静态策略相比改善什么，以及该改善是否仅来自普通检查器。独立反审后再决定机制；本文件不预注册尚未确定的有利指标。

## 候选反馈适配（已实现，尚未形成B结果）

`check_candidates.py SOURCE RUN UPSTREAM`使用官方EvolIF源码commit `00be379c882c15353d43dbabe0bf91ee4152b6c8`的9类纯代码checker。独立Python环境需nltk==3.9.2；不用需要远程模型的emotion/reader_age/style，sentence长度模式因额外tokenizer资源与异常fallback排除。其余checker内部的容错仍按上游定义，不能宣称无语义误差；如CSV的一列文本可通过、bullet只数星号/横线。

每5轮产生共同回答的历史候选检查回执。候选来自此前公开构造状态中首次出现的唯一family+args，忽略topic ID；**这是oracle历史候选供给，不是自主从原文抽取**。当前有效性不进入tasks，只在labels中用当前栈匹配。first_observed_turn是构造状态首次观察轮，并非已审定的自然语言要求原句出处。相同参数规则跨话题合并，不测来源归责。候选只随此前观察增长，不引入未来规则。

独立反审建议把学习对象改为“哪些字面失败有资格成为当轮反馈”，见B_TARGET_REVIEW.md；避免在已给定当前正确规则下声称质量创新。接下来的有效性选择须面对同信息普通纠错+有效候选选择+同checker强基线。候选ID绑定只是待检验反馈形式，不预先认定优于自然语言纠错。旧要求不再适用并不等于历史记忆为假，反馈也不自动等于记忆故障。

## 可复现

### B对照冻结（开发B推理前）

**开发执行后修正记录：**原reasoned开发10点0exact、9输出截断，1完整集合错。原回执/状态保留；未进入预选eval9/10。暂停评估，执行一次全10点compact接口诊断，只将“简短解释后给集合”替换为“只输出集合”，不改变语义规则/候选/回执/512上限或标签。这是基于系统性输出预算问题的开发修正，不是未见评估、不改gold、不从解释猜结果。四臂正式评估使用何种接口须在本诊断后明确记录，旧reasoned结果不覆盖。不继续叠加个案提示。

**评估接口最终固定：compact。**开发compact无生成截断但3非法，集合0/10、TP13/FP79/FN5；32,648输入/752输出、28.13秒。不能称语义成功，说明适用性识别仍弱。新9/10四臂均使用compact及compact-fit首次2错状态，不使用旧reasoned状态，控制相同格式；不对评估结果再改prompt。原开发两版成本和回执都保留。仍检验可靠反馈是否能修复此弱点，而不因低baseline自动宣称反馈有效。

feedback.py仅消费通用tasks/labels接口，不读取EvolIF schema。开发dialog1固定10检查点跑direct；取最早2个完整集合错误（含unknown）的检查点形成有界反馈状态，不按错误类别挑例。每例包含完整可见用户历史、共同回答、历史候选及checker结果，标签只给各失败候选是否可当轮报告，不虚构支持原句。开发direct不消费本轮刚形成的示例，避免开发指标混入自教。

评估预选固定版本下一两个未用文件dialog9/10，每个完整50轮共同回答，20检查点。四臂direct、相同无标签实例、普通纠错prose、候选绑定structured，均同模型/同原文/同回执/512输出与32768输入上限；轮换顺序。prose与structured严格传递相同候选级真值，格式不同，实例数/顺序相同，实际token单报。主比较structured对prose，其次带反馈对unlabelled；不把比direct多给信息的收益全归于格式。

主指标完整告警集合exact、TP/FP/FN、unknown和成本，截断回答分层。B输出截断或集合非法为unknown，所有漏报计FN；不能以少告警即更高置信。两评估对话仅组件迁移证据。当前有效候选+同checker为oracle上界；全部失败均报告为弱下界。反馈学习只改变上限2例的状态，不执行E动作。prose/structured共同使用有效性选择+同checker强基线，若无增益不在这20点更改模板追分。

独立代码审查后、B推理前修正评分：当前有效规则若checker不可观察，该题不能记完整exact；可观察子集exact另报，oracle也扣除此类题。区分input_limit/output_limit/unknown_or_invalid。反馈实例记录选中时的原错误类型（仅审计，不额外送入任一臂）。不同反馈长度若造成输入超限，差值包含表示成本/可执行率，不能全算语义理解。源码内部吞异常仍按固定实现判定，不称无噪声真值。见CODE_REVIEW.md。

`python trajectory.py prepare SOURCE OUTPUT`后，以有torch/transformers环境执行`python trajectory.py generate OUTPUT LOCAL_MODEL`。prepare输出只含可见用户消息；标签留在公开原始文件供离线评估，不复制到生成输入。所有模型调用、输出截断、实际token与生成耗时逐轮留存。生成结束不等于B实验通过。

评估prepare追加dialog数字。完成checker后，`python feedback.py fit RUN MODEL`生成开发预测及feedback-state；评估`python feedback.py eval RUN MODEL FIT/feedback-state.json`不加载当前labels。`python feedback.py score RUN fit-predictions.jsonl`（或eval-predictions.jsonl）离线评分。

最终正式评估命令使用`eval_compact`和compact-fit反馈状态。两个评估及各自score完成后，`python aggregate.py DEVELOPMENT OUTPUT_JSON EVAL9 EVAL10`合并全部任务，保留逐对话指标、四臂实际成本、生成p50/p95与结构化对普通纠错的配对变化。模型总成本包含50开发回答、两版各10开发判断、100评估回答、80评估判断，预期250调用；中途失败/额外尝试须另行补报，不能凭预期数假定完成。候选增减诊断仅在两臂都可解析时统计，全部任务主指标仍保留unknown。临时小型合同检查已验证成本合并、完整覆盖、配对及分位数，不当作真实评估结果。
