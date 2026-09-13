# 从局部原话转向跨请求适用性：发布数据的配对合同

本轮对固定CUPID发布数据完成252 persona/504变体对的结构核验，未生成模型输出、未更改标签或数据。目标是确定后续反馈适用性实验有哪些实际对照，而不是继续逐条摘要。

## 发布数据事实

每个persona都有consistent、contrastive、changing，且三者当前请求文字完全相同。以consistent为参照：

| 对照 | 对数 | 相同请求/当前context factor | 参考偏好及checklist相同 | 历史关系 |
| --- | ---: | ---: | ---: | --- |
| contrastive | 252 | 252 | 252 | 每对6段共同、移除2段、加入2段 |
| changing | 252 | 252 | 1 | 每对6段共同、移除2段、加入2段 |

共同段的相对顺序全部保持。contrastive加入的两段都不具有当前context factor；changing加入的两段都具有当前context factor。这是发布标注的结构关系，不等于已逐句证明所有反馈的适用性。changing中那一对参考未变必须保留，不能根据类型名强造变化，也不通过删除该对构成更好看的子集。

[结构摘要](results/pair-structure.json)、[逐对关系](results/pair-relations.jsonl)、[核验脚本](pair_audit.py)。未展示或阅读新的具体任务内容；聚合关系检查覆盖全部发布数据，因此不能声称验证侧从未做过任何标签结构检查。既有按persona划分仍不变，验证侧未用于提示/策略调参。

## 为什么不能只依赖仓库构造脚本

固定源码 `synthesis/pipeline/instances.py` 的consistent分支排除random、contrastive及changing三组，而contrastive分支排除random及changing两组。按该代码直接推断历史数量可能与当前发布的“各8段、两段置换”不符。此处以实际下载parquet为准，不把未运行的构造脚本行为当已发布集行为；也不据这种差异宣布整个数据集无效或替活动方修造数据。

[官方固定代码](https://github.com/kixlab/CUPID/blob/a8560cab293ae98be4fe260689d58bddf96b51ef/synthesis/pipeline/instances.py)与[固定发布数据](https://huggingface.co/datasets/kixlab/CUPID/tree/f6e5fdae9b31f2b400d6ceb281a6a6760cc00309)供复查。

## 能支持的后续实验，不能支持的标签

这提供了两种必要对照：面对不同语境的反馈，当前目标偏好应保持；面对同一语境的新反馈，目标偏好可能改变。只奖励一致性会让“永远不更新”取得虚假好成绩，故必须同时报告两种对照，并用实际参考关系处理例外。

这些关系可以作为**受控评估反馈**用于开发侧策略更新，但不能在推断时暴露当前context factor、隐藏偏好、实例类型、另一变体或oracle共同段集合。配对结构属于评估器，不能成为候选选择捷径。原始用户反应仍然是运行时证据，必须保留其来源。

同样，参考偏好改变不证明旧反馈已被明确撤销；相同factor也不保证其中每一句话对当前请求都相关。不能将配对关系直接下放成“这条记忆过时/那条反馈错误”的gold。指标必须区分目标内容、来源支持、必要变化与不必要变化；语义评价若靠模型/助手，需保留分歧和成本。

## 当前路线决定

后续主问题从“把每条原话概括一次”转向“反馈的条件在当前用途下是否成立”。原话＋宿主来源记录仍是强基线；不能只因模型推断更详细就算正收益。学习实验必须有真实受控反馈导致的参数或规则变化，并对冻结策略、同信息普通利用进行比较。

本轮只是把可用评估对照查清，**尚未实现该学习器或运行配对质量对照**。不重跑旧6例或16例来选择提示/预算，不将原native写读证明替代此缺口，不扩E。

复现：

```bash
python pair_audit.py --parquet CUPID/test.parquet --out PAIRS
```

同prepare.py的固定parquet和pyarrow依赖。脚本仅输出身份与结构统计，不复制任务正文。
