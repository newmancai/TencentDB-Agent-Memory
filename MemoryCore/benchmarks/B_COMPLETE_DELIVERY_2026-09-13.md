# B+E 完整交付总报告

## 最终结论

本项目要求的五项交付物已经齐备并可从本报告逐项进入。交付状态为
`pass_with_mixed_method_evidence`：公开长对话 CUPID 的自然反馈利用没有超过
冻结基线；ValidMem 生命周期判断和 Trigger Bench 真实 Codex×MemoryCore host
留出取得正向方法结果；关闭开关、强制失败回退、结构化输出、数据适配和内部
移植说明均已具备。这个结论支持“完整、可审阅的 B+E 研究工程交付”，不支持
“已达到 Codex/Claude Code 产品级自学习记忆”。

| 必须交付物 | 状态 | 直接证据 |
|---|---|---|
| 1. 调研报告与设计说明 | 通过 | 本报告；[深度复盘](B_DEEP_RESEARCH_RETROSPECTIVE_2026-09-13.md)；[研究账本](B_RESEARCH_LEDGER.md) |
| 2. 公开长对话 Eval Runner 与结构化基线 | 通过，方法收益为负也保留 | [协议](topic3-b-delivery-v1/PUBLIC_LONG_DIALOGUE_PROTOCOL.md)、[`feedback_learning.py`](topic3-b-contextual-feedback-v1/feedback_learning.py)、[`delivery_eval.py`](topic3-b-delivery-v1/delivery_eval.py)、[结构化结果](topic3-b-delivery-v1/results/public-long-dialogue.json) |
| 3. 所选实现及基座对比 | 通过，证据为混合 | [`memory-feedback`](../src/core/memory-feedback/README.md)、[ValidMem结果](topic3-b-public-suite-v1/VALIDMEM_RESULTS.md)、[Trigger结果](topic3-b-public-suite-v1/TRIGGER_RESULTS.md) |
| 4. 关闭与强制失败回退 | 通过 | [sidecar四态结果](topic3-b-delivery-v1/results/runtime-contract.json)、[真实Codex MCP三态结果](topic3-b-public-suite-v1/results/trigger-runtime-contract.json) |
| 5. 可审阅 PR、数据适配和移植说明 | 通过 | [PR #2](https://github.com/newmancai/TencentDB-Agent-Memory/pull/2)、[移植说明](topic3-b-delivery-v1/PORTING.md)、[公开套件入口](topic3-b-public-suite-v1/README.md) |

机器可读的五项索引是
[`topic3-b-delivery-v1/results/delivery-summary.json`](topic3-b-delivery-v1/results/delivery-summary.json)。

## 1. 问题定义与 B、E 边界

B 的目标不是“存更多文本”，而是在多轮交互式编程任务中决定：某次观察是否应
形成候选记忆，绑定到哪个用户、项目、动作和有效范围；后续任务应当
`omit/include/verify/ask` 哪一种；过期、秘密、第三方指令和相似实体是否必须拒绝。

E 只提供可追溯结果：checker、工具返回、最终文件、MCP trace、最终 store 和回答。
E 可以高置信判断“本次是否按合同执行和落盘”，但一次 E 回执不能直接证明某条
记忆长期有益，也不能把用户不满自动归因给某次记忆使用。

本期选择的实现方向是**有界、可回退的记忆动作策略与生命周期视图**：

```text
公开/内部事件
  -> 数据适配（agent-visible 与 evaluator-only 分离）
  -> 同模型 baseline / enabled 决策
  -> MemoryCore L1 写入与检索，或冻结片段注入
  -> 实际 trace + store + answer + checker
  -> E 结构化回执
  -> 仅在独立后续任务上计算 B 的净收益
```

生产侧保持旁路：导入模块不启用功能，Gateway 主逻辑不被散改，当前策略没有持久
promotion 权限。研究用 target/scope/trace/replay 保留在 benchmark 支持层。

## 2. 相关工作与数据选择复盘

近年的主线已经从长对话事实问答扩展到环境经验、时态变化、多人归属和因果干预：

| 公开资源 | 它真正测什么 | 对本项目的处理 |
|---|---|---|
| [LongMemEval](https://arxiv.org/abs/2410.10813) / [LongMemEval-V2](https://arxiv.org/abs/2605.12493) | 前者覆盖抽取、多会话推理、时序、更新和拒答；V2进一步用最多500条web-agent轨迹检验环境状态、workflow和gotcha | 是后续经验检索强基准；上下文收集得分不能单独证明反馈学习因果，本期不与CUPID/Trigger混分 |
| [AMA-Bench](https://arxiv.org/abs/2602.22769) | 真实与任意长度合成agent轨迹，强调因果关系和客观信息 | 方向高度相关，但运行规模和任务形态超出本期；列入下一阶段长程压力验证 |
| [GroupMemBench](https://arxiv.org/abs/2605.14498) | 多方会话中的speaker belief、更新、歧义、受众适配与拒答 | 适合未来验证用户/实体隔离；不是当前单用户编程闭环主指标 |
| [Memory Intelligence Benchmark](https://github.com/ldclabs/mib) | 用相关记忆消融、无关记忆稳定性和harm resistance测过去是否正确改变未来 | 其paired intervention和分簇统计与本期原则一致；当前公开版本仍有待校准项，不替换已冻结主评测 |
| [ValidMem v1.1](https://huggingface.co/datasets/Zhou11Alex/ValidMem) | 466例、1,393条记忆的替换、过期、当前/历史意图 | 纳入全量适配；开发60后一次性留出406，验证生命周期而非自然反馈学习 |
| [Agent Memory Trigger Bench](https://huggingface.co/datasets/wallfacers/agent-memory-trigger-bench) | 真实工具trace与最终store上的该读/写及不该触发，含注入、secret、过时和实体混淆 | 纳入真实Codex MCP×MemoryCore host；32开发后冻结v3，一次性留出140 |
| [CUPID](https://cupid.kixlab.org/) | 多session persona、偏好和上下文变化 | 作为本期必须的公开长对话方法验证；[本地来源审计](topic3-b-contextual-feedback-v1/README.md)保留其负结果，不当最终业务指标 |
| [CodeMEM](https://arxiv.org/abs/2601.02868) | repository级迭代代码生成中的AST上下文与session memory | 支持“代码状态与对话状态分层”的设计，但论文结果不是本项目结果 |

数据不是越多越好。本期用 CUPID 检验反馈表示，用 ValidMem 检验生命周期，用 Trigger
检验触发和安全，用 AMB/本地 checker 检验 E→B→E 的可执行链。各自分母、标签和
终点不同，因此不生成一个综合“记忆总分”。ISETrace、LongMemEval-V2和AMA-Bench
只作为下一阶段候选，不在没有完整基线时加入本次主结论。完整数据版本、许可和排除
原因见[近期数据集复盘](topic3-b-public-suite-v1/DATASET_SELECTION_REVIEW.md)。

## 3. 方法演化与停止边界

### 3.1 自然反馈路线

CUPID 四臂固定为 request、frozen、unlabelled 和 feedback。同一 Qwen3-4B、相同
解码和轮换次序下，feedback 对 frozen 为3胜4负5平；输入是 frozen 的3.434倍，
生成时间是1.620倍。整段画像、摘要、两例纠正 ICL、片段和规则编译都没有形成
稳定净收益。因此停止在既有题上继续改 prompt、筛样本或换弱基线。

### 3.2 生命周期路线

ValidMem 在60个开发例上选定 type-aware 规则，随后冻结。406例留出中，普通可见性
基线374/406，启用策略387/406，15胜2负389平，提升3.20个百分点。case级
`p=0.00235`，但26个batch只有4正0负22平，batch sign `p=0.125`；因此只称方向性
方法验证，不称高置信产品收益。该协议不测MemoryCore写入路径，L1明确记为未测。

### 3.3 触发与安全路线

Trigger 的32例开发集只用于 v1→v2→v3：先增加长期/短期、secret、注入、实体和
时间边界，再增加有界完整清单与缺输入不保险搜索，最后增加build/install前检查
已存执行约定的窄例外。v3随后冻结，不读取留出错误继续改规则。

140例留出中，真实完整通过从112/140提升到130/140，21胜3负116平；74个相关簇
bootstrap 95%差值为`[+5.98,+19.13]`个百分点，cluster sign `p=0.00235`。收益
主要来自负例静默41/66→59/66；正例触发73/74→72/74，不能宣称全面提升。

### 3.4 B→E→B闭环

AMB 实际失败 artifact 与 checker 回执形成候选后，同任务重放从失败到通过，但只有
1个闭合实例。四个受控代码项目的 include/omit 为4胜0负，双侧sign `p=0.125`。
这证明链路和局部因果可测，不证明跨项目泛化。自然反馈 learned gate 仍未达到上线线。

## 4. 指标、效果与成本

| 层 | 定义 | 当前报告位置 |
|---|---|---|
| L1 抽取/写入 | 实际 `writeMemory` 成功、记录数、最终store include/exclude；若未运行则写`not_measured` | Trigger结果、instrumented loop |
| L0 检索/注入 | 实际search次数、检索片段或exact prompt span、注入记录/token；未使用L0时单列 | Trigger、ValidMem、CUPID各自结果 |
| 触发 | `trigger_accuracy`、正例recall、负例specificity、false positive/negative | Trigger结构化结果 |
| 生命周期 | answer accuracy、CRR、EAR、current/history与空ground-truth保留 | ValidMem结构化结果 |
| 长对话质量 | coverage与同题paired win/loss/tie；assistant评审不伪装官方gold | CUPID结构化结果 |
| E任务效果 | checker/task pass、重复失败、wrong-op/wrong-report | AMB与instrumented loop |
| 代价 | input/cached/output/reasoning token，工具调用，新增记录，端到端p50/p95和重试成本 | 各结果JSON分开报告 |

Trigger 的实际工具调用144→94（-34.72%），选中attempt输入token减少7.76%，p95时延
减少3.08%；p50时延增加3.69%，如实保留。ValidMem启用策略输入token增加0.59%，
总时延增加14.01%。不存在“所有优化同时更准、更快”的笼统结论。

## 5. 置信度与“直接判断”口径

- **合同级高置信**：实际trace、最终store、exact checker可直接判断本case是否调用、
  写入、回退或通过；这些是可重复的程序事实。
- **方法级证据**：配对留出和相关簇统计估计同模型下的增量。Trigger的cluster区间
  高于零；ValidMem的batch符号检验未过线，二者置信度不同。
- **长期产品效果**：仍需不同模型/重复运行、按项目或用户聚类的未见顺序编程任务，
  并把学习、核验和误写成本计入。组件判断比多次端到端运行便宜且更能定位原因，
  但不能替代后者对稳定性和真实效用的估计。
- **自然反馈真值**：用户纠正、编辑或不满先是 observation；对象、权威性、范围和
  记忆因果未知时允许 abstain，不能直接提升为持久事实。

## 6. 结构化输出、开关与回退

所有正式输出都包含模式、通过/失败、分母和边界：

- CUPID：[`public-long-dialogue.json`](topic3-b-delivery-v1/results/public-long-dialogue.json)；
- ValidMem：[`validmem-codex-holdout.json`](topic3-b-public-suite-v1/results/validmem-codex-holdout.json)；
- Trigger：[`trigger-codex-holdout.json`](topic3-b-public-suite-v1/results/trigger-codex-holdout.json)和[逐例压缩结果](topic3-b-public-suite-v1/results/trigger-codex-holdout-cases.jsonl.gz)；
- 五项交付索引：[`delivery-summary.json`](topic3-b-delivery-v1/results/delivery-summary.json)。

sidecar合同验证 feature-off、enabled、selector forced failure 和 over-k fallback 四态；
Trigger真实host验证 enabled、完全不注册MCP的disabled，以及bridge强制报错三态。
关闭后返回原基座或普通Codex路径；失败不写共享store，不删除或永久替换基座索引。

容量上限保持明确：sidecar候选最多256、`k`为1..32、deadline最多30秒；Trigger
完整清单最多20条、单次写入最多4,000字符、每case独立库。关键日志包含模式、策略
版本、`k`、候选/选择数、辅助路径、fallback原因、信号类型、耗时、工具trace和usage。

## 7. 可移植实现与内部改动面

生产实现集中在`src/core/memory-feedback/`的可选旁路；公开数据和真实host桥接集中在
benchmark目录。内部数据只需替换任务/事件loader、初始记忆、evaluator-only标签和
宿主启动命令；MemoryCore写读、trace schema、容量限制与fallback合同不变。详细字段
和回滚步骤见[PORTING.md](topic3-b-delivery-v1/PORTING.md)。

当前MemoryCore package版本为`2.0.0-beta.1`。交付材料只依赖本仓库开源代码、公开
可下载数据与本地可复现运行回执；没有引用未开源内部benchmark、harness或私有模块。

内部多轮编程评测必须按用户/项目/任务族切分，第一轮真实checker回执只能生成候选；
后续相关任务才计算baseline与enabled差值。不得把公开gold、未来turn或人工答案写回
agent输入，也不得用换子集且不重跑基线的方式刷分。

## 8. 复现与审阅

在`MemoryCore`目录运行：

```bash
python benchmarks/topic3-b-delivery-v1/delivery_eval.py
npx tsx benchmarks/topic3-b-delivery-v1/runtime_contract_harness.ts \
  benchmarks/topic3-b-delivery-v1/results/runtime-contract.json
python -m unittest discover -s benchmarks/topic3-b-public-suite-v1 -p 'test_*.py'
npm run build:plugin
```

完整模型推断命令分别保存在CUPID、ValidMem和Trigger协议中；`delivery_eval.py`只从
冻结回执重算，不能伪装成重新运行模型。PR保持draft，便于审阅；没有启用production、
没有合并Gateway策略、没有删除基座索引。

## 9. 最终验收边界

五项交付物均可判通过。主张强度必须保持三层分离：

1. 工程交付完整：**是**；
2. 公开方法验证已有正向结果：**是，Trigger与ValidMem；CUPID仍为负**；
3. 自然反馈驱动、跨任务长期编程收益及Codex/Claude Code产品对标完成：**否**。

下一阶段应优先复核不同模型/重复运行，并在未见repository任务上完成多轮
`失败 → E回执 → B候选/动作 → 后续checker`；不再调当前140例Trigger留出，也不把
增加更多相似QA数据当成因果证据。
