# B+E 项目记忆编码系统：方案介绍与测试结论（最终上交版）

日期：2026-09-14
交付分支：`delivery/topic3-be-project-memory-v1`
代码审阅：<https://github.com/newmancai/TencentDB-Agent-Memory/pull/4>
交付定位：可运行、可安装、可测试的实验产品切片；不是已证明普遍优于现有编码代理的正式产品。

## 摘要

本方案面向“用户已经纠正过一次，编码代理在后续相关任务中仍重复犯错”的问题，将 B（反馈记忆）
和 E（编码执行与证据闭环）实现为一个可安装的项目记忆 CLI。B 默认无损保存用户原话和出处，按项目、
路径、动作、版本链和显式撤销控制适用范围；E 将上下文读取、Codex／Claude Code 调用、独立 checker、
原始事件、usage、耗时和工作区差异保存为可审阅回执，并支持编码完成后的检查恢复。

工程交付已经闭环：实现代码、测试代码、安装入口、格式门禁、完整 MemoryCore 回归、最低 Node 版本验证、
打包后空目录安装 smoke 和本报告均已纳入同一 PR。受控公开仓库任务中，完整原话记忆在 8 个独立项目
家族的首任务上得到 2 胜 0 负 6 平，解决了两个仅靠当前源码不能唯一确定的维护决策；但自然使用前瞻
登记仍为 0/10，且尚未运行外部开源记忆系统的同条件对照。公开 MemoryCode 的完整 10 项更新层上，
Codex 使用完整原话历史得到 7/10、无历史 0/10；事后接收者感知敏感性为 9/10，但冻结主结果保持 7/10，
且非缓存输入增加 411.37%。因此，当前能够支持的是“无损项目历史是一条值得继续验证、且已有窄范围
行为收益的路线”，不能支持“已普遍优于 Codex、Claude Code 或某个开源方案”。

## 1. 最终上交材料

| 要求 | 本次交付 | 状态 |
| --- | --- | --- |
| 方案实现代码 | TypeScript 项目记忆状态机、SQLite 接口、Python 执行宿主、Codex／Claude 后端、差异捕获、安装 CLI | 完成 |
| 测试代码 | TypeScript 单元／集成测试、Python 宿主／后端／差异测试、公共评测器测试、安装包 smoke、GitHub Actions | 完成 |
| 方案介绍＋测试结论报告 | 本文；同时给出方案边界、量化结果、复现命令和不能宣称的结论 | 完成 |

代码可读性专项复盘见
[`B_E_CODE_READABILITY_REVIEW_2026-09-14.md`](B_E_CODE_READABILITY_REVIEW_2026-09-14.md)。
CLI 的用户与维护说明见
[`scripts/project-agent/README.md`](../scripts/project-agent/README.md)。本文是给导师提交时应优先阅读的
单一总报告，前两份作为实现附录。

## 2. 问题定义与目标

普通编码代理通常能读取当前请求和仓库，但项目决策可能只存在于早先的用户纠正、review 意见或例外
说明中。直接把全部历史塞入 prompt 会增加成本，也可能把旧要求错误应用到新目录；把原话自动总结成
规则又可能丢失限定条件。方案需要同时回答：

1. 哪条反馈应保存，出处是什么；
2. 它对哪个项目、路径和动作生效；
3. 新要求出现后，旧要求如何保留但不再作为当前规则；
4. 编码结果是否真的通过独立行为检查；
5. 失败、中断或读取异常时，系统是否留下可审计证据并安全退回。

本项目不把“保存了记忆”当作效果，也不把 checker 通过自动解释为某条记忆正确。评价重点是后续行为的
配对胜负、同主题控制回归、上下文与模型成本，以及证据能否复核。

## 3. 方案设计

### 3.1 B：反馈记忆

- **默认无损。** `remember` 保存完整用户原话，不调用模型，不把自动摘要当作真值。
- **来源可追踪。** 观察和实验性约束使用确定性 ID，约束必须引用实际存在的原文片段。
- **范围明确。** owner、project、动作和路径共同决定可见性，另一项目或不重叠路径不会共享规则。
- **非法范围失败关闭。** 非规范路径、动作或预算在读取记忆和调用模型前拒绝，不会回退成更宽的原话历史。
- **更新可逆。** 新规则只有显式绑定同范围前任时才建立 `supersedes` 链；历史引文仍可查看，但不会重新
  变成当前规则。`retract` 只做显式撤销。
- **结构化编译非默认。** `remember --compile` 最多提议四条带引用约束；来源、容量或格式校验失败时，
  不写入部分规则，只保留原话。引用合法不等于语义一定正确，因此该功能保持实验状态。
- **三种对照模式。** `scoped` 使用范围化视图，`raw` 读取同项目原话，`off` 完全绕过本工具的记忆读写。

### 3.2 E：执行与证据闭环

运行链路保持单向，各层只负责一种问题：

```text
memory-agent
  -> project_agent.py（命令编排、持久化回执、恢复）
     -> backend.py（Codex／Claude CLI、事件流和进程生命周期）
     -> store.ts -> ProjectMemory（SQLite、范围、版本与谱系）
     -> changes.py（相对 HEAD 的可审阅差异）
     -> 独立 checker（行为结果，不充当用户反馈）
```

每次 `run` 在模型调用前保存任务，在编码完成后保存 agent 完成记录，再执行 argv 形式的 checker；提示、
上下文、原始 backend 事件、usage、输出、检查结果和 `changes.diff` 分开保存。超时或 Ctrl-C 会终止本次
进程组并保留 partial evidence。若编码已确认完成而检查中断，`check-run` 可在不再次调用模型、不写入
新记忆的前提下补跑检查；人工检查未完成 diff 后也可显式使用 `--allow-incomplete`，回执会继续标记
`completion_confirmed=false`。

读取失败时，编码任务退回当前请求并记录原因；读取成功但后续写回失败时，已读取上下文仍可使用，
`task_persisted`、`receipt_persisted` 和 `memory_error` 分开记录。系统不会把“空状态”和“存储失败”混为
一谈。

### 3.3 当前边界

- SQLite 单写者，CLI 文件锁只协调同一状态目录；没有多设备同步或后台归档。
- 默认最多 128 条观察；一次普通 `run` 通常使用任务和工具回执两条，容量满后仍可读旧上下文，但不能
  假装新任务已持久化。
- scoped 预算不足时回退完整原话而不静默裁切，因此上下文可能超过目标字节预算。
- `changes.diff` 相对当前 HEAD，可能包含用户已有编辑；它是审阅材料，不是模型归因证明。
- 未自动接入 Gateway，未发布新的 npm 正式版本，也未实现自动语义纠错。

## 4. 实现与测试代码清单

### 4.1 主要实现

| 路径 | 职责 |
| --- | --- |
| `src/core/memory-feedback/project-memory.ts` | 项目记忆状态机、校验、范围、版本链、撤销与上下文视图 |
| `src/core/memory-feedback/index.ts` | 明确导出的项目记忆 API 与类型 |
| `src/core/store/sqlite.ts`、`types.ts` | 原生 SQLite 精确记录能力与存储合同 |
| `scripts/project-agent/project_agent.py` | remember／context／run／history／retract／check-run 编排 |
| `scripts/project-agent/backend.py` | Codex／Claude CLI、实时 JSONL、usage、超时与取消 |
| `scripts/project-agent/changes.py` | 已跟踪和普通新文件的有界差异捕获 |
| `scripts/project-agent/store.ts` | Python 到 MemoryCore SQLite 的 JSON 桥接 |
| `bin/memory-agent.mjs` | 安装后统一命令入口与运行时定位 |

### 4.2 主要测试

| 路径 | 覆盖重点 |
| --- | --- |
| `src/core/memory-feedback/project-memory.test.ts` | 来源校验、隔离、范围、更新链、损坏链、撤销、容量和 fallback |
| `scripts/project-agent/test_project_agent.py` | CLI 流程、回执、错误边界、恢复与读写失败语义 |
| `scripts/project-agent/test_backend.py` | 后端命令、实时日志、超时、取消、进程组终止和 usage |
| `scripts/project-agent/test_changes.py` | 已有／新增文件差异、符号链接、容量和遗漏原因 |
| `benchmarks/topic3-be-agent-product-v1/test_*.py` | runner 隔离合同、公共结果聚合、MemoryCode 评分和证据对齐 |
| `scripts/ci/smoke-memory-agent-package.sh` | 从生成 tarball 安装后的入口、子路径导出及 remember→context→history |
| `.github/workflows/pr-ci.yml` | 全量／最低版本测试、格式、构建、打包、尺寸、manifest 和隔离门禁 |

## 5. 测试方法

### 5.1 工程验证

工程测试分为状态机、宿主、公共评测工具、完整仓库回归、最低支持版本和最终安装包六层。单元测试避免
网络和真实模型调用；安装 smoke 在空消费者目录中从 `.tgz` 安装，防止只在源码工作区可运行。GitHub
Actions 对 PR 的每个新 head 重跑相同门禁。

### 5.2 效果验证

效果实验只接受固定任务、相同 base commit、arm 间文件系统隔离、禁用 web search、独立行为 checker、
完整事件和 usage 的配对运行。累计顺序任务的第二项失败可能继承第一项代码，因此产品胜负按项目家族的
首个必要任务计数，不能把一次初始修复重复算成多个独立胜利。

已发现未来 Git ref、兄弟 arm 路径、联网搜索和过度依赖源码字面形式等污染的矩阵全部作废；只有通过
隔离扫描和等价／near-miss 预检的 v4 与 v10 纳入最终行为结论。这样减少了可报告样本，但避免把明显
不正常的结果继续包装为进展。

## 6. 测试结果

### 6.1 最终工程结果

| 检查 | 结果 |
| --- | ---: |
| MemoryCore Node 24 全量 Vitest | 24 个文件，204/204 通过 |
| Python 项目代理 | 19/19 通过 |
| Python 公共评测／runner | 12/12 通过 |
| 最低 Node 22.19 反馈模块 | 5 个文件，30/30 通过 |
| Black 25.1.0＋Prettier 3.5.3 | 通过 |
| `npm run build` | 通过 |
| 生成包 | 373 个文件，1,477,201 bytes，低于 2 MiB 门禁 |
| 空目录安装后的 CLI／SQLite／子路径 smoke | 通过 |
| Python 编译、shell 语法、`git diff --check` | 通过 |

本轮终检曾真实发现公共评测测试夹具缺少现行回执协议的 `shard`、模型和解码字段；最终修复是补全合法
回执，并将公共评测测试加入 CI，而不是让评分器静默接纳不完整证据。随后又加入跨回执模型／解码／
token 限额一致性断言；12 项测试全部通过，原 72 条模型回执重算结果逐字段不变。这一失败不影响既有
模型成绩，但说明
最终提交前运行分散测试套件是必要的。

### 6.2 受控公开仓库编码任务

| 有效矩阵 | 独立项目家族 | Full raw | No history | 首任务家族胜负 | 严重回归 |
| --- | --- | ---: | ---: | ---: | ---: |
| held-out v4 | packaging、Flask、tqdm、Uvicorn | 8/8 | 6/8 | 1 胜 0 负 3 平 | 0 |
| held-out v10 | h2、pycodestyle、path、importlib_resources | 8/8 | 6/8 | 1 胜 0 负 3 平 | 0 |
| 合计（按独立家族首任务） | 8 个家族 | — | — | **2 胜 0 负 6 平** | **0** |

两个有效收益都属于“当前代码和通用常识不能唯一确定维护者选择”的情况：tqdm 需要保留已知长度提示、
忽略未知提示；importlib_resources 需要采用指定异常类型及诊断语义。完整原话给出了决定性历史，
no-history 选择了合理但不被项目接受的另一实现。

成本只各运行一次，不能作为稳定性能结论：v4 中 full raw 相比 no-history 的总输入、非缓存输入和墙钟
分别低 30.16%、17.06%、12.46%；v10 分别低 51.28%、57.01%、34.40%。这更可能反映明确历史减少了
代理探索和推理，不代表“增加上下文必然省成本”。v4 的 raw top-8 虽同样 8/8 且少注入 30.86% 上下文，
却比 full raw 多用 7.43% 总输入、23.14% 非缓存输入和 4.04% 墙钟，因此该检索优化没有升为默认。

### 6.3 公共数据集与组件研究

下列协议的任务、模型和指标不同，不能相加成一个“总准确率”；它们用于定位机制边界。

| 数据／任务 | 量化结果 | 支持的结论 |
| --- | --- | --- |
| MemoryCode 全量检索 | 360 对话、4,182 查询；最新来源 recall@8 45.89%，100-session 为 20.01%；更新题 stale-only 24.12% | 固定 top-8 在长历史和版本更新上会漏证据 |
| MemoryCode 冻结生成 | 24 对话、72 调用；full history strict 12.50%，FTS 16.67%，1 胜 0 负 23 平；10 个更新题两者均 0% | 小模型下普通检索没有高置信质量收益 |
| MemoryCode Codex 完整更新层 | 固定全部 10 个更新 dialogue、20/20 调用有效；full raw 7/10，no history 0/10，即 7 胜 0 负 3 平；bootstrap 95% `[+0.40,+1.00]`，sign `p=0.015625` | Codex 能从原话历史恢复多数更新约定；这是公开开发数据的方法诊断，不是自然／产品成绩 |
| CUPID 纠正 ICL | 相比普通历史 3 胜 4 负 5 平，输入 3.434 倍 | 当前规则／画像式反馈学习无稳定净收益 |
| ValidMem 生命周期 | 374/406→387/406，15 胜 2 负；batch sign p=0.125 | 支持来源绑定与生命周期方法，不能当编码收益 |
| Trigger 微任务 | 112/140→130/140，21 胜 3 负 | 能减少无关记忆操作；同源场景簇限制外推 |
| STALE 候选提名 | 直接绑定和提议＋裁决均 13/16；独立 candidate-only 15/16 | 只支持候选提名，不支持自动失效／持久化 |

MemoryCode 详细的已提交结果见
[`topic3-be-agent-product-v1/MEMORYCODE_RESULTS.md`](topic3-be-agent-product-v1/MEMORYCODE_RESULTS.md)。
完整更新层的 3 项冻结平局中，两项来自 attribute 提取器只识别字面 `self`：对应输出实际使用了
满足目标后缀的构造器属性，同时遵守另一条“重命名 receiver”的历史约定。接收者感知的 AST 事后
敏感性为 9/10，真实目标遗漏保留 1 项；因为输出可见后才加入该分析，所以 9/10 只作次级解释，不能
替换 7/10 主结论。full raw 相比 no history 的总输入、非缓存输入和墙钟分别增加 120.56%、411.37%
和 51.68%，明确暴露了直接注入完整历史的效率代价。

有效公开仓库矩阵和 Codex 诊断的协议、回执哈希与原始证据保存在研究分支
`delivery/topic3-be-product-v1` 及本机 `.local-evidence/` 归档；它们没有复制进本产品 PR，以免把大量
生成产物混入方案实现代码审阅。

### 6.4 明确未完成的效果结论

- 自然使用 Phase B 前瞻登记为 **0/10**：虽已记录真实纠正，但尚未自然出现符合冻结条件的后续任务。
- 尚未选择并运行外部开源项目记忆方案的同任务、同模型对照。
- Claude Code 在早期服务诊断中连续返回 502，没有形成可评分结果；服务失败没有计作质量失败。
- Codex CLI 记录请求模型与 usage，但不能独立确认服务端实际模型身份或账户美元费用。
- 因此不能声称自然用户收益、总体成功率、商业可用性，或优于 Codex／Claude Code／开源系统。

## 7. 复现工程测试

以下命令不调用模型：

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

最低 Node 验证应使用 Node 22.19.0 运行：

```bash
npx vitest run src/core/memory-feedback
```

真实模型实验不会包含在普通测试命令中。它需要独立 worktree、已登录的 backend、冻结 manifest 和 checker，
应按对应协议显式启动，不能把 smoke、旧工作区或已暴露任务重新包装成新留出。

## 8. 最终结论

本次交付已满足“方案实现代码＋测试代码＋一份方案介绍与测试结论报告”的材料要求。实现不是只有研究
脚本：它有安装入口、明确 API、持久状态、故障语义、恢复路径、审阅证据、最低运行版本和 CI 门禁；
测试也覆盖正常路径、失败路径、安装后路径和公共评测证据对齐。

研究结论保持克制：完整原话项目记忆在严格隔离的公开仓库任务上得到两个独立家族收益、没有家族首任务
损失，说明路线并非纯粹外围工程；Codex 在 MemoryCode 完整更新层上的 7/10 主结果进一步证明强模型
确实能利用原话历史，但同时付出显著上下文成本。6/8 仓库家族仍然打平，长历史检索、自然使用与开源
系统对照尚未完成。最合适的成果表述是：**已完成一个高质量、可复核的 B+E 实验产品交付，并证明无损
项目历史在部分欠定维护决策和公开更新任务中有实际作用；高效、稳定、普适收益仍是后续研究问题。**
