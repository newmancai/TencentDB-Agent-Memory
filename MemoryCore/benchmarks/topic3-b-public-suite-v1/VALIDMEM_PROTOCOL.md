# ValidMem Codex 配对评测协议

## 问题与冻结点

本实验只问：在同一个 Codex 模型、同一批公开记忆和同一选项下，显式生命周期决策策略能否提高答案与所选证据的有效性？它不测自然反馈写入，不是内部业务完成率，也不把上游 MemFSM 成绩记为本项目成绩。

数据固定为 ValidMem v1.1 revision `786d5cd9f18e65bff6172d81fcb7c9009350a400`；适配后 `tasks.json` SHA256 为 `cef3fe3e...`，`gold.json` 为 `8b70d72b...`。模型固定 `gpt-5.6-sol`、reasoning `medium`、Codex CLI `0.153.4`。每个case只允许从公开选项选择，并返回实际选择的memory ID；runner随后才读取隔离gold评分。

开发集使用种子字符串 `validmem-codex-dev-v1`，按case ID SHA256在A/B/C各取前20，共60例。其余406例为一次性留出，开发和留出无重叠。batch只减少CLI固定开销；评测粒度仍是case，但同batch输出可能相关，显著性解释需保留此限制。

## 开发轮次

1. `plain_visibility`：全部可见store，允许Codex自行理解日期、冲突与问题意图。
2. `lifecycle_policy`：显式给出日期到期、current/history与同实体新旧冲突规则，不提供任何case标签。
3. `type_aware_policy`：在第2项上增加上游开源实现使用的可执行TTL：无显式expiresDay的`project-status`在年龄大于14天后到期，其他type不套用该隐式TTL。

第一次两臂开发运行普通54/60、lifecycle 55/60，为1胜0负59平，但CRR/EAR不变。重复运行普通54/60、lifecycle 54/60；type-aware 57/60，相对普通3胜0负57平，A 20/20、B 18/20、C 19/20，EAR 18/20。McNemar双侧精确`p=0.25`，只作为选择机制的开发信号，不是显著结果。

## 一次性留出

冻结后仅运行：

- 基座：`plain_visibility`
- 启用能力：`type_aware_policy`

主指标是406例配对答案accuracy差值和胜/负/平；次指标是Part A/B/C accuracy、Part A CRR、Part B EAR、非法证据选择。CRR定义为答案正确且所选证据不含superseded decoy；EAR定义为答案正确且不含expired decoy。L0报告两臂相同的注入记录量，以及input/output token与批次时延p50/p95；该协议使用预建store，L1写入/抽取不适用并明确记为未测。

留出运行后不再修改TTL、prompt、gold或case集合。源数据中只有一个选项的`TC-B-0185`保留在主分母；若它位于留出，另外报告排除此例的敏感性结果，但不替换主结果。若优化无净收益，原样关闭该策略；若有收益，也只支持ValidMem方法验证，下一步仍需Trigger真实host trace与编码任务E回执验证。

## 命令

```bash
python3 validmem_codex_runner.py \
  --adapted /tmp/validmem-adapted \
  --output /tmp/validmem-development \
  --split development --batch-size 8 --execute

python3 validmem_codex_runner.py \
  --adapted /tmp/validmem-adapted \
  --output /tmp/validmem-holdout \
  --split holdout --arms plain_visibility,type_aware_policy \
  --batch-size 16 --execute
```
