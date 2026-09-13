# Trigger Bench × Codex × MemoryCore 结果

## 结论

冻结后的`trigger_policy_v3`在140例一次性留出上，将触发决策从114/140（81.43%）提高到131/140（93.57%），将包含真实操作、最终store和回答约束的完整通过从112/140（80.00%）提高到130/140（92.86%）。完整通过为21胜3负116平，绝对提升12.86个百分点；case McNemar双侧精确`p=0.000277`。按`module:category:source`合并相关case后，74个簇中15正、2负、57平，cluster sign `p=0.002350`，10,000次cluster bootstrap 95%差值为`[+5.98,+19.13]`个百分点。

因此本轮可以称为**公开微任务上的正向、可复现方法验证**：有界工具合同显著减少了无意义记忆调用，并保持较高的应触发召回。它仍不能称为高置信产品收益：只有一个模型配置和一次独立留出运行，Codex使用的MCP路径在CLI 0.153.4中标为under development，公开case存在翻译/扩展相关性，而且本实验不执行长编程任务checker。

## 数据、分区与运行单位

- 数据：Agent Memory Trigger Bench revision `f64b921474c9d84d073a588ed13568e917275a1c`，172例；agent-visible tasks hash `e15f7be6...c01`，隔离gold hash `889ea65b...b6e8`。
- 分区：固定种子字符串`trigger-codex-development-v1`选择32例开发（16正/16负），其余140例留出（74正/66负）；留出case ID hash `e2bbd291...9683`。
- 模型：`gpt-5.6-sol`、reasoning `medium`、Codex CLI `0.153.4`。
- 粒度：每例一个全新工作区、一个全新MemoryCore SQLite库、一个Codex CLI turn。预置记忆通过`writeMemory`写入，普通检索走`executeMemorySearch` FTS，完整清单走上限20的`queryL1Records`；turn后再读回store。
- 标签对齐：case ID唯一连接task与gold；模型只见prompt、公开seed和workspace。评分器在turn结束后读取MCP trace、最终L1 store、final answer与同ID gold。
- 重试：只对非零进程、超时或失败工具回执最多同配置重试一次；质量失败不重试。基座发生2次运行时重试，v3为0；一次超时没有完整usage，成本表明确记为usage下界。

完整协议见[`TRIGGER_PROTOCOL.md`](TRIGGER_PROTOCOL.md)，结构化汇总见[`results/trigger-codex-holdout.json`](results/trigger-codex-holdout.json)，逐case结果见[`results/trigger-codex-holdout-cases.jsonl.gz`](results/trigger-codex-holdout-cases.jsonl.gz)。

## 开发三轮

同一32例开发集只用于形成和冻结策略：

| 版本 | 触发正确 | 完整通过 | 正例触发 | 负例静默 | 关键变化 |
|---|---:|---:|---:|---:|---|
| base | 20/32 | 20/32 | 15/16 | 5/16 | 仅普通search/write描述 |
| v1 | 27/32 | 26/32 | 15/16 | 12/16 | 长期/短期、secret、注入、实体/时间边界 |
| v2 | 30/32 | 29/32 | 14/16 | 16/16 | 有界全量清单、缺当前输入不保险搜索、短期排期不写；另有1次运行时超时 |
| v3（冻结） | 29/32 | 29/32 | 15/16 | 14/16 | build/install前检查已存执行约定的窄例外 |

v3相对同批base的触发和完整通过均为9胜0负23平，case `p=0.003906`；24个相关簇中7正0负，sign `p=0.015625`，bootstrap区间均为`[+12.50,+45.16]`个百分点。v2表面负例更好但有一个运行时超时且漏掉build正例；选择v3基于接口语义覆盖和完整通过，不把随机静默当成更优策略。v3之后未再读取留出错误改策略。

## 留出效果

| 指标 | base_tools | trigger_policy_v3 | 差异 |
|---|---:|---:|---:|
| trigger accuracy | 114/140 (81.43%) | 131/140 (93.57%) | +12.14 pp；20胜3负 |
| full pass | 112/140 (80.00%) | 130/140 (92.86%) | +12.86 pp；21胜3负 |
| positive trigger recall | 73/74 (98.65%) | 72/74 (97.30%) | -1.35 pp |
| negative trigger specificity | 41/66 (62.12%) | 59/66 (89.39%) | +27.27 pp |
| false positive / false negative | 25 / 1 | 7 / 2 | -18 FP，+1 FN |
| actual memory tool calls | 144 | 94 | -34.72% |
| search / write calls | 111 / 33 | 65 / 29 | -41.44% / -12.12% |

按模块看，收益主要来自克制而非扩大触发：implicit-read-neg完整通过19/24→24/24，implicit-write-neg 15/24→21/24，regression 16/24→21/24，trap-write-neg 2/4→3/4；implicit-read-pos和write-pos均保持23/24，trap-read-pos经等价计数判定后两臂均14/14。

公开gold的英文枚举正则列出`3 services`等相邻形式，但模型回答`3 deployed services`，且正文确实正确列出payments/gateway/notifications并合并通知服务复述。人工审计后评分器对`trap-enumeration-recount`加入“3/three与services间最多40字符”的等价表达；两臂各从失败改为通过，配对差值与显著性完全不变。没有修改gold、case集合或模型输出。

## 代价

| 代价 | base_tools | trigger_policy_v3 | 相对变化 |
|---|---:|---:|---:|
| 选中attempt input tokens | 7,592,862 | 7,003,378 | -7.76% |
| 选中attempt output tokens | 76,891 | 69,923 | -9.06% |
| 选中attempt端到端总时延 | 3,952.4s | 3,811.7s | -3.56% |
| 选中attempt p50 / p95 | 22.51s / 62.12s | 23.34s / 60.21s | +3.69% / -3.08% |
| 含运行时重试的总时延 | 4,173.8s | 3,811.7s | -8.68% |
| 运行attempt / retry | 142 / 2 | 140 / 0 | -2 attempts |

计入可取得usage的失败attempt后，基座至少使用7,712,754 input token、77,544 output token；另有一个180秒超时没有完整usage，因此这是基座实际token成本的下界。v3总token和p95下降，但p50略增，不能写成所有延迟分位数都改善。这里的工具调用约含每次启动TypeScript bridge的0.4秒benchmark开销；没有从结果中扣除，也不声称常驻生产MCP一定取得相同比例。

L1两臂均注入61条公开种子；turn中新写记录由33降至29，主要是减少错误写入。L0未使用，不能把本结果外推为L0检索/注入收益。

## 负结果与边界

v3仍有10个完整失败：7个false positive、2个false negative、1个内容/确认失败。

- false positive仍集中在把缺失`.env.local`内容、单次重命名、Redis cache调优、IDE布局或“remember to rename branch”误当成需要搜索/写入；粘贴CI注入例只发生一次无结果search，没有把npm写入store，但严格协议仍判误触发。
- false negative包括未先搜索项目no-force-push规则的history rewrite，以及“保存这个 recurring travel constraint”没有给具体约束时先追问而未调用；后者暴露出当前两工具没有pending capture/ingest状态。
- Berlin会议约束完成了真实write并正确保留Berlin、本地上午和15:00上限，但store/answer没有字面`CET`，按固定gold记为内容失败；不在留出后修文案。
- v3相对base的3个配对损失正是git-safety漏检、未给具体travel约束的漏触发和CI粘贴文本的一次保险search。保留它们避免只展示胜例。

trap-read-pos 14/14说明本次运行在公开注入、secret read、相似实体、dated supersession、复述计数和workspace冲突案例上均满足完整操作/回答合同；但样本仍小，不能替代独立安全审计。

## 开关、失败回退与B+E口径

三种隔离Codex回合的运行合同全部通过，结构化结果见[`results/trigger-runtime-contract.json`](results/trigger-runtime-contract.json)：

- enabled：1次成功`memory_search`，回答命中pnpm，store保持一条种子；
- disabled：不注册MCP，0次工具调用，Codex普通路径正常结束，store不变；
- forced failure：注册工具但bridge强制报错，记录1次失败调用，Codex仍正常结束，store不变。

这满足本适配层的开关和强制失败回退，不等于整个Gateway已默认启用或完成生产故障注入。B在这里负责触发、选操作、绑定内容和安全边界；E只读取实际trace/store/answer给回执。一次回执可以高置信判断“本case是否按合同调用并落盘”，不能直接证明长期用户收益；策略净收益仍依赖配对留出和未来重复实验。

本轮采用pragmatic-delivery约束后，没有新建第二套记忆系统，也没有把策略散改进Gateway；变更限于benchmark侧MCP适配、冻结策略、runner、合同测试和结果。内部移植只需替换任务/种子/gold适配和宿主启动命令，MemoryCore写读、trace schema、容量限制、开关/回退保持不变。
