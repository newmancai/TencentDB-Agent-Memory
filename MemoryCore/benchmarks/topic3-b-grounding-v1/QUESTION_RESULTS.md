# 保留问句位置探针：未改善关系核验

2026-09-13。200个LoCoMo复用开发QA、十会话，每会话各类别1/2/4/5取5题；400次冻结detector forward，均未超限。共用原问题、oracle引用证据与官方候选答案，仅改变问题在双序列输入中的位置。不是生成任务、B检索发现或反馈学习，标签仅由原QA导出，不是独立人工证据包标签。

## 结果（评分v1.1）

|模式|覆盖|不足告警TP/FP/FN/TN|不足precision/recall|balanced accuracy|
|---|---:|---|---|---:|
|普通：Q在context|200/200|5/56/45/94|8.20%/10.00%|36.33%|
|绑定：Q与A同序列|200/200|2/56/48/94|3.45%/4.00%|33.33%|

绑定相对普通4胜7负189平。类别1正确40→39/50，时间类8→7/50，类别4为46→48/50，对抗5→2/50。不采用新默认，不在200题调prompt或反向告警。普通处理38707token/3.942s，绑定39074token/3.724s，合计77781token/7.666s，仅forward计时；没有生成token。session17804 exit0，自有模型退出，无E/MemoryCore/production。

## 首token接口修正

v1预定“跨答案边界token不计”，实际绑定200条首token均包含prefix最后的单个空格；18条短答案因此全unknown，其余丢首token，不能公平比较。原v1结果单独保留。独立agent用tokenizer也发现同问题。

v1.1逐条实核越界部分仅一个空格后，接纳与答案相交且越界为空白的token；非空白越界直接失败。只重算已有输出，两臂一起评分，不重跑模型、不改gold/阈值。处理token成本按实际forward计，不能漏计原18条评分unknown的成本。协议变更见 [QUESTION_PROTOCOL](QUESTION_PROTOCOL.md)。

## 固定次序的四例机制审读

按类别2/5、ordinary误差、ID字典序各取前2例，未据它们修改方法。这里是助手证据审读，不是新官方grader：

- conv-26:1，2022绘画年份：引用D1:12只含展示图片与caption，未给年份；原QA答案相对完整会话，当前引用包不足。此例不能把detector告警直接当错误。
- conv-26:21，picnic日期：时间戳6 July，消息last week，参考答案前一周；需要相对时间解释，不是直接字符串支持。
- conv-26:156，问Melanie的收养意愿，给的证据是Caroline第一人称意愿；候选文字虽有来源，主体不符，两臂都未正确识别不足。
- conv-26:160，问grandpa礼物，来源说grandma送necklace；答案名词有出处，但关系不符，普通路径未告警。

前两例说明QA支持标签与局部引用包充分性并不等价，不能把总体低分全归因于模型。后两例为可见具体关系错配，支持继续研究语义关系核验；**仅移动问句位置的当前配置不解决它**，不表示关系核验方向达到上限。

## 路线决定

关闭“问句与答案放同序列即可改善”的当前配置；不继续格式变体。保留受控QA关系任务和冻结detector参照。下一步需要直接的普通语义核验强基线，明确判主体/关系/时间下是否支持原答案，并先用共同更完整证据合同解决引用包不充分。不能为此只修四例或挑对抗题；需要重跑共同基线、单列无独立packet标签的限制。之后才决定反馈学习更新什么，不把新的judge或oracle证据算自优化。

已有长会话数据被复用，无法称未见泛化；本轮只证明这项输入位置配置未有收益，原题独立方法验证和反馈学习仍待完成。

## 复跑

```bash
python question_probe.py prepare --source LOCOMO_JSON --out RUN
CUDA_VISIBLE_DEVICES=0 python baseline.py infer --tasks RUN/tasks.jsonl --model MODEL --out RUN/predictions.jsonl
python question_probe.py evaluate --run RUN --out SCORED
```

推理沿用固定base权重/环境；prepare/evaluate只依赖标准库。发布抽样标签/排除/两版评分，正文与token概率留本地。每类别抽样前的排除为96开放推断与6严格类别未解析引用；不是全数据仅6未解析（全量9中其余3在类别3）。
