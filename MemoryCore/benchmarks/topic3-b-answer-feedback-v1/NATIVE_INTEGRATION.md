# 临时B反馈旁路接入

新增`src/core/memory-feedback/answer-feedback.ts`的`selectAnswerFeedback`，与旧E的`processFeedback`并列导出。宿主传入已取得的baselineFeedback、含answerId/候选ID/checkerPass的观察及selector回调；观察可扩展携带原文、规则和真实source记录。返回feedback/useBaseline/status/reason/elapsedMs，供宿主临时反馈展示或后续消费。当前无Gateway默认启用，也无回答改善主张。

关闭立即返回原baseline且不调用selector。开启后候选上限256，单次异步selector期限不超过30秒，加载训练状态/校验必须放在回调内共享期限；异常、未知、重复/越界ID、选择非失败项、超时均回原baseline，不额外跑昂贵基线模型。合法空集是selected。超时abort并忽略迟到结果。回调须遵守异步取消、自己验证训练状态且无写副作用；入口未提供memory/store写句柄，不能保证任意恶意宿主回调的行为。

不新增通用状态格式、签名系统或E权限；冻结示例由数据/模型适配器验证和加载。当前观察不能包含当前gold；训练标签只在有界示例状态内使用。未知不能当作完整正确。`parseAnswerFeedback`只读最终ACTIONABLE列表，截断直接未知；不会从解释推断结果。

## 本轮实际证据

- 新合同和原lifecycle两文件共13测试通过：off、合法子集/空集、unknown/非法集合、加载损坏、超时及迟到结果、终末读取；新模块独立TypeScript类型检查通过。
- `native-replay.ts`对compact开发10检查点写入275实际L0用户消息，使用VectorStore逐条读回构造history，再经旁路重放10个已保存模型输出；成功/失败集合与Python一致。
- 每点off与强制读取失败回原baseline（本演示宿主原无反馈，故baseline=[]）；前后L0行与FTS搜索结果相同。不生成额外模型调用，不改E历史。

这是原生宿主重放与回退验证，不是同一模型在数据库读回后重新推理。无状态/版本更新发生；L0主键作为真实source记录标识，first_observed_turn仍只是构造状态首次观察，并非已证明当前来源归责。候选仍是oracle历史规则值，不借数据库写入改称自主发现。尚需完整评估回执重放及真实内部适配，当前不能宣称商业验收。

复跑：`tsx native-replay.ts RUN fit-predictions.jsonl NEW_DIRECTORY`；评估使用对应RUN和eval-predictions.jsonl。输入RUN须已包含tasks.json与原模型回执，输出目录须新建以保护证据。
