# B Phase 0：反馈轨迹合同与 replay 检查

日期：2026-09-13

## 结论

已在现有 host-neutral `memory-feedback` sidecar 上追加最小 Phase 0 合同：
`decision_trace`、`feedback_claim`、`memory_assertion`、`outcome` 四种记录，
以及纯函数 replay 检查器。原有 `selectAnswerFeedback`、E lifecycle、默认关闭和
fallback 行为均未改变。本轮没有模型调用、下载、GPU、数据库写入或 production
接入。

这一步完成的是“以后什么日志才有资格成为学习样本”的代码边界，不是 B 收益或真实
反馈归因。后续持久任务中已新增一条隔离本地host-path开发事件：真实SQLite L1写入/
FTS召回、OpenClaw recall bridge字节级prompt暴露、反馈、assertion和checker outcome
均写入JSONL并在重启后回放成功。该事件的助手/用户文本和checker是脚本化的，因此
完成Phase 0开发闭环，不等于真实自然用户或production闭环。

## 交付

- `src/core/memory-feedback/trace.ts`
  - 四个 versioned record schema；
  - `selectMemoryAction`、`observeFeedback`、`recordMemoryAssertion`、
    `recordOutcome` 四个无 I/O 构造/校验入口；
  - `validateFeedbackReplay` 跨记录校验和 learner-ready 样本导出。
- `src/core/memory-feedback/trace.test.ts`
  - 完整闭环、缺字段、未知绑定、候选越界、双时态倒置、前向因果引用、
    null reward 和重复 ID 测试。
- `src/core/memory-feedback/{index.ts,README.md}` 与 `src/core/index.ts`
  - 追加导出和使用边界；没有启用运行时 hook。
- `trace-store.ts`、`recall-trace-adapter.ts` 与 `host_trace_harness.ts`
  - 本地append-only ledger；把现有recall shadow observation映射成带真实候选、
    include/omit、propensity、prompt span和output ID的decision；一条本地host路径复放。

## 关键合同

1. `decision_trace` 必须显式保存候选集合、实际动作、选中记忆、策略版本和实际
   action propensity；缺 candidate set、action 或 propensity 的日志整体
   fail-closed，不产生部分学习样本。
2. `include` 至少选一个候选，`omit` 不得选候选；prompt span 只能指向实际选中的
   记忆。这区分“记忆存在”与“策略看见并使用”。
3. `feedback_claim` 将 observation、target、scope、authority、confidence 分开；
   无法绑定时必须保存 `decisionId=null`、`targetType=unknown`，不从相邻消息猜因果。
4. `memory_assertion` 分开 valid time 与 transaction time，支持 candidate、verified、
   disputed、expired、superseded 状态；claim 仍是证据，不自动变成真值。
5. `outcome` 绑定先前 decision；只有 finite numeric reward 才进入 learning sample。
   null reward 保留在 `pendingDecisionIds`，不伪造分数。
6. replay 检查全局 ID 唯一、append order、因果时间、先前 decision/evidence 引用；
   任一结构或因果错误都返回零 learning samples。

## 对旧成果的实用判断

既有 CUPID native raw 记录仍有用：
`../topic3-b-contextual-feedback-v1/results/native-raw-summary.json` 保存了16个事件的
feedback/response record ID，
且82次隔离写读保持文本、角色和 session 一致。这些是新的 `sourceEventIds`、
`contextEventIds` 和 target/output linkage 的可复用来源。

但旧记录没有当时的 candidate memory set、memory action、policy version 或
propensity。因此不能事后把这16项包装成反事实学习样本；补这些字段会是在编造
历史。它们可以作为 raw-event/provenance 回归集，不能直接用于 IPS/DR 或学习 gate。
这正是本合同修补的首要缺口。

## 验证

在 `MemoryCore` 目录执行：

```text
npx vitest run src/core/memory-feedback/*.test.ts \
  src/core/self-supervision/openclaw-recall-turn-bridge.test.ts
Test Files  5 passed (5)
Tests       31 passed (31)

npx tsc --noEmit --target ES2022 --module ESNext --moduleResolution bundler \
  --skipLibCheck --types node,vitest/globals [trace/store/adapter/harness files]
exit 0

npm run build:plugin
Build complete
exit 0
```

另实际执行`host_trace_harness.ts`并用`replay_trace.ts`重开检查，四类记录各1条、
1条learning sample、0 pending。验证覆盖新合同、原有B/E sidecar及本地host路径；
不是全库质量评测、自然用户事件或模型效果评测。

## 停止点与下一判定

后续明确恢复为持久任务后，上述真实本地事件闭环已经完成；证据在
`.local-evidence/topic3-b-feedback-trace-v1/host-closure-v2/`。随后运行的小规模oracle
attribution已达到预设进入scope阶段的阈值，见
[../topic3-b-oracle-attribution-v1/RESULTS.md](../topic3-b-oracle-attribution-v1/RESULTS.md)。
这不改变本合同本身没有启用production hook的边界。
