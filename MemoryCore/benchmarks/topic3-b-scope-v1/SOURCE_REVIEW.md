# EvolIF：当前有效约束违反反馈的来源核查

2026-09-13。**可用于B的可定位约束违反信号研究，但必须由可见指令推断有效规则；不能读取隐藏结构化规则后宣称B发现。** 数据是合成多轮指令，不是自然反馈或过时事实E任务。下一步应做有界生成对照，不再泛审计。

## 已读来源与一份实际数据

- 官方仓库：https://github.com/JiaQiSJTU/EvolIF ，实际README文件为 `Readme.md`。
- 官方论文入口（README）：https://arxiv.org/abs/2511.03508v2 。本次未独立复核论文全部实验。
- 正确HF数据入口是 https://huggingface.co/datasets/KikiNLP/EvolIF 。
- 实际目录API：https://huggingface.co/api/datasets/KikiNLP/EvolIF/tree/main?recursive=true&limit=1000 ，返回153项，已见数据路径为 `dialog_v0.1/dialog_*.jsonl`。
- **唯一读取的数据文件**：https://huggingface.co/datasets/KikiNLP/EvolIF/resolve/main/dialog_v0.1/dialog_1.jsonl ，77,412 bytes，50行/turn 1..50。仅在内存读取，没有下载全集/模型。
- GitHub API本次限流，未取得源码commit。以下源码及数据为核查当时main，不冒称已固定版本；正式实验需保存实际版本。

## 实际schema和跨轮语义

每行键：`turn`, `active_topic`, `user_query_verified`, `user_query`, `instructions`, `style`, `instruction_success`, `topic_success`。

`instructions`是列表，各项 `{id,args,description}`；`style`含 `{uuid,persona,styles}`。本50行 `user_query_verified`均非空，`instruction_success`均true。**这两个success字段是构造/指令核验标记，不是模型回答遵从标签。** 文件没有 `response`、每条回答的违反标签或用户纠错结果。

实读首轮：`active_topic=3506`，可见用户要求研究性内容并用valid CSV；离线规则为 `{id:format,args:{mode:csv}}`。第三轮可见原句明确将4个bullet points改成9个，离线有效栈包含既有CSV和 `{id:countableItems,args:{num:9}}`。这提供“覆盖参数但保留其他约束”的明确观察，不是历史事实变假。

已读 `src/state.py`：每个TopicManager保存自己的instruction字典；支持add/remove/modify，remove弹出对应规则并生成撤销措辞，modify更新同规则参数，topic switching有new/backtrack。当前topic切走不等于其旧约束永远删除；正式B应区分撤销、覆盖、暂不适用。此为源码语义，未对50轮所有转换逐项人工核验。
https://github.com/JiaQiSJTU/EvolIF/blob/main/src/state.py

## 对应可执行checker和可见边界

已读 `src/eval.py`：模型生成输入为 `user_query_verified`、此前user/assistant历史，以及可选system prompt；**不把instructions结构作为模型输入**。生成后，宿主按 `instructions.id` 实例化类并直接设置 `args`，忽略description，再调用checker。
https://github.com/JiaQiSJTU/EvolIF/blob/main/src/eval.py

与首轮CSV数据对应的实际校验源码：
https://github.com/JiaQiSJTU/EvolIF/blob/main/src/instruction/format_instruction.py

`FormatInstruction.check_following`先剥整段代码围栏，再按mode分派；CSV用 `csv.reader`解析并检查行的列数一致。它不检验研究内容质量，也未要求至少两列；单行普通文本可能作为一列CSV通过。应把它当“该实现定义的格式通过”，不能等同全面语义遵从。JSON用 `json.loads`；Markdown为围栏等启发式检查，同样不是完整语法或内容质量真值。

另读 `start_with.py`确认前缀类型能纯代码执行，但不是严格字面匹配：会忽略部分空白/标点、letter模式找首个英文字母并忽略大小写。核查不代表已运行checker。
https://github.com/JiaQiSJTU/EvolIF/blob/main/src/instruction/start_with.py

不能把全部12类统称确定校验：`eval.py`的emotion、reader_age、style调用LLM judge，分数>6才算满足，异常会变失败；其他类捕获异常也变False。若测客观B反馈，最小实验只选公开实现能确定执行、且确认可见语句表达充分的规则，并把检查失败与代码异常分开。不要用运行时异常制造违反正例。

## 实际回答和金标准

本次核验的HF dialog文件只有用户指令和离线规则，没有真实回答日志。README虽描述evaluation/model/eval文件结构，但已读取的仓库根目录未见evaluation目录，未证实有可下载完整回答/标签。因此当前应按**需要新生成回答**规划，而非宣称已有真实回答结果可回放。

`eval.py`生成的结果schema为：turn、active_topic、user_query_verified、instructions、response、eval{overall_ok,details,sub_details}、remaining_patience。默认耐心3次连续失败停止；通过会重置。当前循环没有把checker错误详情送回下一轮模型，历史只追加user和assistant，故原协议不是已实现的“违反反馈学习”。主动反馈消费和学习比较需要自行构造并明确预算。

`instructions/args/active_topic`及snapshot是评价金标准或构造状态；仅可供离线核对，除非明确设为oracle能力对照。Agent/B真实输入只能是可见对话。若B提取规则产生新ID，应回指可见来源轮次和原文，再由宿主离线匹配gold约束；不能直接沿用隐藏ID掩盖定位问题。

## 最小可执行B对照建议

固定一小组完整对话并按对话分训练/保留，先只用确定checker家族。固定基础回答器与相同历史/候选，生成一次未经B处理的回答；冻结后所有B臂看同一回答。B从可见历史输出“当前有效约束来源轮次、原文、是否违反/unknown”，离线用当前gold栈和checker核验。分别测有效性追踪、违反定位、强度适当性；不把任务不满意直接变记忆故障。

若要检验学习，训练对话中给B有界、可定位的宿主反馈，冻结学习状态在保留对话测；比较无反馈、相同去标签实例、带核验标签实例，同模型同token/次数预算。若只评估固定回答上的违反预测，可离线比较B识别收益；若声称改善后续回答，须另用同一回答器/预算配对开关B信号消费，不能从违反预测正确率直接推导QA收益。E无需扩建，C不变。

换成EvolIF本身不是创新；可检验的机制是“反馈学习是否改善当前有效约束的追踪和违反定位，尤其撤销/覆盖/话题回返”，相对整体判错信号提供更具体的反馈对象。此计划尚未运行，也未承诺正收益。

本次只读小文件/源码后写本审计文档；一个超时的自有HTTP读取进程已停止，无模型或其他进程操作。
