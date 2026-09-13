# B Target Binding v1 结果

## Native reply边界

既有CUPID native-raw 16/16事件都可凭宿主保存的reply edge绑定到上一条answer object，
但0/16能据此绑定到memory cause。`bindFeedbackTarget`因此只接受可信显式reference或
host reply edge；reply edge不会从answer自动提升成memory attribution。

## Codex强基线

按[PROTOCOL.md](PROTOCOL.md)在12个新合成开发案例运行固定Codex target binder：

- 12/12调用成功；
- 8/8可唯一绑定纠正选中正确的opaque `candidate-N`；
- 4/4模糊、样式或环境反馈返回空集；
- 总体12/12，超过10/12、7/8、3/4三个预设门槛；
- 174446 input、42496 cached input、247 output token，墙钟116.378秒。

第一次`run-v1`因输出schema使用API不支持的`uniqueItems`，10次均在请求校验阶段返回
相同`invalid_json_schema`、没有模型输出；剩余2次被主动中止，无残留进程。故障证据
保留且不计质量或上述模型usage。删除该关键字后在新目录一次完成`run-v2`，runner仍在
本地拒绝重复/越界ID，没有改prompt、案例或标签。

完整v2 trace replay通过。结果说明给定oracle候选集合时，强模型能做该合成target任务；
它不证明自然日志能生成正确候选，也不证明被纠正answer中的哪条memory实际造成错误。
汇总见[results/summary.json](results/summary.json)，本地证据在
`.local-evidence/topic3-b-target-binding-v1/{native-reply-audit.json,run-v1,run-v2}/`。
