# 商业 Agent 记忆系统对标与 AI Infra 路线

状态：`ARCHITECTURE_REVIEWED / ZERO_LLM_SLICE_IMPLEMENTED / DEVELOPMENT_SCREEN_ONLY / NO_PRODUCTION_ACTION`

## 结论

本项目的核心对标对象是头部产品采用的记忆控制面，单独比较“Codex 对 48 条候选的分类
分数”信息量有限。控制面需要：**把原始经历、可检索事实和可主动改变行为的规则分开；让 scope、触发、预算、
审计和硬约束由宿主管理；把昂贵语义综合移出每次写入的同步关键路径。**

这条路线有明确商业背书，但没有任何公开材料证明“纯规则即可解决通用记忆语义判断”。
相反，一手资料显示商业系统保留模型综合或 sidecar，同时通过显式用户控制、项目/路径作用域、
索引按需读取、后台处理和客户端硬约束限制其风险与成本。因此本项目采用两层结论：

1. 无大模型层可以高精度处理显式耐久性、临时范围、否定/撤回、原文绑定和明显实体冲突；
2. 含蓄偏好、跨句蕴含、复杂改写和冲突消解不能由词表冒充通用语义能力，必须保持 unknown，
   再异步路由小模型或强模型。

## 公开商业实现怎么做

| 产品 | 公开机制 | 对本项目的直接启示 |
|---|---|---|
| ChatGPT Memory / Dreaming | saved memory 与历史综合并存；后台综合多段会话，显式评测“延续上下文、遵循偏好、随时间保持最新”；结果可由用户审阅、更新；新版 serving compute 约降 5 倍 | 不把一次会话等同永久真相；时间是记忆状态的一部分；后台综合与在线使用分离；算力本身是产品指标 |
| Codex | 长任务依赖 compaction；稳定前缀和确定性工具顺序保护 prompt cache；配置变化追加而非改写前缀；大资源放文件系统并按需读取 | 常驻短索引、细节外置；测 cache hit/prefix churn；不要把全部历史塞进每轮 prompt |
| Claude Code | 显式 `CLAUDE.md`/Rules 与 auto memory 分开；auto memory 分 user/feedback/project/reference，跳过代码库可推导内容；按 git repo 隔离；`MEMORY.md` 只常载前 200 行/25KB，topic 文件按需读 | 权威层与自动层分开；机器可重算事实不重复记；repo/path scope 是数据结构，不靠模型猜；索引常驻、正文按需 |
| Claude Platform | context editing 清旧 tool result，memory tool 将文件放在客户基础设施；官方内部 agentic search 报告组合提升 39%，100-turn 搜索 token 降 84% | “记忆质量”和“上下文清理”共同优化；storage/client control 与模型解耦；token 降幅应进入主指标 |
| Cursor | 自动 memory 由 sidecar 模型观察会话生成，后台候选需用户批准才保存；memory 限定 project | 高风险自动写入不必同步阻塞主模型；候选与正式规则之间可以有人审/异步批准边界 |
| Devin | Knowledge 必须有 trigger description；按相关性召回；单条可启停；从反馈产生的是可编辑/可拒绝 suggestion | “建议”不是“已生效记忆”；trigger 是一等字段；禁用可保留内容而不让其参与行为 |
| Windsurf | 自动 memory 绑定 workspace、本机保存、按相关性召回；更耐久/共享的内容转为 Rule 或 `AGENTS.md`；自动 memory 不消耗产品额度 | 自动记忆与组织级规则分权；本地异步处理可把用户侧边际费用压到零；workspace scope 默认隔离 |
| Gemini CLI | global/project/subdirectory 分层 `GEMINI.md`；显式 `/memory add`；可查看完整加载上下文；长会话到阈值自动压缩 | 层级 scope 可无模型实现；显式保存路径应极便宜；上下文 token 水位触发压缩而非每轮综合 |

主要一手来源：

- OpenAI：[Dreaming memory](https://openai.com/index/chatgpt-memory-dreaming/)、
  [Memory FAQ](https://help.openai.com/en/articles/8590148-memory-faq/)、
  [Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
- Anthropic：[Claude Code memory](https://code.claude.com/docs/en/memory)、
  [context editing + memory tool](https://claude.com/blog/context-management)
- 其他产品：[Cursor Memories](https://docs.cursor.com/en/context/memories)、
  [Devin Knowledge](https://docs.devin.ai/product-guides/knowledge)、
  [Windsurf Memories & Rules](https://docs.windsurf.com/zh/windsurf/cascade/memories)、
  [Gemini CLI hierarchical memory](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html)

公开资料不能回答各家内部 extractor 模型、训练数据、阈值和完整线上误报率；本报告不对这些
未公开部分作反向推断。

## 对 MemoryCore 的落地映射

新的控制面采用三态设计，单一二分类器难以覆盖风险边界：

| 层 | 保存 | 是否主动影响行为 | 默认成本 |
|---|---|---|---|
| L0 原始证据 | 保留 | 否；仅回查 | 写盘/索引 |
| retrievable fact/event | 机械支持时保留 | 仅相关检索后作为事实上下文 | 检索与少量 prompt token |
| active behavior rule | 只有直接用户权威、明确跨任务 scope、内容机械支持才激活 | 是；仍受 project/path/time condition 限制 | 常驻短索引或条件命中注入 |
| unknown/quarantine | 候选和证据可审计保留 | 否 | 异步小模型；高风险/低置信再强模型 |

硬权限、工具禁用、执行成功判据继续由 host gate 实现，不把自然语言记忆当安全执行层。
复杂 update/merge 仍保持 deferred。当前实现完全默认关闭，不接 production Memory。

## 无大模型开发切片

新增 `tiered-memory-admission.ts`：在最终草稿上检查完整 source binding、用户权威、消息真实
顺序、显式 durable/temporary/not-adopted 状态和内容 token grounding，并输出独立的
`storageDisposition`、`activation`、`validity`、`semanticEscalation`。原始 L0 是否保存不由
该函数否决。

| 输入 | disposition | validity | 错误激活 | 有用保留 | 升级 | 模型成本 |
|---|---:|---:|---:|---:|---:|---:|
| v4 同窗口开发筛查 | 48/48 | 46/48 | 0/24 | 24/24 | 5/48 | 0 calls / 0 tokens / 约 5.7ms Node wall |
| 旧 v2 诊断 | 25/36 | 13/36 | 0/22 | 3/14 | 23/36 | 0 calls / 0 tokens / 约 7.2ms |
| 旧 v3 措辞压力 | 15/20 | 9/20 | 0/12 | 3/8 | 12/20 | 0 calls / 0 tokens / 约 6.2ms |

v4 很高是因为实现与该模板族同窗口开发，只能证明机制可运行。v2/v3 显示真实代价：严格
无模型层可把已见压力样本的错误激活降到 0，但会把大量有用改写留在 unknown，不能声称
已经泛化。两个 v4 validity 差异也被保守保留为 unknown，而非伪造 refuted 解释。

本地 Qwen3-4B 只完成探针，没有完整 48 条结果。旧 bridge 没把原生 JSON Schema 注入模型
上下文，首次 batch fail-closed；schema-in-prompt 后单条协议有效，契约澄清后的正反一对
核心 validity 2/2、最终 disposition 1/2（缺少重复的 scope evidence 标签）。该批 789 input +
292 output tokens，模型 generation 约 36.6 秒。它说明小模型可做 unknown 路由候选，但在当前
offload serving 上不适合成为所有写入的同步税。随后 5 条探针因本地执行授权通道断线被系统
拒绝，未执行；服务已经关闭。

## AI Infra 量化口径

不把准确率和成本揉成一个可任意调权的总分，报告 Pareto 前沿。四个主指标为：

1. `unsupported_active_rate`：错误行为规则进入 active 的比例，优先约束；
2. `downstream_task_delta`：同基础 agent 的完整任务质量差，不以候选分类代替；
3. `online_added_latency_p50/p95`：记忆链路加入主响应关键路径的墙钟开销；
4. `paid_or_gpu_cost_per_success`：每个成功完整任务的强模型 tokens、本地 GPU generation seconds。

辅助指标：`semantic_escalation_rate`、`strong_model_avoidance_rate`、写入/读取 calls、input/output
tokens、常驻 memory prompt tokens、按需读取 tokens、prompt cache hit、stable-prefix churn、
候选到可用记忆的 freshness lag、后台队列积压与失败率。所有指标按 memory 类型和 scope 分桶，
否则低成本 event 会掩盖高风险 behavior rule。

## 下一执行切片

1. 冻结当前确定性规则，不再用 v1-v4 旧标签加词；生成 16 条新 raw-conversation、来源与模板
   隔离的中英文输入，先测 extraction 后的最终草稿，手写候选只保留为组件检查。
2. 仅比较两条实际策略：`deterministic tier only` 与 `deterministic + unknown 异步语义审核`；
   同时记录错误激活、保留、升级率、tokens、GPU seconds 和 p95。强模型只作升级参考，不默认
   覆盖所有条目。
3. 策略达到安全/成本线后，立即进入新业务 family 的两臂完整任务：不应用自动记忆 vs 应用
   tiered memory。报告正效应、零效应和有界退化。
4. 只有完整任务收益覆盖在线成本，才讨论把该路径接入默认 runtime；production 写入授权边界不变。
