# 项目记忆编码 CLI 原型

这个入口把用户纠正、持久化项目记忆、Codex／Claude Code 执行和独立检查连成了可运行流程。
当前仍是实验原型，尚未证明相对原生产品的稳定质量收益。包内已包含统一的 `memory-agent`
入口，源码检出也可用 `node bin/memory-agent.mjs`；本轮只验证本地打包，没有发布新版 npm 包。

需要 Python 3.10+、Node 22.16+、本项目 npm 依赖，以及已经登录的 `codex` 或 `claude`。
运行前把它们加入 PATH。不会下载本地模型。CLI 运行时已与评测目录解耦；打包后不需要
benchmarks。可用 `MEMORY_AGENT_PYTHON` 指定 Python；Node 入口会把自己的 Node 路径传给
存储桥接，避免 PATH 上另一版 Node 被误用。旧 npm 发布包尚不包含本轮新增入口。

```bash
# 在 MemoryCore 目录执行；替换仓库和状态目录。
python scripts/project-agent/project_agent.py \
  --workspace /path/to/repo --state /path/to/private-state --project my-repo \
  --backend codex --model gpt-5.6-sol \
  remember '今后修改 src/api 时，默认重试次数设为 0。src/workers 不适用这次修改。'

# 先检查实际将送给编码代理的内容；不调用模型。
python scripts/project-agent/project_agent.py \
  --workspace /path/to/repo --state /path/to/private-state --project my-repo \
  context --paths src/api/client.py

# 从此前持久化的状态取上下文，执行编码，再运行指定检查器。
python scripts/project-agent/project_agent.py \
  --workspace /path/to/repo --state /path/to/private-state --project my-repo \
  --backend codex --model gpt-5.6-sol \
  run '实现 API 客户端重试设置，保留显式传入的 0。' \
  --paths src/api/client.py --check '["python", "-m", "unittest"]'

# 查看原话、来源、版本与撤销记录。
python scripts/project-agent/project_agent.py \
  --workspace /path/to/repo --state /path/to/private-state --project my-repo history
```

`remember` 默认只保存完整原话，**不调用模型**。尚未有足够证据支持把约束提议成本放进默认路径。
需要实验性结构化时，显式运行 `remember '用户纠正' --compile`，用固定提示词提议最多四条带原文
引用的约束。它只检查可机械判定的来源、引用和同范围前任关系；作用范围与语义 key 仍然是模型判断。
不能提取、服务失败或提议
被拒绝时，保存原话供普通读取，不写入部分约束。它不把测试输出升格为用户命令，也不自动把
“测试失败”解释成某条记忆应失效。读取 `context` 后可用 `retract CONSTRAINT_ID '撤销原因'`
显式撤回某条约束，旧版本仍可在历史中查看。

`record` 只保存原话，不调用模型，适合普通历史基线及无需结构化的消息。
模型原始事件实时写入 `runs/.../agent/stdout.jsonl`，无需等任务结束才能查看。
取消或超时会停止本次代理的进程组；Ctrl-C 的部分输出与 cancelled 状态会保留。
`run` 还保存可审阅的 `changes.diff`，包含相对 HEAD 的已有和新编辑，不能把其中所有修改
都归因于这一轮代理。普通新文件会加入差异；符号链接、私有状态目录和超过 1 MiB 的新文件
只记录遗漏原因，不悄悄当作完整差异。它提供审阅材料，不自动恢复用户原有改动。

`run` 保存当前任务和执行／检查回执，下一次调用读取相同 `--state`、`--owner`、`--project`
下的历史。原始模型输出、提示词、上下文和 checker 回执保存在状态目录的 `runs/`；它们不进入
项目源码。一个逻辑项目在不同 worktree 中使用同一 project ID；实验各臂则必须使用独立状态副本。

三种模式用于真实对照：`--mode scoped` 使用有作用范围的视图；`--mode raw` 直接读取相同原话；
`--mode off` 完全绕过本工具的记忆读写。预算不足时 scoped 返回完整原话而不悄悄截断规则，
因此 fallback 可能超过目标字节预算；存储失败时编码任务退回当前请求，回执记录原因。
`--paths` 默认 `.`，保留各目录规则的可见范围；仅在明确任务路径时缩小范围，避免猜错路径导致漏读。
没有编译约束时，scoped 直接使用原话，不增加空的结构化包装。

正常使用保留 AGENTS.md／CLAUDE.md 等项目指导的自动发现。实验才传
`--instruction-mode controlled`，显式关闭指导文件和原生记忆的自动注入；这不禁止模型主动
读取仓库里的文件。两种配置都保留权限控制，Claude 只开放本原型需要的读写和 shell 工具，
不代表完整原生产品的所有工具／插件配置。`off` 只关闭 MemoryCore，不改原生产品自身配置。

当前限制：SQLite 单写者、默认 128 条观察容量；CLI 文件锁只协调使用同一状态目录的本工具进程。
尚无多设备同步、后台归档、图形界面、自动语义纠错或长期服务保证。源文引用正确不等于语义一定
正确；部分编译的消息会同时保留完整原话，以免遗漏未被提议覆盖的其他要求。
默认不自动把普通编码请求推广成长期规则。

复现三项顺序任务集成检查：

```bash
python benchmarks/topic3-be-agent-product-v1/sequence_smoke.py --output /path/to/new-smoke-output
```

这会执行两次 Codex 约束提议和六次真实编码 CLI 调用，需要已登录的 Codex。
夹具是合成 Python 仓库，只验证接线、局部更新与控制行为；不要把它作为真实项目或产品分数。
