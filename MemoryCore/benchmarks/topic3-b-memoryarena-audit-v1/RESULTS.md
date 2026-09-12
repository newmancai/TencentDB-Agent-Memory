# MemoryArena：B 反馈来源合同审计

本轮校正最近检索优化逐渐替代 B 的偏移。完成公开文件可用性、源码反馈路径和三个纯函数/合同探针；**没有运行 Agent、模型、MemoryCore 或任务评分，没有新增质量收益结论**。旅行路径另由独立 agent 阅读交叉检查。

## 来源与可复现边界

[官方仓库](https://github.com/ZexueHe/MemoryArena/tree/6cd9de14b71915e39ac742a20dc33785e14b6aab)、[官方数据](https://huggingface.co/datasets/ZexueHe/memoryarena/tree/da1a37c8b19280e18627ca01cf368195a5e1d92e)、[论文](https://arxiv.org/abs/2602.16313)。以实际下载文件和代码为准，不以论文效果代替本项目验证。

固定仓库 commit `6cd9de14b71915e39ac742a20dc33785e14b6aab`，数据 revision `da1a37c8b19280e18627ca01cf368195a5e1d92e`。五个配置共 701 序列、4850 子任务：shopping 150/900，math 40/354，phys 20/86，travel 270/1869，search 221/1641。问题/答案数量全部对应。哈希及范围见 [结构化输出](audit-results.json)。本轮只检查数据结构和数量，未阅读具体题目答案；不因此宣称整个来源从未被历史研究接触。官方任务序列也不能直接称自然用户长对话。

复现：将官方仓库切到上述 commit，将五个配置的 `data.jsonl` 按 `<data>/<config>/data.jsonl` 下载到上述 revision，然后运行：

```bash
python audit.py --source <checkout> --data <data> --output audit-results.json
```

脚本执行固定源码中抽取的纯函数/返回表达式，不启动环境。三个探针通过是缺陷复现通过，不是 benchmark 通过；两个字符串例子仅为 smoke，不能推导数据集错误率。

## 实际反馈能证明什么

| 路径 | Agent 可见信息 | 可支持的反馈 | 不可直接支持的结论 |
| --- | --- | --- | --- |
| travel 搜索工具 | 当前参数与数据库返回；`agent/travel_planner.py` 将工具结果追加到消息 | 调用失败、此次查询无返回、返回记录含某字段 | 现实中不存在该对象；历史记忆导致任务失败 |
| travel `hint` | 从参考方案生成的人员/日期/槽位提示 | 该槽位未通过当前参考匹配器 | 独立语义违约真值、自然用户纠正、记忆故障根因 |
| travel `answer` | 完整参考方案 | 受控答案揭示 | 零显式反馈发现能力 |
| math/phys judge | 参考答案条件下的 LLM 判断 | 该模型裁判的受控评价 | 符号证明、独立可靠事实真值 |

Travel 的环境默认 `none`，直接 CLI 默认 `hint`，必须记录实际配置。`reset()` 把完整 `answers` 返回宿主，默认 runner 在生成完成后才用于评分；未来 B 适配层只能白名单放行当前任务、工具回执、回答和已经揭示的反馈，不能转发整个 reset 返回体。基础人物方案属于允许初始上下文。

## 两项已复现的合同问题

1. `travel_env.py:18` 与 `travel_planner_env/eval.py:12` 均先按较短字符串截断，再计算相似度。`A`/`Airport Hotel` 及 `Airport Hotel`/`Airport Hotel CLOSED` 均得 1.0。另有 hint 0.9 与 reward/eval 0.7 阈值差异；环境检查含 `current_city` 的七槽，最终评估六槽。参考方案相对基础方案的不同也不等于独立验证任务约束。不能直接拿 hint 当 B 的语义金标准。
2. `run_math.py:185` 检查顶层 `result.get('judge_result')`，而 `env_client.py` 返回的 judge 位于 `observation`。抽取官方返回表达式和分支条件，在 flag=true、nested judge 存在时仍为 false。`agent/math.py` 仅在 reward 非空时添加 Judge 文本，未直接复制嵌套判断。这个静态合同说明当前开启方式存在接线问题；没有运行服务，不声称所有运行配置都受同一影响。

## 决策、知识沉淀与下一假设

**关闭“现成 hint/judge 可直接充当高置信 B 真值”的假设，不关闭 MemoryArena。** 暂不启动完整 Agent 套件：那会先消耗环境和 E 成本，却没有解决监督是否对应研究问题。

累计失败提示我们拆开三件事：观察是否可靠、观察支持多强的断言、该断言是否值得改变后续策略。回答错误、用户不满意和参考匹配失败，都不足以单独证明记忆故障。下一可检验假设是：B 学习的是局部反馈的适用范围和可采取的动作，而非强制输出统一的“记忆错了”标签。例如“同一参数此次无结果”可支持一次改变查询，但不能支持永久删除记忆。

最小后续入口：优先审查真实工具回执可独立核验、具有后续重复决策的任务；若使用受控提示，应单列提示质量并与同反馈普通利用比较。B 主指标为有证据反馈的覆盖、越界断言率、后续选择错误与取证成本；学习前后必须有可测状态变化。最终任务分数是辅助，E 只执行已有有界动作。

重新开启本来源需满足：先按序列隔离开发/验证；明确允许揭示的反馈；对参考匹配以外的局部真值制定可复查协议；固定同信息普通反馈利用基线。若修复上游 checker，必须升协议并重跑共同基线，不以修后的分数与旧分数直接比较。shopping/search 本轮仅做 schema 审计，尚未审其反馈语义，不能外推旅行/数学结论。
