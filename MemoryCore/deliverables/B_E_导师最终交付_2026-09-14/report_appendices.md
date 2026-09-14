
---

# 9. 详细量化附录

本附录补充正文中不适合全部展开的协议、逐层指标和失效记录。不同数据集的分母、模型和任务不同，
所有结果分别报告，不合成为一个失真的“总准确率”。

## 9.1 MemoryCode 数据与全量检索

- Source commit：`1ab87e119b2f9a498de8075219e1c07f6041b394`
- Hugging Face revision：`32d888b11c73c67be91414e571dfe98c5c20feac`
- 规模：360 dialogues、8,400 sessions、4,426 次规则新增、2,913 次规则更新、4,182 个查询
- 检索：每个 dialogue 独立 SQLite，原始 session chunk，FTS5，固定 k=8，最新 session 强制保留

| Session 数 | 查询 | 最新来源 recall@8 | 更新查询 | stale-only |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 43 | 100.00% | 0 | — |
| 2 | 45 | 100.00% | 0 | — |
| 3 | 66 | 96.97% | 7 | 0.00% |
| 4 | 79 | 98.73% | 20 | 0.00% |
| 5 | 108 | 96.30% | 23 | 0.00% |
| 10 | 152 | 89.47% | 37 | 0.00% |
| 15 | 244 | 72.95% | 49 | 24.49% |
| 20 | 299 | 70.57% | 66 | 22.73% |
| 30 | 424 | 55.66% | 89 | 25.84% |
| 40 | 545 | 44.40% | 114 | 42.98% |
| 50 | 813 | 38.01% | 133 | 28.57% |
| 100 | 1,364 | 20.01% | 283 | 21.55% |
| **总计** | **4,182** | **45.89%** | **821** | **24.12%** |

更新查询最新来源 recall 为 46.77%，旧版本碰撞率为 61.39%。检索 mean/p50/p95 为
1.546/1.387/2.785 ms；短历史 recall 87.92%，长历史为 36.89%。这说明普通 top-8 在长历史和
版本更新上会漏证据，不能只靠增大 k 在已打开结果上追分。

## 9.2 MemoryCode 24-dialogue、72-call 三臂生成

模型为 Qwen3-4B-Instruct-2507，greedy，输入上限 65,536，输出上限 1,024；24 个 dialogue 覆盖全部
12 档历史长度，每档两个独立 cluster。

| Arm | Strict target | Official-compatible | Coverage | Input | Gen p50/p95 | 截断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full history | 3/24（12.50%） | 23.99% | 91.67% | 304,702 | 11.80/41.34s | 1 |
| MemoryCore top-8 | 4/24（16.67%） | 19.94% | 100.00% | 70,706 | 7.26/16.05s | 0 |
| Latest-rule oracle | 13/24（54.17%） | 65.85% | 95.83% | 5,701 | 9.09/24.67s | 1 |

top-8 对 full history 为 1 胜 0 负 23 平，bootstrap 95% `[0,0.125]`，sign `p=1.0`；输入为
full history 的 23.20%，但 official-compatible 为 3 胜 7 负 14 平。10 个 update 任务两条普通路径
均为 0%，oracle 为 50%，所以后续工作转向来源绑定和版本整理。

## 9.3 Codex 更新层与 focus

全部 10 个 update dialogue 的 Codex 运行使用 CLI 0.153.4、请求 `gpt-5.6-sol`、medium、空只读目录、
无工具与 web。20/20 调用有效。

| 指标 | No history | Full raw | 变化 |
| --- | ---: | ---: | ---: |
| Strict target | 0/10 | **7/10** | 7 胜 0 负 3 平 |
| Input | 116,270 | 256,448 | +120.56% |
| Non-cached input | 37,934 | 193,984 | +411.37% |
| Output | 4,879 | 11,150 | +128.53% |
| Wall | 180.223s | 273.357s | +51.68% |

质量差均值 +0.70，bootstrap `[+0.40,+1.00]`，sign `p=0.015625`。receiver-aware 事后敏感性为
9/10，但冻结主结果保留 7/10。

机制修正后的第二批零重叠 focus 确认：30/30 调用有效，receiver-aware target 由 9/10 到 10/10，
1 胜 0 负 9 平；active-rule mean 89.44%→97.00%，3 胜 0 负 7 平。主区间 `[0,0.30]`、sign `p=1.0`，
只能作为方向性证据。

| Focus 成本 | Raw full | Cold focus | Persisted coding stage |
| --- | ---: | ---: | ---: |
| Model calls | 10 | 20 | 10 |
| Non-cached input | 189,747 | 384,398（2.026x） | 208,938（1.101x） |
| Wall | 360.637s | 615.355s（1.706x） | 349.318s（0.969x） |

产品因此只采用“显式反馈写入时编译、精确 revision 持久复用”，不采用逐请求冷编译。

## 9.4 CUPID、ValidMem、Trigger、STALE

| 数据／任务 | 规模与结果 | 成本与边界 |
| --- | --- | --- |
| CUPID | 756 observations、252 personas；固定 4 personas/12 tasks/48 calls；feedback 对 frozen 为 3W/4L/5T，cluster mean −0.0833，CI `[-0.25,0]` | 输入 3.434x、+73,260；time 1.620x；负结果使默认编译关闭 |
| ValidMem v1.1 | 406-case 留出：374/406→387/406，15W/2L；Part B/EAR 147/176→159/176 | input +0.59%，wall +14.01%；batch sign `p=0.125`，只作生命周期方法验证 |
| Trigger Bench | 140-case 留出：full pass 112/140→130/140，21W/3L；specificity 62.12%→89.39% | 工具调用 −34.72%，input −7.76%，wall −3.56%；公开微任务结果 |
| STALE direct | 13/16，T2 1/4，负例 8/8 | 16 calls；太保守，关闭最终绑定 |
| STALE proposer+judge | 13/16，1W/1L/14T | 48 calls、455,788 input、303.180s；无净收益 |
| STALE candidate-only | 15/16，T1/T2 4/4，负例 7/8，引用错误 0 | 16 calls、228,302 input、171.741s；只授权候选提名，不授权失效 |

另 200 行 STALE candidate-universe 检索中，原始新 session 用户文本 BM25 recall@1/5/8/16/32 为
67.5%/90.5%/96.0%/98.0%/100%，T2 recall@8 为 94%；归一化 `M_new` 只有 61%/53%。

## 9.5 公开项目逐矩阵结果

有效 v4：packaging、Flask、tqdm、Uvicorn；24/24 调用完成、隔离 24/24、严重回归 0。Full raw 与
top-8 均 8/8，no-history 6/8；按首任务是 1 胜 0 负 3 平。tqdm 的关键历史要求是“忽略未知长度提示、
保留最小已知提示，只有全部未知时才用零”。

| v4 | No history | Full raw | Top-8 |
| --- | ---: | ---: | ---: |
| Total input | 2,919,958 | 2,039,342 | 2,190,824 |
| Non-cached input | 243,734 | 202,158 | 248,936 |
| Output | 31,169 | 27,409 | 29,413 |
| Wall | 956.214s | 837.074s | 870.874s |
| Context | 0 | 16,484B | 11,398B |

有效 v10：h2、pycodestyle、path、importlib_resources；16/16 调用与 checker 完成，42/42 preflight
符合预期，包含 18 个被拒绝 near-miss；隔离／额外路径／严重回归均 0。Full raw 8/8，no-history 6/8；
按首任务是 1 胜 0 负 3 平。importlib_resources 的历史提供了源码无法唯一确定的 `TypeError` 和诊断语义。

| v10 | No history | Full raw | 变化 |
| --- | ---: | ---: | ---: |
| Total input | 1,074,156 | 523,336 | −51.28% |
| Non-cached input | 189,548 | 81,480 | −57.01% |
| Output | 22,474 | 11,534 | −48.68% |
| Wall | 668.636s | 438.657s | −34.40% |
| Context | 0 | 17,322B | — |

合计按任务行为是 full raw 16/16、no-history 12/16；按独立项目家族首任务才是正式口径：
**2 胜 0 负 6 平**。两项后续控制失败继承首任务错误，不能重复算成四个胜例。

## 9.6 失效矩阵记录

| 矩阵 | 发起／计划 | 原因 | 处理 |
| --- | ---: | --- | --- |
| v5 | 16/16 | jsonschema no-history 两次 300s timeout，checker 未运行 | 缺失观察，不记 memory win |
| v6 | 2/16 | 首臂 timeout，配对臂人工取消 | partial edit 不补作正式完成 |
| v7 | 11/16 | 未强制 single-file edit scope | 行为通过不能覆盖额外文件回归 |
| v8 | 2/16 | Git porcelain 前导空格被 `.strip()` 删除 | runner 标签不可信，立即停止 |
| v9 | 16/16 | typeguard checker 接受条件顺序 near-miss | 整矩阵失效，新增 near-miss 标准 |

五轮 event、receipt、partial workspace 和复盘保留，但都不进入主成绩。这一部分是评测工作量的重要组成：
目标不是获得更多“胜利”，而是确保保留下来的每个胜例能经得住代码和协议审阅。

## 9.7 工程、fallback 与恢复

| 检查 | 结果 |
| --- | ---: |
| MemoryCore Vitest | 24 文件，204/204 |
| Python 项目代理 | 25/25 |
| Python 公共评测 | 31/31 |
| 主测试合计 | **260/260** |
| Node 22.19 memory-feedback | 5 文件，30/30 |
| Runtime 三臂逐字等价 | 20/20，模型调用 0 |
| npm pack | 376 文件，1,479,928 bytes，低于 2MiB |
| 空目录安装 smoke | CLI、子路径导出、SQLite 写读通过 |

Runtime contract 四例全部通过：`feature_off` 返回 baseline；正常选择 k=1；selector 强制失败返回
`selector_failed` 与原基线；over-k 返回 `invalid_selection` 与原基线。候选最大 256、k 1–32、timeout
最大 30s，adapter 不持有持久化写句柄。

容量恢复实跑：状态预填到 128 observations/revision 128；一次 Codex 调用仍取得 773-byte scoped context，
任务写入失败被标记为 `task_persisted=false`。编码 input 96,294（cached 88,192）、output 2,213、wall
63.256s；checker 被主动取消后，`check-run` 以 **0 次新模型调用**补跑通过，数据库仍保持 revision 128。

## 9.8 AI infra 最终结果

| 20 组轮换三臂 | Bridge 进程 | Mean | p50 | p95 |
| --- | ---: | ---: | ---: | ---: |
| Source/tsx 双调用 | 2 | 0.454s | 0.457s | 0.472s |
| Precompiled 双调用 | 2 | 0.323s | 0.329s | 0.336s |
| Precompiled one-shot | **1** | **0.245s** | **0.245s** | **0.253s** |

最终路径相对 source 双调用 mean/p95 降 46.1%/46.5%；相对最初四进程结构，进程数减少 75%。20/20
context 和最终 SQLite snapshot 逐字一致。该测量不包含模型、网络和 checker，不是生产 SLO。

# 10. 实现细节与代码工作量

## 10.1 核心数据合同

| 对象 | 字段 | 约束 |
| --- | --- | --- |
| Observation | id/order/role/text | ID≤256，text≤32k，order 单调；role=user/tool |
| Constraint | key/quote/scope/sourceId/supersedes | 单次≤4；quote≤4k 且在来源中唯一；更新指向同 key/scope 当前前任 |
| Scope | paths/actions | 1–16 路径；read/edit/test/build/install；拒绝绝对路径与 `..` |
| Snapshot | owner/project/revision/arrays | 默认容量 128，可配但≤1,024；规则≤容量×4 |
| Context | text/selectedIds/status/reason | 默认 12kB，合法 1–64kB；off/selected/fallback |

当前规则由 observation order、supersedes 与 retraction 决定。旧规则只以 `historical` 前任证据出现，
不会重新激活。损坏链、存储降级或预算无法完整容纳时不返回部分 selected ID。

## 10.2 执行与证据顺序

```text
校验 workspace/path/checker argv
→ 从同一 pre-task revision 读取 snapshot 与 context
→ 原子写 task.json，尝试 ingest 当前任务
→ 启动 Codex/Claude 进程组，实时写 stdout.jsonl/stderr
→ 原子写 agent-result.json 与 usage
→ 捕获相对 HEAD 的 changes.diff
→ 运行外置 checker 并保存原始输出
→ 写工具回执和最终 receipt
```

`task_persisted`、`receipt_persisted`、`memory_error` 分开记录。读取成功但任务写入失败时继续使用已取得
context；读取失败则退回当前请求。`check-run` 只恢复检查，不重复模型调用和记忆写入。

## 10.3 代码规模

从原始 MemoryCore 基线 `0ddea892f1e362b4b937b2b38d23beb2a5ac4329` 到实现快照 `84ba04d`：
**166 个文件，+21,878/−83 行**。B+E runtime 与项目代理主要实现 10 文件、2,368 行；聚焦测试 15 文件、
2,158 行；公开评测、数据准备和 checker 源码 50 文件、8,973 行。最终产品化 PR 相对研究分支为
41 文件、+3,855/−1,088 行。

# 11. 结论边界与最终判断

可以确认：完整原话是当前最可靠的证据保留基线；普通 top-8 在长历史更新上会漏掉最新来源；强模型能够
利用版本历史；范围、版本链、撤销、fallback 和执行证据已经形成可运行系统；项目历史在两个不同公开项目
中解决了源码无法唯一确定的维护选择；模型前固定开销已经在等价条件下降低约 46%。

不能确认：普遍优于 Codex、Claude Code 或开源记忆系统；公开结果等同内部真实业务；候选提名可以自动
失效；编译规则已获得稳定反馈学习收益；单次成本下降可直接外推为生产 SLO。Claude Code 诊断连续 502，
没有质量样本，服务失败未计作质量失败。

最终结论是：**本项目完成了一套面向编码代理的可演化项目记忆方案，并在公开长对话和公开仓库任务上
验证了有效机制、失败边界和工程可交付性。** 它已经适合作为实验版和可审阅研究交付；扩大默认启用前，
仍需更大规模新项目、同任务开源方案对照以及内部多轮编程数据复核。

# 12. 复现与移植

零模型复现命令：

```bash
cd MemoryCore
npm install --ignore-scripts --legacy-peer-deps
python3 -m pip install -r scripts/project-agent/requirements-dev.txt
npm run lint:project-agent
npm test
npm run test:project-agent
npm run test:agent-product
npm run build
npm pack
bash scripts/ci/smoke-memory-agent-package.sh ./*.tgz
```

内部数据只需替换 adapter、标签和 checker，主状态机与运行回执保持不变。内部记录至少需要 owner/project/
session/turn、user/tool role、exact text、repo/branch/environment、path/symbol/action、source/supersedes/retract、
base commit/diff、backend/model/usage 和外置 checker。公开数据中的“最新值全局有效”不能直接移植到多分支环境。

# 13. 参考资料

1. TencentCloud, *TencentDB Agent Memory / MemoryCore v2.0.0-beta.1*.
2. Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning*, 2023.
3. Maharana et al., *LoCoMo*, ACL 2024.
4. Wu et al., *LongMemEval*, 2024.
5. Mem0, *Building Production-Ready AI Agents with Scalable Long-Term Memory*, 2025.
6. Rasmussen et al., *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*, 2025.
7. Cohere Labs Community, *MemoryCode*.
8. Zhou et al., *ValidMem / MemFSM*.
9. *Agent Memory Trigger Bench*.
10. *STALE: A Benchmark for Stale Memory in Long-Context Agents*.

---

本文所有“通过”均对应明确协议和分母。开发结果、失效矩阵、事后敏感性和主结果分开标记；未用未完成
调用补数，也未把外部论文成绩记作本项目成绩。
