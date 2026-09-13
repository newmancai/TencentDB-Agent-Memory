# 原生临时反馈旁路独立审查

2026-09-13。仅阅读answer-feedback.ts、对应测试、native-replay.ts、NATIVE_INTEGRATION.md；未读评估模型输出，未改代码。

## 具体问题

1. **无效observation不总能回退。** `selectAnswerFeedback`在try外直接读取`p.observation.candidates`。若宿主从JSON边界传入null/undefined observation，会抛异常而非返回`invalid_observation`基座；answerId也未作运行时非空校验。TS类型保护了正确类型的内部调用，但此函数已有明确运行时invalid_observation语义，不能把它描述为所有坏观察都能回退。应在入口检查观察对象后再取字段；不需新签名框架。

2. **timeout目前是事件循环可调度时的异步超时，不是严格wall deadline。** selector通过微任务启动；若其中状态验证/解析或其他同步工作阻塞事件循环超过timeout后直接返回结果，其完成微任务可能先于timeout定时器被处理，于是仍返回selected。对纯异步等待与普通晚到结果，现有Promise.race正确；若声称所有状态加载验证共享严格截止时间，应在接受结果前再看实际deadline，或明确回调必须保持非阻塞且不保证同步工作硬中断。无需为本小入口引入worker。

3. **Python终末行分割与TS并非完全同一语义。** Python `str.splitlines()`识别单独CR、Unicode行分隔等；TS仅按`/\r?\n/`切分。例如`explanation\rACTIONABLE: []`，Python可接受，TS把它视为一行而拒绝。当前常规LF/CRLF回执可以一致，但不应把已重放10条扩大为全部文本的解析等价证明。可选择统一明确行分隔合同并加一个定向case；不需要宽松地从解释中恢复ID。

4. **重放没有检查预测ID集合/唯一性。** `predictions.find`只取第一个同ID记录；重复ID或多余记录会静默忽略，任务缺记录才会assert失败。其“全部回执重放”证据因此需要补足输入记录数量、唯一ID和与tasks集合一致的断言。当前是否有异常文件未知，本审查没有读它们；这是重放器的可复现完整性缺口，不是已发生的模型计数错误。

## 已核对正确的部分和主张范围

- 合法空数组通过Array.isArray和eligible子集校验，返回selected而不是fallback；unknown/null、非失败项、重复/外来ID均回基座。
- 正常异步超时先resolve timeout再abort，已返回结果没有被迟到Promise写入的路径；返回成功集合时复制数组，不保留selector数组引用。未发现普通晚到结果覆盖返回值的问题。没有store句柄的接口也未调用旧publish链。
- state加载放selector内确实分享同一个异步计时器；当前没有统一状态schema验证是明确交给适配器的责任，不能宣称已验证任意训练状态格式。
- native replay先写L0、读回构造history，后检查L0与FTS结果不变，能支持原生存储+纯反馈旁路的合同证据。selector实际重放保存text，不重新使用读回history推理；文档已准确说明这个限制，未冒称真实在线模型接入。
- 原生层candidate携带构造字段，并未证明first_observed_turn是当轮有效要求的原文来源。当前文档也正确保留oracle候选和来源归责边界。

上述问题无需改变当前模型实验策略。可在宿主接口/重放合同层局部修复并重放既有回执，不需要重新推理、扩建E或引入新状态系统。
