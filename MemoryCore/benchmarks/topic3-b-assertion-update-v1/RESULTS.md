# B Assertion Update Compilation v1 结果

仅对target binding已唯一通过的8个显式纠正运行compiler；4个应拒绝案例没有调用，避免
在unknown上强造记忆。8/8调用均精确返回原target ID、纠正后值和未扩大的原scope，超过
预设7/8门槛。成本为114112 input、10624 cached input、287 output token，墙钟76.620秒。

合并target前缀后的trace replay通过：32 decision、12 feedback、44 assertion、20 outcome；
20条有numeric outcome，12条历史source decision保持pending而未伪造分数。该结果只覆盖
已绑定、明确给出新值的合成纠正；不覆盖隐含偏好、冲突authority或自然scope抽取。

协议、runner和汇总见[PROTOCOL.md](PROTOCOL.md)、[assertion_update.py](assertion_update.py)
与[results/summary.json](results/summary.json)，完整证据在
`.local-evidence/topic3-b-assertion-update-v1/run-v1/`。
