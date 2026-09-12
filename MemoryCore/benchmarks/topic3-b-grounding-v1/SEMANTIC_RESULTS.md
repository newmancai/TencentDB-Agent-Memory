# 普通语义核验强基线：组件改善，尚非高置信或学习收益

2026-09-13。沿用200个复用LoCoMo开发QA，不挑误例。新增完整引用session证据范围，共同比较冻结LettuceDetect base与Qwen3-4B-Instruct-2507单forward普通ABC核验。协议预先固定，未训练、未few-shot、未调阈值。原linked detector200条复用历史输出。

## 同证据比较

原linked包200题：detector TP5/FP56/FN45/TN94，普通语义TP37/FP42/FN13/TN108；balanced accuracy36.33%→73.00%，语义58胜12负130平。告警precision仅46.84%，不能因此称高置信。两者计算成本不同，属于同证据强基线，非等预算领先。

完整sessions范围26/200超4096，两模型共同排除，语义未额外超过自身32768上限。跨范围比较仅用四臂共同174题（不足49/支持125）：

|模型/证据|TP|FP|FN|TN|balanced accuracy|不足precision|
|---|---:|---:|---:|---:|---:|---:|
|detector/linked|5|50|44|75|35.10%|9.09%|
|detector/sessions|0|22|49|103|41.20%|0%|
|语义/linked|36|34|13|91|73.13%|51.43%|
|语义/sessions|41|37|8|88|77.04%|52.56%|

sessions同范围语义49胜23负102平。扩大证据对语义识别不足多5例，同时多3误报，正确总数127→129；不能只报balanced accuracy增加而忽略这一权衡。四臂共覆盖174/200，不把26unknown当正确或负例。完整session也未必包含全会话所需证据，QA标签仍为代理，不是人工packet判定。

## 改变下一行动的结论

普通语义核验明显比冻结token detector更适合当前受控问答关系任务，建立了必须击败的强基线；这部分能力属于所用模型/核验方式，不能归为本项目学习收益。

**不能采用“detector报错才调用语义核验”的默认级联。** sessions队列detector漏掉49/49不足，增加来源还降低了对抗告警。这样的触发门把关键问题挡在核验之外。本轮未实际部署或试验级联；这是由已观察告警集合直接推出的本队列覆盖上限，不是全场景结论。也不反向分数或在当前题拟合新概率头。

尚未解决的是反馈可信度：语义在当前oracle条件下precision约一半，可能混有packet不充分与真实误报。下一应对告警进行来源内独立证据审核，区分“支持关系成立”“可见冲突”“尚不足”，测可核验反馈的保留与误归责，而不是先把这些标签用于改记忆。B学习应针对经核验反馈后续能改善什么；必须与当前普通语义路径比较，E继续只辅助。不能用扩大context的成本换来的覆盖变化冒称学习。

## 成本、输出及边界

|实际路径|forward|处理token|forward秒|是否本轮新增|
|---|---:|---:|---:|---|
|detector linked|200|38707|3.942|否，旧缓存|
|detector sessions|174|356763|17.417|是|
|语义 linked|200|62274|11.564|是|
|语义 sessions|174|390109|58.907|是|

本轮548新增forward、809146处理token、87.887秒，不含加载/tokenization等宿主成本；无生成token。三字母仅约束选择，letter mass最小0.2634、中位0.999978，不能称自由输出100%格式成功。A支持/B冲突/C不足中B/C合并评分，细分没有独立gold，未报三类准确率。session90744/16124均exit0，未动他人GPU，无E/MemoryCore/production。

独立agent确认同范围信息、无gold输入、四臂共同集合；指出旧缓存成本和可能分母差异，已以reused字段及scope_common_arms显式处理。本轮未验证统计泛化；十会话历史已复用，源内相关性和oracle证据均保留，不称独立验收。

## 复跑

```bash
python semantic_probe.py prepare --source LOCOMO_JSON --previous QUESTION_RUN --out RUN
CUDA_VISIBLE_DEVICES=0 python baseline.py infer --tasks RUN/detector-tasks.jsonl --model DETECTOR_MODEL --out RUN/detector-predictions.jsonl
python score_semantic_probe.py allow --previous QUESTION_RUN --run RUN --out RUN/allowed.json
CUDA_VISIBLE_DEVICES=0 python semantic_probe.py infer --tasks RUN/semantic-tasks.jsonl --model QWEN_MODEL --allowed RUN/allowed.json --out RUN/semantic-predictions.jsonl
python score_semantic_probe.py score --previous QUESTION_RUN --run RUN --out SCORED
```

模型环境沿用torch2.5.1/transformers4.57.6，语义BF16/SDPA，detector FP32。QUESTION_RUN指上一question_probe结果，复用ordinary预测；prepare和score只依赖标准库。发布逐例指标、labels、allowed及语义原logits/mass，正文和新detector逐token输出留本地。
