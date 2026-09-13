# B Oracle Attribution Intervention v1 结果

日期：2026-09-13

## 结果

按 [PROTOCOL.md](PROTOCOL.md) 完成8个全新合成开发项目、include/omit各一次的16次
独立Codex调用。16/16返回成功，0重试、0超时。deterministic JSON checker结果：

| 指标 | include | omit |
|---|---:|---:|
| 精确成功 | 8/8 | 0/8 |
| 配对胜/负/平（include相对omit） | 8/0/0 | — |

达到预先固定的进入scope阶段阈值：include至少7/8，且配对净胜至少6项。8个omit
输出均为协议要求的`unknown`，8个include均原样使用了各自oracle assertion；不存在
LLM judge或人工改分。

## 执行与成本

- 模型：`gpt-5.6-sol`，reasoning `medium`，Codex CLI `0.153.4`；
- 16个ephemeral独立会话，只读空目录，忽略用户配置和项目规则；
- 226733 input、59776 cached input、424 output、0 reasoning output token；
- 调用墙钟合计127.772秒；
- 逐调用prompt、事件、最后消息、stderr、usage与checker回执保存在
  `.local-evidence/topic3-b-oracle-attribution-v1/run-v1/`；Git只保存runner、协议和汇总。

执行顺序按项目散列交错：Atlas/Juniper/Kestrel/Quartz/Solace先include，Mica/Nimbus/
Redwood先omit。两臂提示、模型、schema和checker相同，只有oracle assertion是否进入
prompt不同。

## Phase 0 replay

完整trace通过同一fail-closed replay检查：24条decision、8条feedback claim、8条
memory assertion、24条outcome；24个decision均有finite numeric reward，形成24条
learner-ready样本，0 pending。额外8个source decision/outcome用于表示“旧回答→明确
纠正→verified assertion”的来源闭环，不计入上述16次Codex arm结果。

## 能与不能得出的结论

可以得出：在对象、范围和权威均由oracle正确提供，而且当前任务缺少该项目专有值时，
Codex能够读取并使用精确记忆；正确记忆的include动作具有明确任务价值。因此当前B问题
不是“模型即使拿到正确记忆也完全不会用”，允许按预定路线进入scope组件。

不能得出：系统已经学会从自然反馈生成该assertion、判断它何时适用，或选择正确动作。
omit看到的信息更少，8比0是信息干预 sanity check，不是同信息表示学习收益、自然分布
提升或商用证明。任务是合成的精确配置查询，范围也刻意无歧义。

## 下一步

保持oracle target与authority，只替换scope：使用成对的适用/不适用当前上下文，同时测
“应该变”和“不应该变”，先比较高precision确定性范围规则。若规则已充分，不为追求
“学习”而引入模型；只有规则在未见组合上留下明确缺口，才测试轻量scope learner。
