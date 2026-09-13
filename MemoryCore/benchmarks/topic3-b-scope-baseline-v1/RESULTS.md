# B Exact Scope Baseline v1 结果

8组结构化范围各运行match、conflict、missing三种上下文，共24项。确定性合取规则结果：

- match：8/8选择`include`；
- conflict：8/8选择`omit`；
- missing：8/8选择`ask`，不猜缺失条件；
- trace replay通过，24条decision/outcome均learner-ready。

代码入口为`matchMemoryScope`。它只处理精确标量predicate；旧自由文本scope明确返回
`unstructured_scope/ask`。因此在结构化范围内，确定性规则已是满分强基线，不训练scope
模型或bandit追求不存在的增量。该结果不覆盖自然语言scope抽取或复杂时间/逻辑条件。

脚本与汇总分别为[scope_baseline.ts](scope_baseline.ts)和
[results/summary.json](results/summary.json)；完整本地trace保存在
`.local-evidence/topic3-b-scope-baseline-v1/run-v1/`。
