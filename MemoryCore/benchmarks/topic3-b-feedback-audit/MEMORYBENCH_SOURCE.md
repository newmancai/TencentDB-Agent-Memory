# MemoryBench 来源有界审查

2026-09-13。结论：**值得作为受控反馈驱动学习参照接入，不能作为自然真人反馈或记忆故障归责真值。** 已核验实际小数据文件和代码，不仅依据首页。当前不启动全 benchmark、模型或 E。

## 来源身份和版本

- 首页 https://memorybench.thuir.cn/ 的 HTML 元信息指向 https://github.com/THUIR/MemoryBench 。
- 官方论文 https://arxiv.org/abs/2510.17281v7 ，标题 *MemoryBench: A Benchmark for Memory and Continual Learning in LLM Systems*，v7 日期 2026-06-03；论文页面直接链接上述站点、代码和 HF 数据。
- 本次官方代码 main commit：`2d68f2b9e860cbcd42c2b9f24986b037ff175818`。
- 官方数据 https://huggingface.co/datasets/THUIR/MemoryBench ，本次 revision：`3acd60a4bd35b43b408f0e6db4c5f1e88df5e96d`。
- 目录 API 实读：https://huggingface.co/api/datasets/THUIR/MemoryBench/tree/main?recursive=true&limit=1000 。有 LoCoMo-0..9、DialSim-friends/bigbang/theoffice 等子集和独立 corpus 文件。
- README 另指向完整复现 https://github.com/LittleDinoC/MemoryBench-code 、扩展数据 https://huggingface.co/datasets/THUIR/MemoryBench-Full 。这两个扩展入口本次未下载或核查实际内容，不据其宣称覆盖。

## 实际读取的原始小文件

固定 revision 的数据基址：
`https://huggingface.co/datasets/THUIR/MemoryBench/resolve/3acd60a4bd35b43b408f0e6db4c5f1e88df5e96d/`

| 相对路径 | 实际字节 | 实际内容 |
|---|---:|---|
| `dataset/Locomo-0/train/data-00000-of-00001.arrow` | 1,534,496 | 20 QA记录 |
| `dataset/Locomo-0/test/data-00000-of-00001.arrow` | 283,528 | 5 QA记录 |
| `corpus/Locomo-0.jsonl` | 109,417 | 1行，内含19 session、419 utterance |

已在内存用现有 pyarrow 读取，没有下载模型或创建数据副本。metadata也已读：
https://huggingface.co/datasets/THUIR/MemoryBench/raw/main/dataset/Locomo-0/train/dataset_info.json

实际 Arrow 核心字段：`test_idx:int64`, `input_prompt:string`, `dataset_name:string`, `lang:string`, `info:string`, `origin_question:string`。另有成对字符串字段 `dialog_{baseline}` / `implicit_feedback_{baseline}`，baseline 包括 `bm25_dialog, mem0, a_mem, memoryos, embedder, bm25, embedder_dialog, autoskill_with_library_dialog, autoskill_without_library_dialog`。

字符串内容有 Python literal 和 JSON 两种格式，不能只靠 JSON 或只靠 literal_eval；官方 `src/dataset/utils.py` 也按 literal_eval→JSON 处理。实际解析得到：

```text
info = {golden_answer, category, evidence: [{speaker, dia_id, text, ...}]}
dialog_bm25_dialog = [{role: user|assistant, content: string}, ...]
implicit_feedback_bm25_dialog = [{round: int, implicit_action: like|dislike, terminated: bool}, ...]
```

以上 `like|dislike` 是本次单子集单baseline实测，不是所有来源枚举；代码另外允许 copy/none。corpus外层为 `{text: string}`，text解析成 `{conversation: {...}}`，含 `speaker_a/b`、`session_N_date_time`、`session_N:[{speaker,dia_id,text,...}]`。少数消息还有图片相关字段，不需要下载图片才能保留文本ID。

这证明有长多轮跨session正文及可定位的 **QA支持证据**，但 evidence 并不直接标注“哪个记忆对象失效/哪个检索导致错误”。本次未验证所有25条证据与corpus的精确覆盖，未把QA gold当runtime输入。

## 反馈来源：可控奖励，不是自然反馈

已读固定代码：
https://github.com/THUIR/MemoryBench/blob/2d68f2b9e860cbcd42c2b9f24986b037ff175818/src/agent/feedback.py

`get_feedback` 将LoCoMo/DialSim分派到dataset-based分支。LoCoMo以QA `f1 > 0.5` 返回like并结束，否则dislike及固定重试语句；DialSim以accuracy作对应判断。其他任务可走LLM user simulator；其 `reasoning/implicit_action/behavior/response` 是生成输出，不是人工标注。

实际LoCoMo-0训练集BM25-dialog的20条日志：4条有2条消息，16条有6条消息；反馈分别4条含1回执、16条含2回执。36个反馈中4 like、32 dislike。多轮负反馈文本确实为固定请求再答；6条消息的样本只有前两次assistant回答后的两条反馈，第三次assistant回答后没有终末反馈字段。因此不能把“达到三轮”当成成功或已确认失败，更不能补造terminal反馈。

HF README仍描述旧 `dialog/implicit_feedback` 和Qwen simulator格式，当前LoCoMo Arrow为baseline专属字段。当前默认代码、README叙述和具体发布文件应分开记录；没有证明每个历史发布文件都由当前commit生成。

## 是否能支持反馈驱动策略学习

**能支持有界受控实验。** 可固定一种baseline的同一套训练日志和用户可见反馈，比较无反馈、去反馈但保留同样正文、带反馈的B策略更新；在后续保留QA上冻结测收益。QA支持证据可以离线核验候选来源，gold答案不能直接暴露给B。用户已允许受控反馈，所以gold派生reward本身不是拒绝此来源的理由。

**尚不能直接称跨基础会话泛化。** 实读的Locomo-0 train/test只是同一19-session corpus上的20/5个QA，非彼此独立的基础会话。欲测跨会话策略迁移，应另按Locomo-X corpus或其他来源身份划分训练/保留，并扣除项目历史暴露的LoCoMo；不要因为新封装有新train/test字段就称新会话。DialSim系列可作为候选，但此次只核了目录及大小，未核文本分割与可定位标签。

官方 `src/off-policy.py` 读取train dialog创建memory，test仅预测；`stepwise_off-policy.py`按批增加训练日志，并装载同一corpus。这提供持续积累经验的流程，不保证其默认拆分回答本项目跨会话问题。读取来源：
https://github.com/THUIR/MemoryBench/blob/2d68f2b9e860cbcd42c2b9f24986b037ff175818/src/off-policy.py
https://github.com/THUIR/MemoryBench/blob/2d68f2b9e860cbcd42c2b9f24986b037ff175818/src/stepwise_off-policy.py

## 公平成本与最小接入建议

1. 固定同一baseline的日志给全部B臂，不能不同方法各读不同baseline生成的反馈日志后将差异归因于B。统一原始corpus写入和查询预算。
2. 明确学习对象是反馈条件化候选排序/选择等有界策略，而非直接把错误回答全部存入memory。提供相同次数、相同token预算的静态/无反馈对照；反馈采集或回放成本另报。
3. 先做一个来源身份和回执对齐的小适配合同：每条反馈对应哪个assistant回答、哪些末轮没有反馈、支持证据ID能否回指正文、训练与保留是否共享基础会话。再决定是否运行学习。无需扩建E。

实际日志没有完整token/wall/检索成本回执，不能用已发布日志推算端到端成本领先；可报告回放成本并把原采集成本列为未知，或在后续实跑时共同计量。

综合优先级：**适合作为受控反馈学习组件的候选，优于再次仅调DECODE阈值；不替代自然长对话B发现与归责验证。** 是否带来正收益仍未实验。没有要求自然反馈作为唯一合法研究来源，也没有因为反馈由gold派生就否定学习用途。

## 主线程后续实际适配

同日将上述三个固定revision文件保存到工作区`.local-evidence/topic3-b-memorybench`，由`memorybench_prepare.py`实际转换。419条原始记忆、19session、20训练/5测试问题；52个训练回答事件，36有受控反馈、16没有终末反馈，未补造标签。36反馈为4 like/32 dislike。25题共30个支持引用的原文、说话人、dia_id均精确匹配corpus。

输出memory/queries/learning-events与offline-gold/offline-evidence-audit隔离；test的发布反馈轨迹不进入learning-events，每个学习事件只有截至对应回答的前缀及当轮回执。训练/测试共享基础corpus明确标记。两个合同测试覆盖稀疏round对齐、未来与gold隔离、缺失终末回执以及重复round拒绝。

复跑：安装pyarrow后，`python memorybench_prepare.py SOURCE_DIRECTORY NEW_OUTPUT_DIRECTORY`，SOURCE内文件名为train.arrow、test.arrow、corpus.jsonl。现有解释器为工作区`.local-evidence/topic3-b-feedback-audit/venv/bin/python`。结构化适配统计见delay-results/memorybench-summary.json。此步骤没有训练策略、没有模型收益，不调用E。
