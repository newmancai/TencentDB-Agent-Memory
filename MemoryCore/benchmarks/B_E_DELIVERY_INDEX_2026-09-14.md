# B+E 项目记忆系统：最终交付清单

本项目围绕“编码代理如何记住项目反馈，并在后续任务中正确使用”展开。交付内容包括研究设计、公开数据
评测、项目记忆实现、失败回退验证和可审阅 PR。本文件用于快速核对材料；完整的方法与结果以
[`B_E_FINAL_SUBMISSION_REPORT_2026-09-14.md`](B_E_FINAL_SUBMISSION_REPORT_2026-09-14.md) 为准；
可审阅实现位于 [PR #4](https://github.com/newmancai/TencentDB-Agent-Memory/pull/4)。

导师最终提交请直接使用
[`B_E_导师最终交付_2026-09-14.zip`](../deliverables/B_E_导师最终交付_2026-09-14/B_E_导师最终交付_2026-09-14.zip)。
压缩包内含 17 页白底 PDF、报告 Markdown 源文、完整可运行源码快照、相对原始 MemoryCore 基线的
精确 patch、代码／测试索引以及 SHA-256 清单。

## 五项必交材料

| 序号 | 要求 | 对应交付物 | 状态与结论 |
| ---: | --- | --- | --- |
| 1 | 调研报告＋设计说明：问题、相关工作、方法、协议、演化边界、fallback、移植说明 | [研究与验证设计](topic3-be-agent-product-v1/RESEARCH_AND_VALIDATION.md)、[产品协议](topic3-be-agent-product-v1/PROTOCOL.md)、[移植说明](topic3-be-agent-product-v1/PORTING.md)、[最终报告](B_E_FINAL_SUBMISSION_REPORT_2026-09-14.md) | **完成**；覆盖原话保留、约束编译、范围与版本链、失败回退和适用边界 |
| 2 | 公开长对话上的 Eval Runner 与结构化结果，含基座基线 | [`memorycode_codex_update_full.py`](topic3-be-agent-product-v1/memorycode_codex_update_full.py)、[`memorycode_focus.py`](topic3-be-agent-product-v1/memorycode_focus.py)、[`agent_product_runner.py`](topic3-be-agent-product-v1/agent_product_runner.py) 及相邻 `*-results.json` | **完成**；MemoryCode 更新层 full raw 7/10、no-history 0/10；独立 focus 确认为 9/10→10/10 |
| 3 | 所选方向实现，以及与基座对比或方法验证 | [`project-memory.ts`](../src/core/memory-feedback/project-memory.ts)、[`project_agent.py`](../scripts/project-agent/project_agent.py)、[`store.ts`](../scripts/project-agent/store.ts)、[公共结构化结果](topic3-be-agent-product-v1/public-eval-results.json)、[runtime 三臂结果](topic3-be-agent-product-v1/PROJECT_MEMORY_RUNTIME_OPTIMIZATION_RESULTS.md) | **完成**；公开项目家族首任务 2 胜 0 负 6 平；模型前 bridge 最终 4→1 |
| 4 | 关闭开关与强制失败回退验证 | `--mode off`、raw fallback、损坏／容量／存储失败测试；[`runtime-contract-results.json`](topic3-be-agent-product-v1/runtime-contract-results.json) 和实现测试 | **完成**；off 不读写本工具记忆，非法范围调用模型前拒绝，读取成功但写入失败仍保留上下文并显式报错 |
| 5 | 可审阅 PR：数据适配层与内部移植说明 | [PR #4](https://github.com/newmancai/TencentDB-Agent-Memory/pull/4)、[`prepare_real_projects.py`](topic3-be-agent-product-v1/prepare_real_projects.py)、[`PORTING.md`](topic3-be-agent-product-v1/PORTING.md) | **完成待审**；PR 保持 draft，最终 head 的 6 项 CI 均已通过 |

公开数据的开发／确认划分、固定任务、独立 checker、原始 usage 与失败样本均按协议保存。外部开源记忆
系统尚未完成同条件实跑，因此“优于某个开源产品”不属于本次结论。

## 导师要求的最终上交材料

| 上交项 | 首选入口 | 内容 |
| --- | --- | --- |
| 方案实现代码 | [项目记忆核心](../src/core/memory-feedback/project-memory.ts)、[编码代理宿主](../scripts/project-agent/project_agent.py)、[SQLite bridge](../scripts/project-agent/store.ts) | B 的来源／范围／演化与 E 的执行、检查、回执、恢复；安装入口为 [`memory-agent.mjs`](../bin/memory-agent.mjs) |
| 测试代码 | [`project-memory.test.ts`](../src/core/memory-feedback/project-memory.test.ts)、[`test_project_agent.py`](../scripts/project-agent/test_project_agent.py)、[公开评测测试目录](topic3-be-agent-product-v1/) | 204 个 TypeScript 测试、25 个项目代理测试、31 个公共 runner 测试；另含安装包 smoke 与 CI |
| 方案介绍＋测试结论报告 | [白底 PDF](../deliverables/B_E_导师最终交付_2026-09-14/B_E_方案介绍与测试结论报告.pdf)、[`Markdown` 源文](../deliverables/B_E_导师最终交付_2026-09-14/B_E_方案介绍与测试结论报告.md) | 17 页主报告，包含原始题目、研究问题、设计创新、逐环节指标、失败复盘和适用范围 |

## 方案亮点与完成规模

- 项目记忆不是普通文本缓存：原始反馈、结构化约束和版本演化分别建模，并支持项目／路径／动作范围、
  来源引用、替代链和显式撤销。
- 记忆效果直接落到编码行为：Codex／Claude Code 调用、checker、usage、事件流和代码 diff 形成同一份
  可恢复回执，能够追踪“记住了什么”是否真正改变了代码。
- 评测覆盖 8 个独立公开项目家族、16 个有效顺序任务，以及 MemoryCode 360 段对话和 4,182 个检索查询；
  v5–v9 五套受污染或 checker 不完备的矩阵均被复盘并排除，没有挑选有利子集。
- PR 相对研究基线覆盖 41 个文件；三套主测试共 260 项，另有最低 Node、构建、安装包、尺寸和隔离门禁。
- 运行时优化以逐字等价为前提，把模型前 bridge 进程从 4 个降到 1 个，均值／p95 固定开销下降
  46.1%／46.5%。

## 最终量化摘要

- 公开仓库独立项目家族：**2 胜 0 负 6 平**；这是当前产品收益锚点。
- MemoryCode 独立 focus 确认：**9/10→10/10，1 胜 0 负 9 平**；样本区间仍触及 0，作为实验性证据。
- AI infra：最终三臂 20 组本地配对中，上下文和最终快照 20/20 逐字一致；source/`tsx` 双调用
  `0.454s` 均值、`0.472s` p95，precompiled one-shot 为 `0.245s`、`0.253s`，分别降低
  **46.1%／46.5%**；该数字不含模型、网络或 checker。
- 工程回归：MemoryCore **204/204**、项目代理 **25/25**、公共 runner **31/31**。

## 建议阅读顺序

1. 先读最终报告，了解问题、方案、主要结果和结论范围。
2. 再按“导师要求的最终上交材料”进入实现代码与测试代码。
3. 需要重算结果时，再进入各实验协议和机器可读 JSON；历史过程文档不作为首要阅读材料。
