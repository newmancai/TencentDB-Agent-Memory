# B Target Binding v1

## 目标

在candidate memory set和反馈所针对的answer object均已知时，测试强普通基线能否把
自由文本反馈绑定到具体memory assertion，或在非记忆故障/信息不足时返回unknown。
这一步不学习scope、不更新记忆，也不把相邻回复直接归因为记忆错误。

## 固定协议

- 12个全新合成开发案例：8个可唯一绑定的具体纠正，4个应拒绝的模糊、样式或环境
  反馈；每例3个候选assertion和实际answer，expected target不进入prompt。
- 固定`gpt-5.6-sol`、reasoning `medium`、12个ephemeral独立会话、只读空目录，禁止
  工具/浏览/文件访问；输出schema固定为`{"target_ids": [...]}`。
- 模型只能返回候选ID；不能唯一归责时返回空数组。deterministic checker比较目标集合，
  无LLM judge。失败/超时不重试。
- 所有candidate、source answer decision、answer-target feedback claim、binder decision和
  checker outcome写入Phase 0 trace并做fail-closed replay。

## 预设判定

通过组件门槛：总体至少10/12、可绑定至少7/8、应拒绝至少3/4。达到门槛只表示该强
基线值得进入有界端到端组合；不表示自然反馈target学习已解决。未达到则只检查执行/
解析故障，不改本12例prompt、标签或候选追分。
