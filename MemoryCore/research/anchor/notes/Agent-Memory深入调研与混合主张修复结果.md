# Agent Memory 深入调研与混合主张修复结果

日期：2026-09-07

## 先说结论

这轮补上了一个真实缺口：弱模型有时会把“业务事实”和“本次回复格式”写进同一条长期
记忆。旧版只能拦住独立的错误 instruction，拦不住 episodic 正文里的格式片段。

新版会回到候选引用的用户原文，把能够独立成句的事实写入 L1，把一次性回复格式留在 L0。
句子无法安全拆开时，候选进入 quarantine，等待复核。整个处理不调用模型。

结果分三层：

| 检查 | 结果 |
|---|---:|
| 14 个新来源模板组件检查 | 动作 14/14，内容 14/14，旧格式残留 0 |
| 旧 r1 真实 Qwen 混合候选只读重放 | 格式残留 1→0，3/3 业务事实保留 |
| 新 r2 本地 Qwen 端到端两臂 | 调整臂 exact 4/4，普通臂 2/4；语义事实均 4/4；严重回归 0 |
| r2 全生命周期 token | 13,995→13,578，减少 417（2.98%） |
| 仓库测试与构建 | Vitest 202/202；插件构建通过 |

端到端只有两个业务来源，每臂各重复两次。这个样本足以做开发验收，还不足以给出统计
泛化结论。

## 还有哪些团队在长期记忆上投入较深

公开资料里，值得持续跟踪的实现可以分成三组。

### 已经商业化的产品和云服务

| 系统 | 公开做法 | 对本项目有用的部分 |
|---|---|---|
| Anthropic Claude | 记忆按 topic 保存；项目拥有独立记忆空间；用户可编辑、删除或暂停。Claude Code 还把自动记忆放在项目目录，长期规则可落到团队维护的 `CLAUDE.md`。 | 项目隔离、可见可改、行为规则与项目资料分开管理。公开资料没有披露内部接纳算法。 |
| OpenAI ChatGPT | 维护可更新的 memory summary；Project-only memory 限制跨项目读取；用户可以管理记忆。 | 作用域和用户控制应放在存储与读取层，不能只靠提示词提醒模型。公开资料没有给出候选核验细节。 |
| Google Vertex AI Memory Bank | 后台从会话抽取并整理记忆；按 scope 管理；可设置 memory topics、few-shot、生成模型、向量模型和 TTL；新信息可触发合并与冲突更新。 | 写入异步化、主题白名单、TTL、按 scope 定制抽取。 |
| AWS Bedrock AgentCore Memory | 明确区分偏好、语义事实、会话摘要和 episodic；处理链包含 extraction、consolidation、reflection；actor/session/namespace 可配，并提示 memory poisoning 风险。 | 记忆类型分层、后台合并、命名空间和安全边界。 |

资料入口：[Claude memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)、
[Claude Code memory](https://support.claude.com/en/articles/14554000-claude-code-power-user-tips)、
[OpenAI Memory FAQ](https://help.openai.com/en/articles/8590148-memory-and-projects)、
[OpenAI Projects](https://help.openai.com/en/articles/10169521-using-projects-in-chatgpt-496)、
[Google Memory Bank 配置](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/set-up)、
[AWS 内置策略](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-configuring-built-in-strategies.html)、
[AWS 记忆组织](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-organization.html)。

### 专门做 Memory 基础设施的团队

| 系统 | 公开做法 | 可借鉴点 |
|---|---|---|
| Mem0 | user、agent、run 等 scope；异步写入；update/delete/history API。 | 把归属、版本历史和写入成本作为基础能力。 |
| Zep / Graphiti | episode 保存来源；事实边带 `valid_at`、`invalid_at`；新事实可使旧边失效；图检索结合语义和关键词。 | 原始事件与可用事实分开，旧事实保留历史并退出当前召回。 |
| Hindsight | 原始 fact 上生成 observation；保留支持文本、证明数量、历史和 freshness；后台刷新 mental model。 | 派生结论必须能回到证据，更新时保留来源和时间。 |
| Letta / MemGPT | core memory 常驻上下文，archival memory 按需读取；新版本采用文件化和分层加载。 | 少量规则常驻，大体量历史按需取，直接降低上下文税。 |

资料入口：[Mem0 async memory](https://docs.mem0.ai/open-source/features/async-memory)、
[Mem0 update](https://docs.mem0.ai/core-concepts/memory-operations/update)、
[Graphiti overview](https://help.getzep.com/graphiti/getting-started/overview)、
[Hindsight observations](https://hindsight.vectorize.io/0.6/developer/observations)、
[Letta memory architecture](https://github.com/letta-ai/skills/blob/main/letta/letta-api-client/memory-architecture.md)。

### 框架和研究实现

LangGraph 把长期记忆分成 semantic、episodic、procedural 三类，并讨论 profile 与原子记录
集合的取舍、在线写入与后台写入的成本差异。A-MEM 用结构化 note、标签、链接和 memory
evolution 组织经验，适合研究记忆之间的关系，但其主流程仍依赖模型。

资料入口：[LangGraph memory overview](https://docs.langchain.com/oss/python/concepts/memory)、
[A-MEM](https://github.com/agiresearch/A-mem)。

## 这次具体借了什么

各家产品细节不同，公开设计有四个稳定共识：

1. 原始会话或 episode 要留底，后续结论能追溯来源。
2. 事实、经历和行为规则应分开存放和激活。
3. user、project、session、agent 等作用域要进入数据模型。
4. 长期记忆需要更新、失效、历史和用户控制，不能只有 append。

本轮把前两点落实到现有 TDAI Memory：

```text
L0 用户原文
  └─ Qwen 生成 L1 候选并引用 source_message_ids
       └─ evidence_scoped_v1 检查候选
            ├─ 纯事实：照常写入
            ├─ 事实 + 本次回复格式，且原文可分句：从原文投影事实
            └─ 混在同一句，无法可靠拆分：quarantine
```

这里有两个工程选择：

- 投影内容直接取自用户原文，避免规则系统自己改写事实。
- 只处理带临时范围和回复指令的窄场景。业务描述里的“API 输出格式改为 JSON”保持原样。

实现位于 `src/core/self-supervision/evidence-scoped-admission.ts`。中英文、不可拆分和误报反例
位于同名测试文件。

## 实验结果

### 1. 新来源模板组件检查

14 个模板均未沿用旧实验的实体名或格式标记：8 个可安全投影、2 个必须隔离、4 个应保持
原样。结果如下：

| 指标 | 数值 |
|---|---:|
| 动作判断正确 | 14/14 |
| 最终内容正确 | 14/14 |
| 需处理的格式片段 | 10 |
| 处理后仍在活跃记忆中的格式片段 | 0 |
| 模型调用 / token | 0 / 0 |
| 本机执行时间 | 16.8ms |

这是手工构造的确定性反例测试，主要检查边界和回归，不计作盲测。

### 2. 旧真实候选重放

r1 保存了一条真实 Qwen3-4B 候选，其中同时包含 Boreal 生产限制、预发布试点、截止日期和
`REVIEW|...` 回复格式。新版直接读取当时保存的 candidate 与 source，未重新调用模型。

| 项目 | 旧审核 | 新审核 |
|---|---|---|
| 活跃记录数 | 1 | 1 |
| 带 `REVIEW|...` 的活跃记录 | 1 | 0 |
| 三项业务事实 | 保留 | 3/3 保留 |
| 最终事实语言 | Qwen 改写的中文 | 来源英文 |

该重放证明新逻辑能修掉已经出现过的 mixed fact/behavior 问题。

### 3. 新端到端两臂

本地 Qwen3-4B 重新执行 Vendor Boreal 和 Aurora Window 两类来源。每类都有普通抽取和
审核抽取，后续任务按 AB/BA 各跑两次。

| 指标 | 普通臂 | 审核臂 |
|---|---:|---:|
| 精确输出 | 2/4 | 4/4 |
| 语义事实正确 | 4/4 | 4/4 |
| 严重回归 | 0 | 0 |
| 目标 token | 10,130 | 9,738（-3.87%） |
| 全生命周期 token | 13,995 | 13,578（-2.98%） |
| 全生命周期调用 | 8 | 8 |
| 活跃记忆完全不含旧格式 | — | 2/2 来源 |

普通臂两次 Aurora 任务都照搬了历史 `WINDOW|...`，没有遵守当前任务要求的 `MAINT|...`。
审核臂两次都输出正确。两臂的日期和起止时间都对，差异集中在旧行为格式对当前行动的
干扰。

r2 的 Qwen episodic 本身较干净，所以新投影分支没有在这次新抽取中触发；端到端收益主要
来自已有的 instruction 范围审核。投影分支的真实证据来自上一节的 r1 只读重放。两种证据
需要分开解释。

## 成本判断

这次新增逻辑为字符串和来源句子检查，线上模型调用增加 0。调整臂少写一条错误 instruction，
后续任务上下文缩短约 3.9%，全生命周期 token 下降约 3.0%。

Google、AWS、Mem0 等方案通常用模型做后台抽取或合并，能力上限更高，也会带来推理费用。
当前实现适合先覆盖高频、证据清楚的范围错误；冲突消解、跨句归纳和复杂更新继续走异步
模型升级。这样能把 GPU 成本集中到规则无法确定的少数候选。

## 当前边界和下一步

- 端到端只有 2 个来源、4 个目标结果，重复运行采用固定温度和种子，不提供独立统计样本。
- 组件模板有 14 个，覆盖中英文、混合语言、可拆分、不可拆分和格式误报，仍属于开发期
  手工反例集。
- 句子级投影会保守丢弃和临时格式写在同一句里的业务信息。这类候选进入 review queue，
  L0 原文仍完整保存。
- 下一轮应增加至少 8 个真实抽取来源，覆盖撤回、事实更新、多个 source、引用顺序和 TTL。
  端到端指标继续看 exact、语义事实、错误激活、严重回归、token 和 unknown 数量。
- 生产 Memory 保持关闭，本轮没有写入、删除或降权任何生产记录。

## 复现入口

- 组件结果：`mixed-claim-projection-result.v1.json`
- 旧候选重放：`r1-mixed-claim-replay-result.v1.json`
- 端到端机器结果：`.local-evidence/mainline-2026-09-07/feedback-cross-family-r2/result.json`
- 端到端完整 trace：`.local-evidence/mainline-2026-09-07/feedback-cross-family-r2/`
- Qwen receipts：`.local-evidence/mainline-2026-09-07/feedback-cross-family-r2-qwen-receipts.jsonl`
