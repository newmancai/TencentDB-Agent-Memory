# DECODE human-bot 重标来源只读核查

日期：2026-09-13。此文件仅记录来源和适配边界，不替换当前 pair-v1 的 gold，不启动清理、改写或模型实验。

## 官方来源与具体文件

- 作者仓库：https://github.com/jind11/utterance-rewriting ，README 的 “Rewritten DECODE Dataset” 指向下列目录；GitHub 仓库内的 `data-samples.json` 是改写输入示例，不是 human-bot 证据 gold。
- 作者公开 Drive 目录：https://drive.google.com/drive/folders/1nNnBBm5kHXkw26FW27ztUaHEmPgDbIEa
- 原句非平衡重标文件：`human-bot-unbalanced-new.jsonl`，file ID `1ifYckZyex69I6sf05U7By75NqH38rfIO`，实际读取 1,773,447 bytes、1,889 JSONL 行。小文件读取地址：https://drive.google.com/uc?export=download&id=1ifYckZyex69I6sf05U7By75NqH38rfIO
- 原句平衡重标文件：`human-bot-new.jsonl`，file ID `1xoQl-jaOlPittmiFyAYv1z90pcSGI9Tg`，目录所示 902,169 bytes，实际读取 906 JSONL 行。地址：https://drive.google.com/uc?export=download&id=1xoQl-jaOlPittmiFyAYv1z90pcSGI9Tg
- 同目录还存在 `human-bot-new-t5-large-rewritten.jsonl`（ID `1TDmVcH7fyhtkyFJvcOfwM854lMCH2On7`）、`human-bot-unbalanced-new-t5-large-rewritten.jsonl`（ID `16ezQBuXi0vAL-Un762PZh5G9H-RJJAlS`）和 `train-rewritten.jsonl`。本次没有读取这些改写文件，不可把其机器改写正文当人工原句。

## 人工标签含义

论文：https://aclanthology.org/2022.sigdial-1.56.pdf ，§3.1、Appendix A。

作者说明原 DECODE human-bot 缺少证据标签；合并重叠会话、去除仅一轮会话后，得到 507 个完整对话，再截取至各 bot 发言，产生 1,889 个前缀。首轮三名 AMT 工人标二分类及历史 bot 证据索引；不一致样本由另一组三名工人验证，仍不一致由作者裁决。论文报告非平衡集 453 正/1,436 负，平衡集 453 正/453 负。它们是对原会话的人类重新标注，不是新来源会话，也不是机器 NLI 预测。论文说明不能代替实际文件合同检查。

## 实测 schema 与索引边界

非平衡集全部 1,889 行具有相同键：

```text
turns: [{agent_id: int, turn_id: int, text: str}, ...]
is_contradiction: bool
aggregated_contradiction_indices: list[int] | null
original_model: str
is_in_sentecen_contradiction: bool
```

`is_in_sentecen_contradiction` 的拼写来自文件。没有 `record_id` 或 `conversation_id`。证据索引是零起始的全对话 `turn_id`，不是仅 bot 的序号。例如首行证据 `[5,7]` 对应全对话的第 6、8 句 bot 发言。

实测非平衡集 453 正/1,436 负，平衡集 453 正/453 负。非平衡集证据长度分布（null 视作长度 0）：0=1436、1=366、2=69、3=15、4=3；正例证据全非空。所有证据索引均在全对话范围内、与 turn_id 相等、对应 agent_id=1。

但有 **2 行证据包含末句自身**，不符合当前“历史句→末句”关系合同，不能默默删除索引并声称已适配：

- JSONL 第 253 行（零起始 row 252），4 句，证据 `[3]`，`is_in_sentecen_contradiction=true`。
- JSONL 第 587 行（零起始 row 586），4 句，证据 `[3]`，`is_in_sentecen_contradiction=false`。

该标志总计 true=83、false=1806，且 true 可与 `is_contradiction=false` 共存；不要用此标志替换主标签。这里只记录实际值和冲突，不自行推定标志的完整操作定义。

## 与本地原始包的匹配实测

比较基准：`/home/edarace/Tencent-Memory-2/.local-evidence/topic3-b-feedback-audit/decode_v0.1.zip` 内 `decode_v0.1/human-bot.jsonl`，764 行。

严格 key 为全序列 `tuple((turn.agent_id, turn.text) for turn in turns)`；不读取标签参与匹配。

- 新非平衡集 1,889 行只有 1,827 个不同严格正文 key；57 个 key 出现重复。4 个重复 key 的主标签互相冲突，4 个重复 key 的证据互相冲突。因此正文完全相同也不能直接覆盖一个唯一 gold。
- 新集 717 行严格全序列匹配原集，原集 666 行被至少一个新集行匹配；这些数字的单位不同，包含新集重复，不能理解为一一映射数量。
- 对所有严格全序列匹配配对统计，新旧主标签不同共 84 对；这是配对数量，不是独立原记录数量。
- 新集 1,873/1,889 行能严格匹配某原记录的从开头截取的前缀；16 行不能如此匹配。前缀可帮助链接原始基础会话，但不代表末轮相同，因此不能将原记录的末轮标签移植到该前缀。
- 平衡集 906 行中 14 行正文不在非平衡集严格 key 集合中；因此文件层面不能未经检查称其为精确子集。

另做了一次仅用于来源诊断的确定性文本等价检查：把左右单引号改成 ASCII `'`、左右双引号改成 ASCII `"`，并用空白 split/join 归一化。此时新非平衡集仍有 5 行不能匹配原集任一前缀；平衡集仍有 4 行不在非平衡集归一化 key 集合中。未进一步修补或人工对齐，这不构成运行时输入改写方案。

## 后续适配条件与当前决定

当前不切换 gold。若后续确实采用此来源，应另存来源版本和新旧标签；通过严格正文匹配恢复一个或多个原 `record_id`，再恢复基础会话身份并进行 split 隔离。重复/冲突、末句自身证据、未匹配行应显式保留状态，不能凭行号硬接，也不能把原128条全部宣布已获得定位 gold。本文未计算当前128条的覆盖率。

同一个原会话被切成多个前缀，必须按基础会话归组；不能按新JSONL行随机拆校准和验证。论文与公开文件显示可用的人类证据来源，但还不足以宣称完整、无歧义的一对一适配。

本次只读取官方小文件/目录和已有本地 zip；没有下载模型，没有写入数据副本，没有修改工作树代码或运行推理。唯一写入为本审计文件。
