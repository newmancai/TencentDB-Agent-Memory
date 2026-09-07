# 最终写入草稿审核：v4 候选切片与 Codex 对标

状态：`CANDIDATE_SCREEN_COMPLETE / NOT_FULL_V4_ACCEPTANCE / NO_PRODUCTION_ACTION`

## 结论

新链路已经从“候选类型分类”推进到“审核 dedup 后的最终写入草稿及完整有序证据窗口”。
实现能在副作用前核验内容支持、行为适用性、用户采纳与范围，机械检查 message ID 和原文
摘录，并把隔离/暂缓草稿持久写入本地 review queue。复杂 update/merge 在第一切片保持
deferred，避免未经复核的改写替换旧记录；所有能力默认关闭。

量化上，Codex 直接判断仍显著强于旧本地词法路径。MemoryCore + Codex 独立核验在单次
trial 中与 Codex 直接判断同为 48/48 disposition，并把该 trial 的 validity 从 43/48
提高到 45/48，同时提供 48/48 可机械验证的证据引用；但没有 disposition 增益，而且
观察到的墙钟延迟超过直接判断 2 倍预算，因此按停止规则只跑 1 次，不选作默认策略。

## 数据与结果

外发输入为 48 条新合成模板，8 个语义组，24 retain / 24 quarantine。ID 为不透明哈希；
gold、provenance、category 与嵌套 `scene_name` 均被移除。评分使用完整 48 条固定分母，
缺失、重复、额外 ID 或非法枚举会记录协议失败。

| 路径 | disposition | validity | 错误激活 | 有用保留 | 调用/成本 |
|---|---:|---:|---:|---:|---:|
| 全保留 | 24/48 | 3/48 | 24/24 | 24/24 | 0 模型调用 |
| 旧 `evidence_scoped_v1` | 27/48 | 18/48 | 15/24 | 18/24 | 0 模型调用 |
| Codex 直接判断，3 trials | 144/144 | 133/144 | 0/72 | 72/72 | 118,258 tokens |
| MemoryCore 最终草稿 + Codex D，1 trial | 48/48 | 45/48 | 0/24 | 24/24 | 38,641 tokens |

Codex 直接判断的首 trial 为 disposition 48/48、validity 43/48；三次 observed pass³
分别为 48/48 与 43/48。三次输出协议均有效。D 路径的 24 retain 都通过最终草稿合同；
24 quarantine 的原因包含内容反驳 21、任务范围 15、未建立采纳 6，一条可同时有多个原因。

## 优势与劣势

MemoryCore 当前优势在于把风险控制放在真正写入点。这里没有将“模型分数超过 Codex”作为结论：dedup
改写后的 content/type 会被看到，`work_method` 等行为规则不能靠类型绕过，候选引用顺序
不能覆盖宿主消息顺序，审核异常会 fail closed，隔离对象有持久审计记录。

劣势也很明确：旧词法路径在新模板上只有 56.25% disposition，不能作为通用 fast path；
全量 D 审核延迟过高；主机只能验证引用存在和摘录精确，不能自行证明语义蕴含。当前更合理
的方向是保留最终草稿/证据合同，压缩语义核验为单次结构化 S 或只对高风险行为规则路由；
全量记忆默认增加 D 调用的成本过高。

## 实现与验证

- `final-draft-admission.ts`：最终草稿构造、SHA-256 身份、窄 `ScopeAssessmentV1`、证据核验、
  fail-closed、update/merge deferred 与 dedup gate。
- `l1-extractor.ts`：在 dedup 后、writer 前调用审核，并将隔离项追加到
  `review_queue/YYYY-MM-DD.jsonl`。
- standalone LLM runner：可选原生 JSON Schema structured output；旧调用兼容。
- pipeline factory 与研究 sidecar：新增默认关闭的 S/D 选择入口。
- reviewer 对一批最终草稿使用一次 structured-output 调用；批次缺项、重复或调用异常时，
  对应草稿 fail closed，不退回逐条无界调用。
- Hermes execution gate：绑定当前任务边界，拒绝空结果、文本错误、`success:false`、
  `is_error:true` 和旧任务成功回执。
- 测试：Vitest 183/183（聚焦 15/15）；Hermes Python 13/13；插件构建及三个现存脚本构建通过。
  `npm run build` 最终仍因仓库原有 `scripts/seed-v2/tsconfig.json` 不存在而退出 1，未将其
  误报为本次回归。

OpenAI 官方建议用结构化输出保证格式，并基于代表性 eval 同时比较准确率、token 与端到端
延迟；本切片据此保留了 D 的质量结果，也因延迟超预算停止扩跑：
[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)。

## 边界与下一步

这不是完整 v4 acceptance：48 条当前全是 candidate-decision checks，计划中的 16 条
raw-conversation end-to-end 抽取以及新业务 family 两臂完整任务仍未执行。样本虽消除了
已知元数据泄漏，但由同一开发窗口构造，称“metadata-clean synthetic screen”，不称独立
严格盲测。下一步应先实现/压测低成本 S，再冻结 16 条端到端来源；只有达到成本线后才进入
新业务两臂。未启动 production Memory 写入、删除、降权或重排。
