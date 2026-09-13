# LettuceDetect v1 固定 detector 合同

只读代码/metadata；未加载模型或运行推理。代码 checkout 为 `2096ed28f3b662a62b4406795da3d6fbc5490063`，本地 `lettucedetect/`；下载模型元数据为 `KRLabsOrg/lettucedect-base-modernbert-en-v1` revision `bbd77832f52f9bd87546a3924c032467921f5c34`，本地 `model-api.json`、`model/config.json`。

## 模型身份与训练来源

[模型卡](https://huggingface.co/KRLabsOrg/lettucedect-base-modernbert-en-v1)的 metadata 指向 `answerdotai/ModernBERT-base`，但正文两处写 Large、性能段也讲 large，存在卡片复用错误。实际本地 config 为 `ModernBertForTokenClassification`，22 层、hidden_size 768、12 attention heads、max_position_embeddings 8192，符合 base 配置，不能将 large 的 79.22% 当该权重成绩。config 无显式语义 id2label；标签 0/1 的 supported/hallucination 解释来自训练/推理代码，不是模型卡推断。

卡片明确训练数据是 RAGTruth。因此本项目从官方 train 取开发校准，仅能称已训练来源上的开发复用；不能称 detector 从未见过的任务。官方 test 可作为既定 benchmark 测试，但仅靠模型卡不能逐条证明所下载权重训练成员及版本，也不能把该测试升级成新来源泛化。当前 checkout 的预处理代码不必然等于当初生成该权重的数据脚本。需保留模型/代码 revision 与这一未知，不额外扩大数据审计。

## 应复用的路径与函数

1. `lettucedetect/datasets/hallucination_dataset.py::HallucinationDataset.prepare_tokenized_input`：使用 tokenizer 的 `(context, answer)` 双序列格式，不拼成 chat。`add_special_tokens=True`、`truncation='only_first'`；预期布局为 CLS/context/SEP/answer/SEP。`answer_start_token = total_seq_len - independently_tokenized_answer_count - 1`，取得 offsets 后将其从模型输入移除。上下文可截断，回答不可在该模式下默默裁剪；过长回答仍可能报错。默认 API 长度是 4096，模型 config 支持 8192不意味着调用默认8192。
2. `lettucedetect/detectors/transformer.py::TransformerDetector.predict_prompt` / `_predict_single`：直接传官方 `source['prompt']` 与原回答，最接近 v1 RAGTruth preprocess；无 taxonomy_head，不用 v2 cascade。不要改用 `predict(context, question)` 后宣称输入相同，后者会通过 `PromptUtils.format_context` 重新组 QA/Summary 模板并自动分块。
3. 缓存分数时复用上述编码，保存 answer-region offsets 与 `softmax(logits)[...,1]`。只将 answer region 且 `end > start` 的真实文本 token 用于 response aggregation/定位；末尾 SEP 的零长度 offset 必须排除。tokens API 当前从 answer_start 一直到序列末尾，包含 SEP；直接对 tokens API 全列表求 max，会让无文本特殊 token 触发回答告警。

双序列 offset 对回答本来是回答内坐标；官方 span 构造又减去首 answer token 的 start。若首 start 非零（某 tokenizer 跳过前导空白），该平移会相对未修改原文错位；适配需保留原坐标并核对原文切片，不能把通过此函数就视作定位已证明。当前代码尚未针对本次真实输入运行，不能预先声称出现了该问题。

## 默认判定与 aggregation

单块 `_predict_single` 以二类 argmax 判 token，等价于 hallucination 概率大于 .5（恰相等时 argmax 选类别0）。连续 hallucinated tokens 合并 span，span confidence 取其中最大概率；它不是 span 正确率。`min_confidence` 默认 .0，仅过滤已有 spans，对 token 输出不起作用，不是把 token 阈值设为0。

`_predict_chunked` 对不同 context chunks 的同位置 token 取 **max hallucination probability**，并以 `>= .5` 判正。这要求每块都支持才可能不告警；一个只在某块有依据的正常断言也可能被其他块判无据。故不能把这种结果解释为对完整来源集合的 grounding 判断，也不能在本轮无记录地切到该路径。`predict_prompt` 不分块，超限只警告并裁剪 context；本轮宜事前按真实 token 数记录覆盖，对超限给 unknown，不把裁掉支持的结果当官方完整证据评分。宿主若定义 response score=max真实answer token概率，应明确是宿主聚合，不是 span confidence 的质量概率。

## 与 RAGTruth 官方 preprocess 的差异

本 checkout `lettucedetect/preprocess/preprocess_ragtruth.py::create_sample` 原样使用 source.prompt/response，并复制所有 gold span 的 start/end/label_type；`implicit_true` 和 `due_to_null` 没有被过滤，metadata 本身未带入转换后的 sample。其 `main` 遍历所有 responses，**不按 quality 筛选**。

相比之下，[RAGTruth 固定 prepare_dataset.py L34–40](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/baseline/prepare_dataset.py#L34)只保留 quality=good；对 implicit_true/due_to_null 同样不删除。因此本轮官方 test 基线应自己固定 good-only 队列并报告其余覆盖，保留原特殊 metadata 做离线切片。不能把 LettuceDetect 转换文件丢掉 metadata 误读为这些 span 被排除，或把 quality 未筛的数据与官方成绩混报。

本轮可交付对象是固定预训练的回答 grounding detector 及有限监督校准，标签仍相对给定来源。它既不证明事实真假，也不证明 MemoryCore 检索失败、长对话反馈发现或自优化收益；这些边界不因采用专用预训练模型而消失。
