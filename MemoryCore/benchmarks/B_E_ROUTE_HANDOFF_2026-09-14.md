# B+E 路线与产品交接（2026-09-14）

**接手先读本文件。当前目标是比现有系统和合适的开源方案更有用，先验证路线是否值得做；不再把完整对标 Codex／Claude Code 作为近期验收条件，也不要求必须有创新算法或反馈学习。**

当前长程执行与阶段门槛见 [B+E 长程任务](B_E_LONG_TERM_TASK_2026-09-14.md)。

当前结论：已有可运行的项目记忆编码 CLI，E 的执行与证据链明显完善；B 在公开项目上为 2 胜 0 负
6 平，在第二批不重叠 MemoryCode 更新集上把 receiver-aware 目标从 9/10 提到 10/10、1 胜 0 负
9 平。后者区间仍触及 0，支持显式 experimental 路线，不支持稳定普适收益。原话保留仍是默认方案，
约束编译是显式实验选项；编译结果应按精确 history revision 持久复用，不应每次编码重算。接下来做
同条件开源对照和热路径降本，不用外围功能数量、文档数量或组件分数替代后续任务效果。最新两条模型侧
降本捷径均因冻结质量门槛关闭；产品 bridge 已在语义等价条件下把模型前进程 4→2，本机均值固定开销
降低约 37.6%。

本文整理既有资料与用户最新决策。本次交接不启动模型、下载或新评测；不表示用户永久停止后续优化。

## 1. 用户最新要求与执行原则

用户在完成三轮产品优化后明确说：

> “只要和我们现在的比，和一些开源的比做的更好就行了，我更在意你的这个东西路径到底好不好，创新点只是副产物。”

据此调整工作标准：

- 核心问题是“用户纠正之后，后续相关任务是否少犯重复错误，且不误伤其他场景”。
- Codex／Claude Code 可作为执行底座；完整产品平替、两个 backend 同时获得净胜不再是当前工作的前置条件。
- 比较对象先是固定的现有版本，再是同任务、同执行模型下的普通历史／检索及合适的开源方案。
- 简单检索或确定性更新若最好，就采用它；没有收益就收缩或换路，不为了创新保留复杂机制。
- 工程可靠性是基础条件，不能替代记忆质量、回归与总成本证据。

尚未选定、移植或运行新的开源对照，不能宣称已经优于任何开源系统。历史论文调研也不等于本地复现。
旧报告中“同级编码产品”“四臂均通过”等表述保留为历史目标；本节是最新方向。现有 runner 的旧
`pass` 逻辑未在交接中改动，后续新协议应另标版本，不能放宽旧标准后追认旧成绩。

## 2. B 与 E 的职责和完成程度

| 部分 | 职责 | 已做到 | 主要缺口 |
| --- | --- | --- | --- |
| B | 判断哪些反馈应保留、作用于哪个对象／任务、何时引用或更新，验证后续行为收益 | 原话保留；实验性来源引用提议；路径／动作范围；同范围显式版本替换；历史前任引文；撤销 | 范围和 key 仍可能误判；复杂提议没有超过原话基线的稳定证据；不能声称学会了跨任务反馈策略 |
| E | 保存实际执行、工具、检查和状态回执，支持可审阅的闭环 | SQLite 持久化；CLI 编辑与独立检查；usage／日志／差异；取消进程组；编码完成后恢复检查 | 128 条容量、单写者、未完成编码的续跑、真实新机安装及长期使用尚不完善 |

checker 通过只证明该次被检查的行为；不能证明某条记忆长期正确。工具输出不是用户指令，
一次失败也不能直接归因为某条记忆错误。接口引用合法不等于语义适用正确。

## 3. 对当前路线的判断

**值得继续验证的基础：** 保存完整原话和出处；在当前任务读取相关证据；用户明确更新时保留版本链；
用真正的后续代码行为评价效果。它让错误可以追查和纠正，但它的净收益仍需对照验证。

**当前不能默认投入的机制：** 对每条消息强制总结、编译成规则或学习共享策略。CUPID 等旧实验没有
稳定净收益，最近真实仓库试验也没有显示编译比原话更好。新的 MemoryCode focus 只证明同一强模型的
两阶段历史整理在一批新更新题上方向性提高；样本小且冷路径成本约翻倍，因此默认 `remember` 仍不调用
模型，只有 `remember ... --compile` 才调用提议模型。编译状态可按 revision 复用，但不能据此把强制
编译改成默认。

**不要把简单方案理想化：** MemoryCode 显示固定原话 top-8 检索在长历史和更新任务上会漏掉新版本。
这说明需要找失败机制，不意味着所有场景都需要复杂编译，也不意味着普通检索已经足够好。

近期优先级是效果验证。容量归档、桥接性能、界面等只在阻碍真实使用或本次验证时投入；
不要因上一份工程报告列了“下一步容量管理”，就自动把 E 扩展变成新的主线。

## 4. 已有证据：哪些有效，哪些不能外推

### 4.1 最近三轮编码原型

| 验证 | 结果 | 结论边界 |
| --- | --- | --- |
| 首轮合成顺序任务 | 原话 3/3，记忆 3/3；0 胜 0 负 3 平 | 真实 Codex 工具调用接线；不是产品增益 |
| 四个真实仓库上的人为维护任务 | boltons、more-itertools、packaging、itsdangerous；每项目 3 步；24 次编码运行；两组均 12/12 | 0 胜 0 负 12 平；只有 4 个相关项目簇；任务不是自然 issue，检查不是完整上游测试套件 |
| 历史引文修复 | 沿 supersedes 补回标为 historical 的前任原文；两份真实状态各恢复两条前任引文 | 修复在上述 24 次运行结束后合入，不能把 12/12 当作修复后的质量成绩 |
| 满容量与检查恢复 | 128 条原生 SQLite 观察；1 次新 Codex 跨文件编码；主动取消检查后成功补跑；恢复模型调用 0 | 人工规则、合成任务；支持故障恢复与引用接线，不是 B 质量对照 |

真实仓库试验的关键成本：

| 累计量 | 原话 | 编译记忆 |
| --- | ---: | ---: |
| 编码 CLI 次数 | 12 | 12 |
| 额外编译 CLI 次数 | 0 | 12 |
| 全部输入 token，含编译和缓存 | 2,803,371 | 2,629,487 |
| 全部非缓存输入 token，含编译 | 295,851 | 435,567 |
| 各步骤完整耗时累计，含编译／存储／检查 | 1,323.672 秒 | 1,347.321 秒 |

没有稳定质量增益，也不能宣称省钱。缓存与执行顺序没有完整交叉平衡；CLI 没有提供美元费用和可
独立确认的 served model ID。请求模型为 `gpt-5.6-sol`、medium。Claude 默认及 Sonnet 诊断连续 502，
没有获得该轮质量成绩；服务故障不能记为质量失败，后续也不必为了满足旧四臂目标反复重试。

具体输入和全部限制见[真实仓库报告](B_E_REAL_PROJECT_OPTIMIZATION_2026-09-14.md)、
[恢复报告](B_E_RECOVERY_OPTIMIZATION_2026-09-14.md)及对应
[真实仓库 JSON](topic3-be-agent-product-v1/results/real-project-pilot.json)、
[恢复 JSON](topic3-be-agent-product-v1/results/recovery-smoke.json)。

### 4.2 需要继承的公共数据与早期研究结论

- **MemoryCode：** 全量 360 对话、4,182 次检索，最新目标来源 recall@8 为 45.89%，100-session
  为 20.01%；更新题 stale-only 为 24.12%。冻结 24 对话／72 次生成中，原话历史 strict 为
  12.50%，FTS 为 16.67%，1 胜 0 负 23 平，未达高置信增益；两者 10 项更新题均为 0%。
  特权最新规则 oracle 为 54.17%，只表示有信息组织空间，不是可部署方案。FTS 输入减少 76.80%
  是该协议下的成本证据，不代表质量等价。最初 4 次 Codex 有界诊断在两个固定更新 dialogue 上得到
  完整原话 2/2、无历史 0/2。后续又覆盖冻结子集全部 10 个更新 dialogue：20/20 调用有效，冻结评分下
  完整原话 7/10、无历史 0/10，即 7 胜 0 负 3 平，bootstrap 95% 区间 `[+0.40,+1.00]`，exact sign
  `p=0.015625`；短历史 4/5，长历史 3/5。其中两项平局是固定 attribute 提取器只认字面 `self` 导致的
  假阴性，明确标为事后敏感性时为 9/10；冻结主结果不改。完整原话的总输入、非缓存输入、墙钟分别
  多 120.56%、411.37%、51.68%，所以这是模型依赖和历史效用证据，不是高效上下文或产品成绩。详见
  [MemoryCode 结果](topic3-be-agent-product-v1/MEMORYCODE_RESULTS.md)与
  [完整 Codex 更新诊断](topic3-be-agent-product-v1/MEMORYCODE_CODEX_UPDATE_FULL_RESULTS.md)。
  随后第一批不重叠 focus 开发集从 7/10 到 9/10，但 3 胜 1 负；修正已定位的独立命名规则混淆后，
  第二批再排除 34 个已用 dialogue，正式结果为 raw 9/10、focus 10/10，1 胜 0 负 9 平，30/30 调用
  有效。冻结 active-rule 均分 88.67%→91.78%；事后 receiver-aware 全规则敏感性 89.44%→97.00%，
  3 胜 0 负 7 平。主指标区间 `[0,0.3]` 且 sign `p=1.0`，只支持方向性 experimental 结论。
  冷 focus 为 2.026 倍非缓存输入和 1.706 倍墙钟；持久复用编译状态后的已执行 coding stage 为
  1.101 倍非缓存输入、0.969 倍墙钟和相同调用数。详见
  [focus 与 infra 结果](topic3-be-agent-product-v1/MEMORYCODE_FOCUS_RESULTS.md)。authoritative-source
  后续在再不重叠 10 题上把热编码非缓存输入降到 0.693 倍，但主指标为 1 胜 1 负 8 平，未启用；
  single-pass 两题为 1 胜 1 负且成本回退，提前停止。详见
  [进一步 infra 结果](topic3-be-agent-product-v1/MEMORYCODE_INFRA_OPTIMIZATION_RESULTS.md)。
- **CUPID：** 当前两例纠正 ICL 对普通历史为 3 胜 4 负 5 平，输入 3.434 倍；没有稳定反馈学习收益。
- **ValidMem：** 留出 374/406→387/406，15 胜 2 负；case 显著但 batch sign p=0.125。属于生命周期
  方法验证，不能当编码收益或实际 L1 写入验证。
- **Trigger：** 112/140→130/140，21 胜 3 负，主要减少无关记忆操作；它是公开微任务中的接口／触发
  改善，不能当跨任务反馈学习。后续复盘发现开发／留出同源场景簇交叉，需保留这一限制。
- **STALE：** 直接最终绑定与提议后裁决分别 13/16；独立 candidate-only 15/16。只支持候选提名，
  不支持自动失效或持久化。另 200 行普通检索显示 raw-session 措辞比归一化状态句召回更好。

这些是不同任务、不同模型或不同运行合同，不能加成一个总准确率。完整早期证据在另一工作树：
[原研究交接](/home/edarace/Tencent-Memory-2/topic3-be-delivery/MemoryCore/benchmarks/B_REVIEW_HANDOFF_2026-09-13.md)、
[深度复盘](/home/edarace/Tencent-Memory-2/topic3-be-delivery/MemoryCore/benchmarks/B_OPTIMIZATION_DEEP_REVIEW_2026-09-13.md)、
[STALE 复盘](/home/edarace/Tencent-Memory-2/topic3-be-delivery/MemoryCore/benchmarks/B_STALE_RESEARCH_REVIEW_2026-09-13.md)。
这些绝对链接是本机归档入口，外部接手者需要同时取得研究分支的对应文件。

## 5. 工作区、提交与代码入口

研究工作树：`/home/edarace/Tencent-Memory-2/topic3-be-product`，分支
`delivery/topic3-be-product-v1`，focus 结果主提交为 `7da00f5`；除既有未跟踪
`MemoryCore/node_modules` 和本交接同步外干净。
最终产品 PR 工作树：`/home/edarace/Tencent-Memory-2/topic3-be-project-memory-pr`，分支
`delivery/topic3-be-project-memory-v1`；bridge 实现锚点为 `5428a96`，最终文档提交也在 PR #4。原始研究工作树仍为
`/home/edarace/Tencent-Memory-2/topic3-be-delivery`、分支 `delivery/topic3-be-v1`。三者不能混用提交状态。

| 提交 | 内容 |
| --- | --- |
| `25d09a6` | 从研究主线删除自然验证协议、registry、runner 模式和测试 |
| `ecaf3d0` | 新增第一批不重叠 MemoryCode focus 开发比较 |
| `4fa13dc` | 修正前缀／后缀／子串／数字等独立规则维度 |
| `a47528e` | 在模型调用前冻结第二批不重叠质量集 |
| `7da00f5` | 发布 focus 质量、失败试验和冷／热 infra 成本结果 |
| `545eca4` | 产品热路径复用测试、无损紧凑 JSON、最终上交报告更新 |
| `7e19d4f` | 关闭 source-context 与 single-pass 两条冻结模型侧降本候选 |
| `5428a96` | 产品 pre-model bridge 4→2，并冻结等价性／时延协议 |
| `a3b1a63` | 保证范围选择只读取并使用同一个 pre-task 快照 |

| 文件 | 接手用途 |
| --- | --- |
| [CLI README](../scripts/project-agent/README.md) | 使用方式与真实限制 |
| [project_agent.py](../scripts/project-agent/project_agent.py) | remember／record／context／run／history／retract／check-run；宿主锁与证据 |
| [project-memory.ts](../src/core/memory-feedback/project-memory.ts) | 来源、范围、版本链、撤销、历史视图和容量 |
| [store.ts](../scripts/project-agent/store.ts) | Python 到原生 SQLite 的 JSON 桥接，每次操作启动 Node |
| [backend.py](../scripts/project-agent/backend.py) | Codex／Claude 命令、真实进程组、日志、usage |
| [changes.py](../scripts/project-agent/changes.py) | 相对 HEAD 的工作区差异，包含原有编辑，不能全部归因于本轮 |
| [sequence_runner.py](topic3-be-agent-product-v1/sequence_runner.py) | 每项目／臂独立保存代码与记忆、累计检查与成本 |
| [旧评测协议](topic3-be-agent-product-v1/PROTOCOL.md) | 原四臂及 schema 2 合同；是历史协议，不是最新验收目标 |

本地原始证据位于 `/home/edarace/Tencent-Memory-2/.local-evidence/`：

- `project-agent-sequence-v1/`：首轮合成顺序任务。
- `project-agent-real-v1/`：四项目来源、manifest、全部回执、状态与已修改工作区。
- `project-agent-recovery-v3/`：满容量真实编码及检查恢复；v1／v2 是模型调用前的夹具初始化失败。

旧工作区、已用题目、已打开的 MemoryCode 全量数据均不能包装成新留出。不得重置这些证据来获得
“干净”重跑；后续需要新独立工作区。保留 node_modules、v9 文件和其他本地证据。

## 6. 已验证能力与尚未解决的使用限制

研究侧 31 项 agent-product 测试通过；第二批 focus 和第三批 source confirmation 各有 30/30 次 Codex
调用完整有效，所有失败 pilot 原始证据均保留。产品侧本轮重新通过 TypeScript 全量 204/204、项目代理
22/22；bridge 20/20 配对上下文与最终快照等价，模型调用 0。Black／Prettier、build、
1,478,631-byte 包和空目录安装 smoke 已通过；远端 CI 仍须以最终 head 的本轮结果为准，不沿用旧 run ID。

- 128 条观察仍是硬容量；通常每个 run 消耗两条。满后旧上下文可用，但新任务不会进入项目记忆。
- scoped 预算不足时回退完整原话，可能超过字节目标；不代表已经有长期有界上下文策略。
- check-run 仅恢复编码完成之后的检查，针对当前文件；不是未完成模型会话的恢复。
- 单写者文件锁只协调同状态目录的 CLI；不是多设备或分布式一致性。
- 打包测试复用已有依赖并用模拟后端；不等于全新机器安装验证。没有正式 npm 发布。
- 不自动启用 Gateway／生产，不把提议 API 变成自动持久化语义真值。

接手后的最小本地检查（不调用模型）：

```bash
cd /home/edarace/Tencent-Memory-2/topic3-be-product/MemoryCore
export PATH=/home/edarace/node-v24.15.0-linux-x64/bin:$PATH
python -m unittest discover -s scripts/project-agent -p 'test_*.py' -v
python -m unittest discover -s benchmarks/topic3-be-agent-product-v1 -p 'test_*.py' -v
node bin/memory-agent.mjs --help
```

需要真实 CLI 冒烟时再按 [CLI README](../scripts/project-agent/README.md) 操作；`sequence_smoke.py`、
`recovery_smoke.py` 及 `sequence_runner.py` 会调用已登录模型，不能把它们当零成本文档检查。
不要恢复旧 30B 下载、旧本地模型路线、旧题 prompt 追分、production 或他人 GPU 操作。

## 7. 建议下一次优化只交付什么

**建议的有界任务：固定当前 focus 质量锚点，完成一个开源项目记忆方案的同模型适配，并把编译状态复用
接到可审计成本回执。** 不再在已用的三个 10-dialogue 集上改 prompt，也不再恢复“自然验证”。

1. 选择一个能直接给相同 Codex 编码任务提供持久项目上下文的开源实现，固定版本、许可和默认配置；
   若只能做向量召回或无法保留来源，明确写成合同差异。
2. 在未用任务或现有有效公开项目矩阵上比较 `raw_full`、当前 experimental focus／持久约束和开源方案；
   模型、base、checker、隔离和执行顺序保持一致，写入与摘要调用全部计成本。
3. 编译缓存键至少包含 owner/project、精确 history revision、compiler protocol、model 和 effort；任一变化
   必须失效。热路径回执明确标记 cold／reused，不能把算术摊销写成实测 SLO。
4. 质量下限保持第二批公开结果：receiver-aware target 不低于 raw，active-rule 不出现新配对损失；若降本
   路线回归，直接关闭，不用 scorer 或重试掩盖。
5. 输出逐题胜负、全量 active rules、总／非缓存 token、调用数、时延和集成维护成本，并给采用、保留
   experimental 或关闭的明确决定。

当前已排除四条捷径：compact-history 有目标回归，独立 CLI 共享前缀没有产生非缓存 token 收益，
source-context 有一项冻结主指标回归，single-pass 同时有质量和成本回退。下一轮不要重复这些 pilot。

## 8. 接手者必须能回答的五个问题

1. 当前系统到底在哪类真实后续任务上失败，旧代码或当前请求能否已经恢复所需信息？
2. 原话／普通检索能解决多少，新增机制解决了哪个剩余问题？
3. 同一纠正在应该应用时有效、在例外／另一目录／撤销之后又不会误用吗？
4. 包含编译、检索、重试和后续生成后，效果是否值得新增成本和维护复杂度？
5. 与开源方案的比较是否真正在相同任务和执行条件下完成，而非对比论文数字？

先回答这些问题，再决定做哪一种记忆机制。用户认可简单可用的结果，不要求为了创新走复杂路线。

## 9. 交接后首轮推进（2026-09-14）

已新增 [route v2 协议](topic3-be-route-v2/PROTOCOL.md)、三臂真实失败发现 runner、完整原话 BM25
top-8 基线及 [首轮结果](topic3-be-route-v2/DEVELOPMENT_RESULTS.md)。Tenacity #233 和 cattrs #190
两个未用过的修复前项目各含一个真实 issue 任务和一个明确标注的人为同主题控制；探索运行中无历史、
完整原话、top-8 共 12 次 Codex 编码均完成并通过 checker，严重回归 0，逐题全平。随后审计发现准备器
使用的 worktree 可读取源码 clone 的未来 remote refs，且 cattrs 无历史 agent 实际尝试搜索后续版本；
因此整组质量与成本结果已作废，不能据此断言任务无区分度、B 有收益或当前系统无缺陷，也不会进入留出。

一次早期运行因 Tenacity checker 的回调参数名错误而误判，已中止并在原始证据中标为 INVALID；
修正后旧提交仍稳定表现为兼容通过、目标行为失败，而三份既有 agent 修复均通过修正 checker。
下一批开发任务应来自真实 issue／PR 中无法从旧代码恢复的用户或维护者决策（精确策略、例外、名称、
默认值或作用范围），同时配对不应继承的同主题控制；准备器已改为只获取声明 base 及祖先的独立浅仓库，
并验证已知 post-fix SHA 在每个 workspace 中不可解析。在出现重复失败前不实现新修复臂。

随后新增 cachetools #408 与 HTTPX #2278 两个真实 review 中间态，各配一个同主题覆盖控制。六个
workspace 均实核只有一个可达提交、无 remote、最终 review SHA 不可解析；12 次调用和外部检查完整，
三臂仍各 4/4、严重回归 0，质量全平。HTTPX 必要更新中 raw 两臂比 no-history 少用输入 token 和时间，
但单次开发运行只构成效率线索。当前仍没有可重复的质量失败，因此不据此增加编译器或学习器；下一组
必须选择代码常识无法唯一推回的维护者决策，继续找真实质量边界。

又完成 HTTP Core #1008 与 Werkzeug #3166 的精确策略开发矩阵：12 次调用仍全过、质量全平，full raw
相对 no-history 的总输入和墙钟继续下降，top-8 相对 full raw 也继续下降，但 uncached input 略升；因此只
冻结“top-8 能否无质量损失降成本”留出，不增加编译器。首个四项目留出在 15/24 回执时发现 attrs checker
错误依赖源码字面形式，把语义等价条件表达式误判成严重回归，整组已停止并全部作废；Click、HTTP Core、
attrs、MarkupSafe 均视为已暴露，不能重包装。详见
[留出失效复盘](topic3-be-route-v2/HELDOUT_INVALID_REVIEW.md)。下一留出必须换新项目，并在冻结前用至少
两种语义等价实现验证 checker 的实现无关性。

替代留出 v2 随后换用 urllib3、Starlette、AnyIO、Trio，并以行为检查器完成 base、上游结果和等价实现
预检。但在第 9 个调用中，Starlette `no_history` agent 从绝对工作路径向上搜索，读取了已完成
`raw_full` 的 diff、上下文、prompt 和 checker 结果。独立 clone、无 remote 和不可解析未来 SHA 仍不足以
构成 arm 隔离；已立即停止 runner，8 条完成回执和中断调用全部作废，四个项目家族均视为暴露。详见
[v2 留出失效复盘](topic3-be-route-v2/HELDOUT_V2_INVALID_REVIEW.md)。

runner 现已加入外层 `bwrap` 文件系统隔离：隐藏整个研究仓与 `.local-evidence`，只重新挂载当前独立 clone，
并给 Codex 单独的临时 runtime。20 个项目代理测试通过；一次使用已暴露 AnyIO clone 的真实 CLI 预检确认
主研究仓和兄弟 arm 不可见、当前 Git clone 可用。下一矩阵必须再换四个新项目，强制经过该隔离层，并在
接纳结果前扫描原始事件中的禁用路径；此前看似有利的 urllib3/Starlette 数字不进入产品结论。

第三套留出冻结后在第一个 pytest 调用中发现另一条逃逸路径：文件系统隔离有效，但 Codex 使用了服务端
`web_search`，搜索了该 MonkeyPatch 问题的公开实现。runner 在首条回执写入前停止，v3 全部不计成绩；
pytest 视为暴露，h11 也因后续禁网反向预检明确点名而不再复用，packaging 与 Flask 尚未接受模型调用。
详见 [v3 失效复盘](topic3-be-route-v2/HELDOUT_V3_INVALID_REVIEW.md)。适配器现显式设置
`web_search="disabled"`、隔离用户配置，runner 也会把任何 web-search event 当作整组失效；真实负向预检
返回 `SEARCH_DISABLED` 且无联网事件。下一套 v4 只能复用未暴露的 packaging／Flask，再加两个全新项目，
重新冻结后运行。

v4 现已在任何正式矩阵调用前冻结，入口为
[web-disabled held-out v4](topic3-be-route-v2/HELDOUT_V4_PROTOCOL.md)。它使用 packaging、Flask、tqdm、
Uvicorn 四个家族和 12 个新浅克隆；base 均为兼容通过／目标失败，上游结果和另写的等价实现均通过两阶段
行为检查，top-8 也在四项目召回第 12 条接受决策。manifest、checker 哈希与禁网／文件系统双隔离合同均已
写入协议。

v4 24 次正式调用现已完整且可采信，详见 [v4 结果](topic3-be-route-v2/HELDOUT_V4_RESULTS.md)。完整原话和
top-8 均 8/8，无历史 6/8，三臂严重回归均 0；这是一个独立项目家族的有效收益，不是两个：tqdm 无历史
首步选择了“任一未知长度即 None”的合理但错误策略，随后控制因累积代码继续失败；两种历史臂依据旧审查
保留“忽略未知、取已知最小值、全未知才为 0”并通过。24 回执均文件隔离、无 web-search event 或禁用路径。
完整原话相对无历史同时少 30.16% 总输入、17.06% 非缓存输入和 12.46% 墙钟，但每格只运行一次，成本只算
本协议证据。top-8 虽减少 30.86% 注入上下文字节，却相对完整原话多 7.43% 总输入、23.14% 非缓存输入和
4.04% 墙钟；按冻结规则关闭 top-8 效率候选，不在 v4 调参。产品继续保留完整原话默认，下一步只做新项目
家族复现或第二 backend，不增加编译／学习／新检索层。

v5 随后以 Websockets、jsonschema、Scrapy、wsproto 四个全新家族执行两臂复现，结果见
[v5 结果](topic3-be-route-v2/HELDOUT_V5_RESULTS.md)。16 个计划调用均留下回执，完整原话 8/8；但
jsonschema 的 no-history 两格达到 300 秒时限、未运行 checker 且缺 usage，按预注册合同整组失效，
不能把旧机械汇总的“5 胜”当质量结论。可比的家族首任务中，Websockets 和 wsproto 出现完整原话通过、
无历史完成但行为失败的分叉，Scrapy 平，jsonschema 不可判；这强化“精确维护决策可消歧”的假设，
仍不够进入自然轨迹验证。隔离复核未发现实际泄漏：宽路径只看见当前 clone，两个远端命令均连接失败；
所有尝试原样保存在事件日志。runner 已在 v5 后修正为将执行失败汇总为 `indeterminate`。下一步必须换
未暴露、规模更小的新家族做 v6，不重跑 v5 或事后提高时限。

v6 随后完成冻结和 base／上游／等价实现预检，但首个 platformdirs no-history 调用在正确源码行为已经
形成后继续增加测试、文档和检查，最终 300 秒超时且没有正式 checker／usage。确认整组按合同失效后，
正在运行的 full-raw 配对由操作者取消；事后冻结 checker 在两份静止代码上都通过，只用于证明这是 E 的
完成／恢复缺口，不能追认 B 质量成绩。其余 hpack、PrettyTable、importlib_metadata 没有模型调用，仍可
进入新协议。精确边界见 [v6 失效复盘](topic3-be-route-v2/HELDOUT_V6_INVALID_REVIEW.md)。下一 v7 只复用
这三家并补一个新小家族，明确只改指定源码、不加测试／文档、至多一次 focused smoke 后停止；不重跑
platformdirs 或放宽既有结果。现有 `check-run` 无法检查未完成调用，已获得真实 E 缺口证据，但不得自动
接受 partial edit。

v7 进一步把任务限制为单一源码文件。hpack、PrettyTable 共八格完成且两个家族首任务全平；
importlib_metadata 中 no-history 把缺失源转成空 Message 而行为失败，full-raw 依据历史返回 `None` 并通过
行为检查，但同时留下两个 `__pycache__` 目录，违反冻结的单文件／无生成物合同。runner 当时只记录
`changes_after`、未把越界路径纳入 pass，因此整组按 checker 缺陷停止，旧汇总的一个 memory win 不可引用；
详见 [v7 失效复盘](topic3-be-route-v2/HELDOUT_V7_INVALID_REVIEW.md)。现在隔离运行设置
`PYTHONDONTWRITEBYTECODE=1`，runner 也会把任何非声明路径标成 checker 失败和严重范围回归。zipp 没有
收到模型调用，仍可用于下一新协议；hpack、PrettyTable、importlib_metadata 均不可重包装。

v8 在模型调用前完成四家族、两阶段的 base／上游／独立等价实现预检，并首次开启声明输出路径强制。
首个 hyperframe no-history 调用完成后只修改声明的 `src/hyperframe/frame.py`，但共享 `git_output` 对整个
porcelain 输出使用 `.strip()`，删除第一行的前导状态空格；路径解析因此把 `src/...` 误成 `rc/...`，机械
记录为越界严重回归。按冻结协议整组立即停止，正在进行的 raw-full 由操作者取消，其余 14 格未调用。
详见 [v8 失效复盘](topic3-be-route-v2/HELDOUT_V8_INVALID_REVIEW.md)。该轮没有 memory/no-history 配对
结论；no-history 只修标识符、漏掉值掩码仅是单臂机制观察。共享解析现保留前导状态位，并新增真实 Git
回归测试；21 项 project-agent、16 项 agent-product、5 项 route-runner 测试通过。下一 v9 只能复用未调用
的 jmespath、pluggy、zipp，另补一个全新家族；已调用的 hyperframe 不得重跑或包装成 v8 成绩。

v9 修复 porcelain 后完成全部 16 格，执行、checker、usage、隔离和声明路径回执齐全，raw-full 机械 8/8、
no-history 5/8。jmespath 首任务按接受历史实现 FIFO/512/并发删除边界，无历史臂保留随机淘汰/128；zipp
无历史臂在后续控制中受旧测试影响撤销了刚做的异常类型更新，历史臂保留更新。两者是有价值机制诊断。
但逐补丁审计发现 typeguard 无历史臂先比较值再比较类型，仍被冻结 checker 接受；合法 Enum 的只读探针
证明其行为不等价，而协议明确要求类型检查在前。因此 v9 整组失效，机械三胜和较低 token／时延均不能
作为正式收益。精确数据见 [v9 失效复盘](topic3-be-route-v2/HELDOUT_V9_INVALID_REVIEW.md)。下一矩阵不得
复用这四家族，且须按 [checker 编写标准](topic3-be-route-v2/CHECKER_AUTHORING_STANDARD.md) 为每个关键
语义提供会被拒绝的近错实现；仅验证 base fail、上游和等价实现 pass 已被证明不够。

v10 首次按近错标准冻结：42 个预检阶段覆盖 8 个 base 拒绝、8 个上游通过、8 个独立等价通过和
18 个近错拒绝。正式 16/16 调用、checker、usage、隔离和路径回执完整；raw-full 8/8、no-history 6/8，
独立首任务为 importlib_resources 一胜、h2／pycodestyle／path 三平，raw-full 控制回归 0。无历史臂根据
仓内线索选择 `ValueError`，完整原话保留维护者接受的 `TypeError` 及模块名/spec 边界。逐补丁审计通过，
详见 [v10 结果](topic3-be-route-v2/HELDOUT_V10_RESULTS.md)。它与 v4 的 tqdm 分叉构成两个有效矩阵中的
两个不同家族收益，达到 Phase A，而非证明普遍有效或优于开源产品。

用户已明确删除自然验证路线。`PHASE_B_NATURAL_PROTOCOL.md`、registry、冻结工具、审计模板以及 runner 的
`natural` 模式和专用测试均从主线移除；此前的 0/10 不是产品成绩，不再进入摘要、门槛或下一步判断。本地
原始纠正记录不作为量化数据，也不阻塞公开数据和开源产品对照。

新的主线是：先在未运行的新公开样本上验证一个最简单的 update-aware 表示，提高当前 MemoryCode 冻结主
结果 7/10 所暴露的真实遗漏；同时保留公开仓库 2 胜 0 负 6 平及其独立家族计数。随后直接适配一个能在同一
Codex 任务上运行的开源项目记忆方案。公开质量、开源对照、安装／恢复／CI 闭包完成后发布 experimental
版本，再冻结质量下限，从 AI infra 角度优化非缓存 token、上下文字节、缓存复用、调用次数和 p95 时延。
