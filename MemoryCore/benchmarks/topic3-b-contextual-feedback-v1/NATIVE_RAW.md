# 原话反馈与原生 L0 的接入边界

完成16个公开开发事件、82条消息的实际隔离SQLite L0写读。通过已有VectorStore.upsertL0写入用户/助手正文，queryL0RecordsCursor读回，逐条核对文本、角色和session ID；宿主据原prefix顺序构造feedbackRecordId/responseRecordId，16对均匹配且只读后记录未变。结果[结构化回执](results/native-raw-summary.json)，复现[脚本](native-raw.ts)。无模型、语义审核、E或生产Memory操作。

这一检查只证明原话及来源记录可以通过基座保存/恢复。回复关系由宿主持有的顺序映射，并未新增持久reply-to字段；未验证仅靠重启后的数据库就能独立重建整个事件图，也未测检索排名、多用户权限隔离或并发写入。每个事件独立数据库；相同会话前缀在不同事件数据库重复写入，不把82条称独立会话。

## 为什么没有把这些反馈接到checker失败接口

现有selectAnswerFeedback只允许checkerPass=false候选。用户认可、局部修改要求或建议并不是checker失败。将它们伪装成false会把行为观察误当已核验故障。因此本轮复用L0原文存储，不修改已有选择器资格规则，不新增默认Gateway钩子。

自然反馈未来可以作为宿主观察记录，被已授权策略读取；何时能转成可操作候选，仍需明确内容/对象/适用范围和监督来源。原话没有模型摘要造成的遗漏，也不自动具有外部事实权威。当前没有新的自然反馈学习器或默认处理路径，旧17合同测试的off/failure覆盖不能冒充本轮新路径验收。

## 执行与修正

首次命令工作目录使用错误，未创建脚本/数据库即失败。修正目录后，第一版harness错误地假设cursor返回user_id，实际L0RecordRow只投影record/session/role/text/time字段；在第一事件断言失败，数据库保留在本地native-raw。修正为公开返回合同的session_id核对后，在新的native-raw-v2目录完整通过（session11253 exit0）。没有修改基座以迎合harness；不声称验证owner字段。

```bash
tsx native-raw.ts EVENTS/audit-inputs.jsonl NEW_DIRECTORY
```

相对导入复用MemoryCore基座，需安装仓库已有依赖。完整数据库留本地，不上传PR。此次代码仅研究harness，MemoryCore/src未变。
