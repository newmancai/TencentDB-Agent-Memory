# 普通联合审核：无净提升，错误互补仍待学习验证

2026-09-13。为上一可见speaker比较补同信息强基线，保留原30配对/60端，全路径共同覆盖58端，2端长度unknown。原context与answer逐条实核不变，只追加可见speaker生成的替代问题，并明确其为假设而非证据。普通ABC系统prompt/模型不变，新增联合一次forward；不训练、不给gold或正确对照问题。

|方法|TP|FP|FN|TN|正确端数|
|---|---:|---:|---:|---:|---:|
|原单端|24|0|5|29|53/58|
|原+替代分数OR|26|1|3|28|54/58|
|普通联合|24|0|5|29|53/58|

联合相对原4胜4负50平；相对比较4胜5负49平。因此不能因为联合与原混淆矩阵相同就声称逐题等价，也不能把联合当成比较规则的低成本无损替代。共同covered已核对，不是改变分母的结果；旧两个方法回执未重跑。

新增58forward、120528token、18.086秒，仅forward。原单端历史58forward118821token17.914秒；原+替代逻辑上另有58替代评分，成本见SPEAKER_RESULTS，含部分可复用输入，不能称完全独立116次真实新调用。联合一次forward输入稍长，与比较具有相同信息，但不是精确等计算预算。72806 exit0，自有模型退出，无E/MemoryCore/production。

## 路线判断

不采用当前普通联合配置为新默认，不在30对改输入布局追分。保留它作为同候选普通审核强参照，避免未来把额外候选或两次模型调用的收益全算B创新。

相同总分下存在逐题互补：如果事后读取gold选择原/联合，最多57/58；读取gold选择比较/联合，最多58/58。**这是不可部署的标签选择上界，不是现成策略，更不是学习收益。** 它只说明当前总分没有穷尽可修复实例，不能据此断言可以从输入预测哪条路正确。

下一有界学习问题应明确定为：先前受控核验反馈能否帮助选择审核方式，或者在固定成本下选择是否执行替代比较。必须在训练/验证分离、当前输入可得特征、同信息/成本静态参照下验证；不能用当前题gold选择路由或根据本30对失败设计特例。如果可观测特征无法预测互补，或学习成本超过收益，则关闭该选择路线。这里保留新的可检验问题，不否定关系信号，也不继续仅换提示词。

本轮仍是历史复用LoCoMo开发探针；oracle候选答案/引用session还在，QA代理标签不是独立packet真值。未满足B自优化、独立方法验证或最终PR验收。

## 复跑

```bash
python joint_probe.py prepare --previous PAIR_RUN --candidates SPEAKER_RUN --model QWEN_MODEL --out RUN
CUDA_VISIBLE_DEVICES=0 python semantic_probe.py infer --tasks RUN/tasks.jsonl --model QWEN_MODEL --allowed RUN/allowed.json --out RUN/predictions.jsonl
python joint_probe.py score --previous PAIR_RUN --candidates SPEAKER_RUN --run RUN --out SCORED
```

发布原始logits/限制名单、共同队列逐例结果和明确标记的离线标签选择上界。60条输入逐条检查仅追加生成替代，未追加标签或oracle正题；prepare需tokenizer，score只需标准库。goal active。
