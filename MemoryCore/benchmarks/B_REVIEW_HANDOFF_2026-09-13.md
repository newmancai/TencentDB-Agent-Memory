# B+E 复盘审阅交接

## 给接手人的一句话

请把本项目看成“**多轮编程任务中的记忆决策自优化**”，不要看成又一个长对话
RAG，也不要把 E 的 checker 通过率当成 B 已经学会。当前五项研究交付已齐，证据从
早期纯负结果推进到混合结果：Trigger 与 ValidMem 有正向方法验证，CUPID 自然反馈
利用仍为负，真正的跨任务反馈学习和 Codex/Claude Code 产品级收益尚未证明。

当前交付状态：`pass_with_mixed_method_evidence`。

审阅入口：[PR #2](https://github.com/newmancai/TencentDB-Agent-Memory/pull/2)，分支
`delivery/topic3-be-v1`。请以PR实时head为准；本交接之前的已发布基础head为
`758f58f386007932a1a11102dd25490b1274c972`。

## 1. 主线到底是什么

B负责回答四个问题：

1. 当前观察或反馈是否值得形成记忆候选；
2. 它绑定到哪个用户、项目、动作、声明和有效时间；
3. 后续任务应该`omit/include/verify/ask`哪一种；
4. 使用后是否真正减少重复失败，并且收益超过token、时延、核验和错误写入成本。

E只负责提供可追溯回执：checker、工具返回、文件状态、MCP trace、最终store和回答。
E能证明“这次调用/落盘/任务是否按合同成功”，不能单凭一次结果证明某条记忆长期
正确，也不能把用户不满自动归因给MemoryCore。

当前工程形态是旁路而非替换：

```text
事件/任务
  -> 数据适配，隔离agent-visible与evaluator-only标签
  -> 同模型baseline / enabled
  -> MemoryCore写读或冻结证据注入
  -> trace + store + answer + checker
  -> E结构化回执
  -> 在独立后续任务上判断B净收益
```

Gateway没有默认启用新策略，基座索引没有被删除或永久替换，研究用target/scope/
trace/replay主要保留在benchmark侧。

## 2. 为什么主线演化到现在这样

早期假设是“把历史反馈整理成画像、摘要、示例或规则，模型就会在未来变好”。多个
对照否定了这个简单假设：后见答案能改善本题词面检索，但不能稳定迁移；query残差
和小K reranker更新没有超过普通强基线；CUPID整段画像、两例纠正ICL、片段和规则
编译都没有稳定净收益。

复盘后把问题拆成三个正交组件：

- **内容与反馈**：CUPID检查用户反馈表达了什么、适用范围是什么；
- **有效性**：ValidMem检查记忆虽然可见，是否已过期、被替换或只适合历史问题；
- **触发与安全**：Trigger Bench检查何时该读写，何时不应因关键词、secret、注入、
  相似实体或缺文件而误触发。

E只在这些组件之后提供实际结果，不再作为扩大题目的替代路线。

## 3. 现在已经做了什么

### 3.1 完整交付与调研

- [完整交付总报告](B_COMPLETE_DELIVERY_2026-09-13.md)逐项覆盖五个必须交付物；
- [深度研究复盘](B_DEEP_RESEARCH_RETROSPECTIVE_2026-09-13.md)记录相关工作、失败机制、
  B-Core设计、置信口径和长期路线；
- [公开数据集复盘](topic3-b-public-suite-v1/DATASET_SELECTION_REVIEW.md)记录版本、许可、
  纳入/排除理由，不用最新日期替代数据质量；
- [机器交付索引](topic3-b-delivery-v1/results/delivery-summary.json)的schema为2，五项均
  `pass`，同时保留各方法的`pass/fail`。

### 3.2 公开长对话：CUPID

- 固定公开revision、parquet hash、4个开发persona、12任务、4臂、48次模型调用；
- frozen是同模型普通历史基线，feedback使用两条受控纠正示例；
- feedback对frozen为3胜4负5平；输入为3.434倍，生成时间为1.620倍；
- 结论：Eval Runner和结构化结果满足交付，但自然反馈利用没有正收益；assistant语义
  审查不是官方gold，也不是memory-cause标签。

入口：[协议](topic3-b-delivery-v1/PUBLIC_LONG_DIALOGUE_PROTOCOL.md)、
[Runner](topic3-b-contextual-feedback-v1/feedback_learning.py)、
[结构化结果](topic3-b-delivery-v1/results/public-long-dialogue.json)。

### 3.3 生命周期：ValidMem

- v1.1全量466例、1,393条记忆完成适配；保留69个空ground-truth过期题；
- 固定60例开发选择type-aware策略，其余406例一次性留出；
- 普通374/406，启用387/406，15胜2负389平，绝对提升3.20个百分点；
- case级`p=0.00235`，但26个batch的sign `p=0.125`；输入token增加0.59%，总时延
  增加14.01%。

结论：方向性方法验证，不是高置信产品收益；本协议不测MemoryCore L1写入。

入口：[协议](topic3-b-public-suite-v1/VALIDMEM_PROTOCOL.md)、
[结果](topic3-b-public-suite-v1/VALIDMEM_RESULTS.md)、
[JSON](topic3-b-public-suite-v1/results/validmem-codex-holdout.json)。

### 3.4 真实host触发：Trigger Bench

- 固定32例开发与140例一次性留出；v1→v2→v3只在开发集演化，v3后冻结；
- 每例使用独立workspace、独立MemoryCore SQLite库和一个Codex turn；
- 预置记忆走`writeMemory`，检索走`executeMemorySearch`/`queryL1Records`，判定读取真实
  MCP trace、最终store与answer，不接受模型自报“我搜索了”；
- 完整通过112/140→130/140，21胜3负116平；74相关簇bootstrap 95%差值
  `[+5.98,+19.13]pp`，sign `p=0.00235`；
- 负例静默41/66→59/66，但正例触发73/74→72/74；工具调用144→94；输入token
  减少7.76%，p95下降3.08%，p50增加3.69%。

结论：当前最强正向证据，主要收益是少做无关记忆操作；仍是单模型、单次公开微任务
方法验证，不是自然反馈学习或长编程任务通过率。

入口：[协议](topic3-b-public-suite-v1/TRIGGER_PROTOCOL.md)、
[结果](topic3-b-public-suite-v1/TRIGGER_RESULTS.md)、
[Runner](topic3-b-public-suite-v1/trigger_codex_runner.py)、
[JSON](topic3-b-public-suite-v1/results/trigger-codex-holdout.json)。

### 3.5 B→E→B局部闭环

- AMB中一个实际失败artifact与checker回执形成候选后，同任务重放从失败到通过；
- 四个受控代码项目include/omit为4胜0负，但双侧sign `p=0.125`；
- 已有decision→feedback claim→memory assertion→outcome的重放合同；
- 这些证明链路可测，不证明跨项目迁移。

入口：[AMB结果](topic3-b-public-suite-v1/AMB_OBSERVED_LOOP_RESULTS.md)、
[受控闭环](topic3-b-instrumented-loop-v1/RESULTS.md)。

### 3.6 实现、开关与失败回退

- 生产侧只保留可选`memory-feedback`旁路，导入不启用；
- off返回宿主原baseline；异常、超时、非法ID和over-k都fallback；
- sidecar候选最多256，`k`为1..32，deadline最多30秒，没有持久写句柄；
- Trigger完整清单最多20条，单次写入最多4,000字符，每case隔离；
- sidecar四态全部通过；真实Codex MCP enabled/disabled/forced-failure三态全部通过，
  强制失败store不变。

入口：[运行时说明](../src/core/memory-feedback/README.md)、
[sidecar合同](topic3-b-delivery-v1/results/runtime-contract.json)、
[真实host合同](topic3-b-public-suite-v1/results/trigger-runtime-contract.json)、
[移植与回滚](topic3-b-delivery-v1/PORTING.md)。

## 4. 五项交付物的审阅判定

| 项目 | 当前判定 | 审阅时必须确认 |
|---|---|---|
| 调研+设计 | pass | 相关工作是否支持方法选择；B/E边界和演化停止条件是否自洽 |
| 公开长对话Runner+基线 | pass | CUPID版本/子集/seed/粒度/标签隔离是否可复现；负结果是否保留 |
| 实现+基座对比 | pass | Trigger/ValidMem是否只比较同模型同协议差异；不能跨分母合并 |
| off+强制失败 | pass | 是否真实回到基座、是否记录fallback、是否避免store污染 |
| PR+适配+移植 | pass | benchmark适配是否与生产代码分层；内部只需替换loader/标签/宿主 |

## 5. 请重点复盘的六个问题

1. Trigger的工具描述差异是否构成公平、可移植的方法，还是过度贴合公开类别？
2. Trigger在相关簇上的统计处理是否足够保守，三项配对损失是否揭示不可接受的召回
   风险？
3. ValidMem的type-aware策略是否使用了允许的标准化生命周期元数据，是否存在间接gold
   泄漏；batch `p=0.125`应如何限制主张？
4. CUPID的反馈对象、authority和scope为什么仍不足，是否有比继续调prompt更有信息价值
   的实验？
5. 当前sidecar、MCP bridge和数据适配是否符合Tencent Memory代码风格，是否还能减少
   重复而不牺牲审计性？
6. 下一阶段若要证明产品收益，最小的未见repository顺序任务、同模型baseline和E
   checker合同应怎样设计？

建议审阅输出分为：`blocking`、`major`、`minor`、`accepted claims`、`rejected claims`、
`next experiment`。若没有blocking，也请明确哪些结论只是方法级，哪些可以进入产品
shadow，避免用“整体不错”代替逐项判断。

## 6. 不允许误报的内容

- 不说CUPID自然反馈学习已经成功；
- 不把ValidMem的case显著写成batch/产品高置信；
- 不说Trigger正例召回也提高，实际略降1例；
- 不把Trigger工具触发等同跨任务反馈学习；
- 不把AMB 1/1或受控4/4外推为跨项目稳定收益；
- 不说PR已经合并、Gateway已经启用、持久promotion已开放；
- 不使用旧30B下载、未完成规则迁移或部分回执作为完整质量结果；
- 不把历史`B_FINAL_HANDOFF`中的“任务停止”当成当前状态。该文件是当时的停止快照，
  后续工作由用户重新授权，本交接和PR实时head是当前审阅入口。

## 7. 建议阅读顺序

1. 本交接；
2. [完整交付总报告](B_COMPLETE_DELIVERY_2026-09-13.md)；
3. [机器交付索引](topic3-b-delivery-v1/results/delivery-summary.json)；
4. [Trigger结果](topic3-b-public-suite-v1/TRIGGER_RESULTS.md)与逐例JSON；
5. [ValidMem结果](topic3-b-public-suite-v1/VALIDMEM_RESULTS.md)；
6. [CUPID结构化结果](topic3-b-delivery-v1/results/public-long-dialogue.json)；
7. [运行时实现](../src/core/memory-feedback/README.md)与[移植说明](topic3-b-delivery-v1/PORTING.md)；
8. 需要追溯失败路线时再读[深度复盘](B_DEEP_RESEARCH_RETROSPECTIVE_2026-09-13.md)
   和[研究账本](B_RESEARCH_LEDGER.md)，不要按时间遍历全部历史目录。

## 8. 最小复验

在`MemoryCore`目录执行：

```bash
python benchmarks/topic3-b-delivery-v1/delivery_eval.py
npx tsx benchmarks/topic3-b-delivery-v1/runtime_contract_harness.ts \
  /tmp/topic3-b-runtime-review.json
python -m unittest discover -s benchmarks/topic3-b-public-suite-v1 -p 'test_*.py'
npm run build:plugin
```

当前已验证：delivery schema 2五项均pass；公开套件20 tests passed；运行时相关10文件
57 tests passed；sidecar 4/4与Codex MCP 3/3合同通过；插件构建通过。完整模型重跑成本
较高，审阅者应先从冻结回执重算；若质疑模型随机性，再做预注册的不同模型/重复运行，
不得读取留出失败后修改v3。

## 9. 当前最准确的结论

工程交付已经完整，B的触发、安全和生命周期方向已有实证价值；E回执与回退合同也已
扎实闭合。尚未完成的是最难的一段：从自然反馈中可靠归因并形成可迁移状态，在新的
长编程任务中稳定减少重复错误。请围绕这个缺口复盘，而不是重新回到“多存历史、换
更大模型或堆更多相似QA”的路线。
