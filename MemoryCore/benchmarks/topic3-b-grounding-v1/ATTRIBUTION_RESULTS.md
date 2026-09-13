# 引用归属反馈生成：解释局部改善，未形成判定收益

2026-09-13。排除上一200 QA（含已审8例），新24开发QA、各类1/2/4/5各6，仍来自已复用十会话，不称未见泛化。两臂同证据、同Qwen、greedy/256输出上限；普通审核与先核对归属再审核都输出relation/evidence_ids/explanation。无学习、E或MemoryCore写入。

## 实际结果

|模式|全量|可评|TP/FP/FN/TN|BA（自身covered）|有引用的合法输出|
|---|---:|---:|---|---:|---:|
|direct|24|15|1/1/3/10|57.95%|15|
|attribution|24|15|1/1/3/10|57.95%|15|

两臂有效集合不完全相同，共同14题全部二元判定持平；0胜0负14平10至少一侧unknown。不得拿各自15条作为完全相同的比较分母。QA仍只是相对全历史的代理标签，不是独立packet gold。与此前200题ABC单forward分母/输出合同不同，不直接比较BA宣称退步或改善。

各臂6input_limit；direct2invalid_output+1触及256上限，attribution3invalid_output。共36实际生成，输入75876token、输出4078token、116.658秒：direct37677/2114/60.301s，attribution38199/1964/56.356s。生成时间包含prefill/解码、不含加载等，不能与旧单forward时间直接比。97928 exit0，自有模型退出，仅保留他人GPU。未重新推理/放宽解析。

结构失效有具体依据：模型把问题ID conv-* 当成消息引用，或拼接问题ID和时间戳作为来源；不是引用与gold不匹配才被排除。触及上限样例在JSON后继续自我纠正又开新JSON，旧relation和后续推理不一致，保留整条unknown。实现对恰好第256token结束也保守拒绝，因此“output_limit”仅保证触及上限，不一律证明被截断。

## 匿名解释审读

在24题按独立固定hash抽4题，A/B映射按IDhash隐藏。独立agent只看packet和匿名输出，不看标签/映射/统计，结果为归属臂解释较好1、平2、不可评1。这是助手审读，不是总体质量估计或新官方gold；不替换主结果。

- conv-43:194：归属臂解释发现Tim动机不能直接支持John动机；direct仍把Tim的原话归给John。但归属臂relation=supported与解释末尾insufficient冲突，且忽略John愿意同行的D7:7，不能直接消费。只证明输出中出现了有用辨别信息，不是正确反馈已经交付。
- conv-47:90：两侧相同，D10:10支持慈善款用于狗收容所。
- conv-42:16：两侧同样可由D7:1/D7:3及所给caption支持紫色染发；没有实际看图，不能称图像验证。
- conv-43:13：两侧输入超限无输出，不能当解释质量tie。

合法引用仅说明ID真实存在，不能证明该消息支持目标关系；本例的relation/解释矛盾即使JSON合法也会漏过结构校验。不能用扫描解释末尾或人工改写relation把这次算成功。

## 路线决定

不采用当前归属提示为新增默认，不据24题修prompt/加token/改解析追分。给相同普通审核加入归属提醒尚无可消费判定收益；未证明所有证据归属方法达到上限。

本次观察把更具体的缺口暴露出来：模型在解释中偶尔能发现错归属，但不能稳定把证据、目标和最终判定保持一致。下一若继续，应研究明确的证据绑定对象与独立核验，使反馈建立在可定位的关系上，而非再加一句“仔细考虑”或从自由解释里抢救答案；必须保留当前同预算普通生成强基线。结构性重设计也不自动等于自优化，仍需先前经核验反馈带来的独立收益。

当前代码是可复跑的研究生成器及验证器，尚非运行时高置信模块。原题公开长对话独立验收、B反馈学习收益与可交付PR全部要求仍未达成，goal active，E不扩展。

## 复跑

```bash
python attribution_probe.py prepare --source LOCOMO_JSON --previous QUESTION_RUN --out RUN
CUDA_VISIBLE_DEVICES=0 python attribution_probe.py infer --tasks RUN/tasks.jsonl --model QWEN_MODEL --out RUN/predictions.jsonl
python score_attribution_probe.py --run RUN --out RUN/summary.json
python prepare_attribution_review.py --run RUN --out RUN/review
```

prepare/score/review只需标准库；模型沿用torch2.5.1、transformers4.57.6、BF16/SDPA。发布labels、原始输出、汇总和匿名审核映射/判断，完整会话正文仅存本地。独立代码审查确认同信息、输出上限/顺序、无gold输入；指出空引用允许与触上限解释边界，已分开报告实际有引用输出。
