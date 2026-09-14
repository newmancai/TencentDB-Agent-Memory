# B+E 方案实现与测试代码索引

实现快照：`84ba04dee30bd72d7e9f9e57365c5015e7cd5e6d`

## 方案实现

- `MemoryCore/src/core/memory-feedback/project-memory.ts`：项目记忆状态机、来源、范围、版本链与撤销。
- `MemoryCore/src/core/memory-feedback/answer-feedback.ts`：反馈选择、超时、开关与基线回退。
- `MemoryCore/src/core/memory-feedback/dependency-candidate-adapter.ts`：非破坏候选提名。
- `MemoryCore/src/core/memory-feedback/lifecycle.ts`：经验证生命周期旁路。
- `MemoryCore/scripts/project-agent/project_agent.py`：remember/context/run/history/retract/check-run。
- `MemoryCore/scripts/project-agent/backend.py`：Codex／Claude 事件、usage、超时和取消。
- `MemoryCore/scripts/project-agent/changes.py`：工作区差异捕获。
- `MemoryCore/scripts/project-agent/store.ts`：SQLite bridge 与 one-shot `prepareRun`。
- `MemoryCore/bin/memory-agent.mjs`：安装后的统一 CLI。

## 测试代码

- `MemoryCore/src/core/memory-feedback/*.test.ts`：状态机、来源、范围、更新、撤销和 fallback。
- `MemoryCore/scripts/project-agent/test_*.py`：宿主、后端、恢复、checker 和 diff。
- `MemoryCore/benchmarks/topic3-be-agent-product-v1/test_*.py`：公开数据对齐、评分和 runner。
- `MemoryCore/benchmarks/topic3-be-route-v2/test_failure_discovery_runner.py`：项目隔离和失效合同。
- `MemoryCore/scripts/ci/smoke-memory-agent-package.sh`：真实 tarball 空目录安装 smoke。
- `.github/workflows/pr-ci.yml`：Node 24/22、Python、格式、构建、包和 manifest 门禁。

## 公开评测代码与结构化结果

- `MemoryCore/benchmarks/topic3-be-agent-product-v1/memorycode_*`：MemoryCode 适配、检索、生成与评分。
- `MemoryCore/benchmarks/topic3-be-agent-product-v1/public_eval.py`：数据集无关的聚类评估器。
- `MemoryCore/benchmarks/topic3-be-route-v2/prepare_*.py`：公开项目和任务准备。
- `MemoryCore/benchmarks/topic3-be-route-v2/*checker.py`：外置行为 checker 与 near-miss 预检。
- `MemoryCore/benchmarks/topic3-be-agent-product-v1/*.json`：可重算的结构化结果。

## 建议阅读顺序

1. PDF 总报告；
2. `MemoryCore/scripts/project-agent/README.md`；
3. `project-memory.ts` 与对应测试；
4. `project_agent.py` 与对应测试；
5. MemoryCode、route-v2 协议和结构化结果；
6. 相对基座 patch 与在线 PR #4。

## 零模型验证

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
