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

`python trajectory.py prepare SOURCE OUTPUT`后，以有torch/transformers环境执行`python trajectory.py generate OUTPUT LOCAL_MODEL`。prepare输出只含可见用户消息；标签留在公开原始文件供离线评估，不复制到生成输入。所有模型调用、输出截断、实际token与生成耗时逐轮留存。生成结束不等于B实验通过。
