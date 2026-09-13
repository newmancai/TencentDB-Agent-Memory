# 冻结 detector 开发基线：2026-09-13

本轮实际完成 150 个官方 train 来源、889 个 good 回答的专门 grounding 检测。**这是上游训练来源上的开发复用，不是本项目自优化收益或未见泛化。** 官方测试尚未推理；不据本轮误例调阈值或补规则。

|任务|回答数/覆盖|回答告警 precision|recall|F1|字符定位 F1|
|---|---:|---:|---:|---:|---:|
|全部|889/889|99.47%|96.42%|97.92%|92.85%|
|Data2txt|300/300|99.04%|97.63%|98.33%|87.44%|
|QA|290/290|100%|94.44%|97.14%|97.44%|
|Summary|299/299|100%|95.56%|97.73%|93.29%|

回答级 TP377、FP2、FN14、TN496；字符级 TP35705、FP3441、FN2062。字符指标按原回答字符区间并集计算，非官方 word/span F1。无超限或 unknown。全部原标注含 implicit_true / due_to_null；gold 未进入推理输入。

889 次 forward，705920 处理 token，合计 23.970 秒，单条 p50 20.497 ms、p95 53.364 ms。时间包括 forward、softmax/argmax 与结果 CPU 转移，不含加载、tokenization、文件写入及完整宿主流程，不能当端到端服务时延或与生成模型总耗时直接比较。环境 torch2.5.1、transformers4.57.6、FP32、SDPA、CUDA 单卡；无生成 token。进程 exit0，自有模型退出；保留其他用户 GPU 进程。

## 可复跑

先按 README 的来源下载与 prepare.py 生成 ADAPTED。模型固定为 `KRLabsOrg/lettucedect-base-modernbert-en-v1` revision `bbd77832f52f9bd87546a3924c032467921f5c34`，下载 config.json、tokenizer.json、tokenizer_config.json、special_tokens_map.json、model.safetensors 到 MODEL。实际为 base；不引用模型卡 Large 成绩。

```bash
python baseline.py prepare --data ADAPTED --out RUN
CUDA_VISIBLE_DEVICES=0 python baseline.py infer --tasks RUN/tasks.jsonl --model MODEL --out RUN/predictions.jsonl
python score.py --tasks RUN/tasks.jsonl --labels ADAPTED/labels.jsonl --predictions RUN/predictions.jsonl --out SCORED
```

推理依赖 torch/transformers/safetensors/tokenizers，评分依赖 numpy。输出使用独占创建，已有 predictions 不会被覆盖；不自动重试或接续不完整文件。来源合同见 [DETECTOR_CONTRACT](DETECTOR_CONTRACT.md)，预先固定的 [协议](BASELINE_PROTOCOL.md)。发布 selection、逐例字符计数/预测区间及 summary，正文数据和 token 概率留本地 `.local-evidence/topic3-b-grounding-audit/baseline/`。

独立 agent 只读复核全部889条：ID无重复，回答 offsets 合法、特殊 token 排除，独立重算回答与字符计数完全一致；未发现实质实现/评分问题。

## 结论与下一步

信号对象从整段满意度转为具体来源约束下的回答片段，已有可运行的强参照。开发集接近饱和，继续在这批题拟合接纳头无法有力检验新能力；也不能因已训练数据高分就称 B 做好了。

下一先固定官方测试全 good 队列跑同一冻结 detector，报告长度覆盖与三任务分层。该测试用于冻结基线能力刻画：上游卡未给逐记录训练清单，且看过测试后不得根据误例选择新方法再把同测试当独立验收。学习方法的选择只用 train 的来源分组划分，并另留尚未观察的评估来源/公开长对话。若只改善概率校准、收益可由普通单阈值获得，则关闭“新接纳学习”主张，保留检测器组件。

B 的最终待证命题是：先前可核验反馈能否改善后续反馈的定位、误报/覆盖成本；不要求 E 的最终 QA 每次都提高。当前尚无反馈驱动参数更新，尚未建立公开长对话的新定位标签，不能作为完整原题验收或商业交付完成。
