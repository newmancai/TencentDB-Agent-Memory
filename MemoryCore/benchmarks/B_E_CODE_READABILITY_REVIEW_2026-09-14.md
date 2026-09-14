# B+E 项目记忆：代码整理与架构审查记录

## 结论

整理前，项目记忆的行为边界、测试和安装链路已经成形，但代码还保留着研究原型的压缩写法：一行承担
多个动作、公开返回结构依赖类型推断、固定协议夹在执行流程中，Python 宿主的主路径不容易顺序阅读。
这些问题不会立刻造成测试失败，却会显著增加评审成本，也容易让后续修改破坏隐含不变量。

本次整理以“行为不变、职责清楚、持续可检查”为原则。状态机、安装 CLI、进程后端、差异捕获及其测试
统一了格式；关键阶段被提取为具名边界；公开 TypeScript 返回值改为显式合同；格式要求进入 CI。整理
没有改写研究算法或扩大默认能力，性能改造也必须通过上下文与数据库终态的逐字等价检查。

## 发现与处理

| 发现 | 风险 | 处理方式 |
| --- | --- | --- |
| `ProjectMemory` 的验证、提议接纳、路径匹配和谱系遍历挤在长表达式中 | 状态机不变量难以逐段审阅 | 提取规范化、`materializeConstraints`、`pathsOverlap`、空快照和谱系证据边界 |
| `ingest` / `context` 返回结构靠 TypeScript 推断 | 调用者难以确认 off、selected、fallback 的完整合同 | 新增并导出 `ProjectIngestResult`、`ProjectContextOptions`、`ProjectContextResult`、`ConstraintRetraction` |
| Python 主机内嵌两段长提示，并在 `run` 中混合读取、模型、checker、diff 和回执 | 修改一个阶段时容易误碰另一阶段 | 固定协议提升为常量；提取提示、序号、原话判断；将运行拆成加载、调用/检查、差异、回执四阶段 |
| 超时、取消和异常三处重复终止进程组 | 修复某一路径时容易遗漏其他路径 | 后端统一为 `_stop_process_group`，保留三种终态和实时日志行为 |
| 新文件差异的容量与遗漏判断是魔法数字和密集分支 | 审阅证据边界不直观 | 命名超时/容量常量并提取 `_omission_reason` |
| 只有一次性人工格式整理，没有回归约束 | 后续提交容易恢复压缩风格 | 固定 Black 25.1.0、Prettier 3.5.3；新增 `npm run lint:project-agent` 和 PR CI 检查 |
| 组件关系只散落在长说明中 | 新维护者需要从入口反查职责 | 在 CLI README 增加单向运行链路和各层所有权 |
| `run` 为同一 revision 多次启动 bridge，读取与渲染边界交织 | 固定延迟高，后续优化容易改变 fallback 语义 | 提取纯 `render_context`；最终 `prepareRun` 只编排既有 `loadContext` 与 `ProjectMemory.ingest`，不复制 Memory 规则 |
| 安装路径逐次用 `tsx` 转译 bridge | 每次进程启动重复解析 TypeScript | 将同一 `store.ts` 纳入既有 `tsdown` 构建；安装包使用预编译产物，未构建源码仍有明确 fallback |
| 两个后续 infra runner 重复 seed、时延和配对循环 | 结果入口分散，修复容易遗漏一份 | 合并为单个三臂 `project_memory_runtime_benchmark.py`，复用首轮基准的 seed 与统计函数 |

## 量化变化

这里比较整理前的 PR head `6a521b5` 与最终实现；“长行”定义为超过 100 字符。
部分复合语句展开后，物理行数会增加；这里关注的是控制流是否清楚，而不是单纯比较文件行数。

| 文件 | 长行：前 → 后 | 最长行：前 → 后 |
| --- | ---: | ---: |
| `project-memory.ts` | 22 → 0 | 129 → 100 |
| `project_agent.py` | 52 → 3 | 139 → 104 |
| `changes.py` | 1 → 0 | 101 → 94 |
| `test_project_agent.py` | 8 → 0 | 145 → 100 |
| `project-memory.test.ts` | 17 → 3 | 148 → 118 |
| `test_backend.py` | 8 → 3 | 256 → 108 |

保留的 9 个长行都位于提示／帮助文本、测试断言或内嵌子进程脚本，不承担多步业务控制流。
我没有为了压低统计数字而拆碎用户可见提示，也没有把测试夹具抽象到难以对应真实命令的程度。

最终依赖方向保持单向：Python 宿主负责命令编排，`store.ts` 负责一次进程内的操作顺序，`ProjectMemory`
仍唯一拥有选择、范围、谱系、容量、校验和持久化语义。性能优化没有形成第二套状态机或第二种 fallback。

## 验证

- Black 与 Prettier 检查通过。
- Python 语法编译通过。
- 项目代理测试：25/25 通过。
- agent-product／公共评测测试：31/31 通过。
- 最终 bridge 三臂 20 轮配对上下文和最终快照逐字等价，模型前进程由 4 个降到 1 个。
- 项目记忆定向测试：3/3 通过。
- MemoryCore Node 24 全量测试：24 个文件、204/204 通过。
- 最低 Node 22.19 反馈模块：5 个文件、30/30 通过。
- `npm run build` 通过。
- 从新 tarball 安装后的入口、remember → context → history 和子路径导出 smoke 通过。
- `git diff --check` 通过。

## 后续维护的触发条件

1. `project_agent.py` 仍是一个约 700 行的动态 JSON 编排模块。当前各阶段已有清楚边界，继续拆包会
   增加安装和导入复杂度；当新增第三个 backend、后台归档或远端存储时，再按协议类型拆分。
2. 持久快照读取目前验证外层版本、容量和数组形状，具体嵌套对象主要在使用时失败关闭。若未来接收
   非本 CLI 写入的状态，应新增独立迁移/完整 schema 校验，而不是把兼容逻辑塞进主路径。
3. 可读性和测试通过不等同于模型质量收益。本次整理没有新增模型成绩，也不改变“默认保存完整原话、
   结构化编译显式开启”的产品边界。

## 审查结论

最终代码已经可以沿“CLI → Python 编排 → TypeScript bridge → ProjectMemory → SQLite”的单向依赖顺序
审阅。选择、范围、谱系、容量和持久化仍由 `ProjectMemory` 唯一负责，`prepareRun` 只合并进程内操作，
没有复制第二套记忆规则。剩余拆分项都有明确的规模触发条件，不影响当前 PR 的维护和评审。
