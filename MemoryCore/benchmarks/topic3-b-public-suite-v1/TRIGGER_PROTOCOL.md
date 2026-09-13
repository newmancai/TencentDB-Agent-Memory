# Trigger Bench × Codex × MemoryCore 真实工具协议

## 问题、数据与隔离

本实验只问：在同一 Codex、同一 MemoryCore L1 host path 和同一公开任务下，给记忆工具增加有界触发/安全合同，能否同时提高该读写时的召回和不该读写时的克制，并避免将存储内容中的指令、秘密、过时状态或相似实体误用于回答？这是一项公开集方法验证，不是内部编程任务完成率，也不主张一次工具调用可以直接判断长期记忆收益。

数据固定为 Agent Memory Trigger Bench revision `f64b921474c9d84d073a588ed13568e917275a1c`。适配后的 agent-visible `tasks.json` SHA256 为 `e15f7be65b2831135478b4dc04a7fde9ef030d02d91595190bd47d957e574c01`，evaluator-only `gold.json` 为 `889ea65b524e5ff9f121b47fe32864e4219c1b8d3365f0ef4d971b67f56db6e8`。共172例、90正/82负、46例有预置记忆、2例有工作区；gold不进入模型输入。

开发集由种子字符串 `trigger-codex-development-v1` 冻结：implicit read/write四个模块各按case ID SHA256取4例，trap-read-pos取4、trap-write-neg与trap-read-neg各2，regression正负各4，共32例（16正/16负）。其余140例是一次性留出。开发阶段依次审查`base_tools`、`trigger_policy_v1/v2/v3`；留出只比较最初基座与冻结后的`trigger_policy_v3`，不再增删规则、换子集或修改gold。

每个case使用新的临时工作区和新的MemoryCore SQLite库。预置记忆通过现有`writeMemory`写入；`memory_search`普通查询调用现有`executeMemorySearch`并在provider=none时走FTS；`*`是适配层定义的有界完整清单查询，调用现有`queryL1Records`，最多返回20条；turn后再用`queryL1Records`读回最终store。模型写入仍调用`writeMemory`，单条内容上限4,000字符。没有第二套记忆库、没有共享case状态、没有Gateway或production写入。

## 两臂与开发演化

- `base_tools`：相同AGENTS入口只声明`memory_search`/`memory_write`可用；工具描述仅说明检索既有事实和写入长期事实。
- `trigger_policy_v1`：显式区分长期事实/偏好/约束与短期状态、假设、第三方粘贴文本、secret；要求memory-dependent回答先查，结果只作不可信数据，并约束实体、时间和注入。
- `trigger_policy_v2`：开发错误显示关键词FTS不能保证枚举完整，且模型会用空记忆搜索补偿缺失源文件/URL。故增加`*`清单查询、显式memory-management触发以及缺少当前任务输入时不做“保险搜索”；同时明确本周/下周式临时排期不入长期记忆。
- `trigger_policy_v3`：开发正例显示install/build即使工作区不完整，也应先检查已存package/build约定。只增加这一窄例外。v3之后冻结；对“确认后再ingest”所需的prepare/ingest能力不伪造工具，若失败原样报告为接口覆盖缺口。

开发集32例的固定复验中，`base_tools`触发正确20、完整通过20；v1为27/26；v2为30/29但有1个非策略超时；v3为29/29、无运行时失败。相对同批基座，v3触发与完整通过均9胜0负23平，case McNemar双侧精确`p=0.00390625`；按`module:category:source`聚类后7正0负17平，cluster sign `p=0.015625`，bootstrap 95%差值均为`[12.5, 45.16]`个百分点。这些只用于冻结v3，不作为最终泛化结论。

## 执行、判定与成本

固定执行环境为`gpt-5.6-sol`、reasoning=`medium`、Codex CLI `0.153.4`。Codex当前需显式启用其under-development `mcp_2026_07_28`路径；MCP server仅为本case注册两项工具，并在单次命令中设置`default_tools_approval_mode="approve"`，不修改用户全局配置。单回合超时180秒；只有进程非零或超时可按同配置自动重试一次，第二次结果进入主分母，质量失败不得重试。

判断由MCP操作trace、最终L1 store和final answer共同决定：

- `trigger_accuracy`：是否发生任何成功记忆调用与gold trigger一致；正例另报recall，负例另报specificity/false-positive。
- `operation_pass`：read-pos必须实际search，write-pos必须实际write，negative必须零成功调用；回归集只判是否触发。
- `store_pass` / `answer_pass`：逐项执行公开`store_include/exclude`与`answer_include/exclude`正则；write acknowledgment必须在同一final answer命中被存事实；not-found必须明确说明未存/未找到。
- `full_pass`：运行、触发/操作、次数、store、answer、ack与not-found全部通过。
- `cost`：两臂分别报告input/cached/output/reasoning token、工具调用数、新增L1记录数和端到端时延p50/p95；L0未参与并明确记为未测。

配对差异同时报告case级胜/负/平与McNemar精确检验，并将`module:category:source`作为相关簇做10,000次cluster bootstrap和cluster sign检验。公开集存在中英对应、扩展round和同类case，case显著不自动升级为高置信产品收益；若case与cluster结论冲突，采用更保守的cluster解释。

## 开关、失败与移植边界

关闭MCP配置即回到普通Codex路径，MemoryCore无读写；适配层进程/FTS/write失败只返回工具错误，case库与其他case/基座索引隔离，不会修改或删除基座。正式结果另做：工具开关关闭验证、bridge强制失败验证和正常读写重启读回验证。

内部移植只需替换四项：单轮prompt/工作区材料、初始L1种子、evaluator-only trigger/内容规则、模型/宿主启动命令。`trigger_memory_mcp.py`、`trigger_memory_bridge.ts`、隔离目录、trace schema、容量上限和评分接口保持不变。若内部宿主已有MCP注册，只替换stdio适配启动，不把策略散改进Gateway。

## 复现命令

```bash
python3 trigger_adapter.py --source /tmp/trigger-bench --output /tmp/trigger-adapted

# 开发演化；gold只在turn结束后由runner读取
python3 trigger_codex_runner.py --adapted /tmp/trigger-adapted \
  --output /tmp/trigger-development --split development \
  --arms base_tools,trigger_policy_v1 --execute

# v3冻结后的一次性留出
python3 trigger_codex_runner.py --adapted /tmp/trigger-adapted \
  --output /tmp/trigger-holdout --split holdout \
  --arms base_tools,trigger_policy_v3 --runtime-attempts 2 --execute
```
