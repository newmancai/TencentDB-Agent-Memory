# v8 RealMem 归责负结果独立诊断

这是助手事后参考审计，不是新增 human gold、官方 grader 复现或因果干预实验。未改任何标签、模型输出、prompt 或 runtime。

## 范围与方法

采用 `model32/results.jsonl` 的最终评分；32k 补齐沿用原输入与提示，不能把此前未执行评分当作语义失败。最终总体由主报告统计：RealMem 17 题，human RetrievalError 5、AnnotationError 12；direct 命中 memory 0/5、误报 1；factorized 命中 3/5、误报 3。精确归责分别 6/17、4/17。

按首次已成功执行结果中的 ID 排序，固定选前 2 真命中、前 2 漏检、前 2 非记忆误报。六题在补齐后原评分保持。此前超窗口的 `ba27e4486a6b38912c4f`、`158300a5c8225ccfe964` 不纳入本次六例语义诊断；现已补齐，不再算模型错误。本报告不是对最终全部 3 个误报的穷尽分析。

读取 task query、完整 prediction、原 graph 对应 annotation 的 source_evidence/golden_answers/reason；完整 context 做了原文检索和 10 个 retrieved unit 逐项主题检查，并展开相关段落。未把关键词不出现或源全文未精确匹配独立作为“语义证据不存在”的证明。原始六题与完整 annotation 保存在 `diagnosis-<id>.json`，选择清单为 `diagnosis-selected.json`。原 graph 来自 `memtrace/rag-Adeleke_Okonjo.json` 与 `rag-Ethan_Hunt.json`。

## 六例

| ID | human 标签 | factorized | 核心观察 |
|---|---|---|---|
| 00547101fb5b955d889c | RetrievalError | memory，命中 | “下一步”是既定健身计划推进，不能仅按眼前 meal plan 推成做饭步骤 |
| d1471938f9f94102ea5c | RetrievalError | memory，命中 | 缺产品集成规格，但已有同产品 Food Tour 线索；缺检索与错误使用可同时存在 |
| 2de832600580ee80f603 | RetrievalError | 非 memory，漏检 | 泛化 CoT 建议没有恢复既定 sprint 的具体进度 |
| 5959790f918d90a0b693 | RetrievalError | 非 memory，漏检 | asyncio/httpx 已在问句；缺的是 LLM API 任务身份，回答错接滑雪项目 |
| 7688ce879edd09fd420f | AnnotationError | memory，误报 | 用户确认储蓄承诺，参考答案额外推进多个项目并不是当轮必要答案 |
| 939277b1bf0f94a19ea4 | AnnotationError | memory，误报 | “今天的 protocol”指代不清；参考澄清与生成运动方案都须单独评价 |

### 1. 00547101fb5b955d889c：真命中，任务推进信息缺失

Query 确认 jollof/fish meal plan 并问 “What's next for us?”。Prediction 给备料、准备、烹饪、摆盘、享用等下一步。Human source `aa50063a-2@1` 则列出 Nutrition Strategy、Training Protocol、Recovery & Lifestyle、Tracking & Adjustments 四项健身计划；gold 接到 Training Protocol。Retrieved context 的十个单元主要是商业、WhatsApp、金融、安全等，不含上述计划推进说明。

原来源支持 retrieval 归责，但仅看 query，继续做饭也并非语法上不可能。在线模型要知道用户要求“继续我们已约定的计划”，并确认缺了哪一段；离线 source 才能证明该记忆确实存在。不能把一次判 insufficient 的命中等同于已定位丢失记忆，更不能据此持久失效当前其他记忆。

### 2. d1471938f9f94102ea5c：真命中，但不能解释成只有检索失败

Query 要把 “this product” 接入 KudiFlow 的 Technical Integration Brief。Prediction 完整写成 Cross-Border Remittance，而 gold 是 Lagos Food Tour Guide V2.1 的移动端指南、地图、15 餐厅、展开区块等。Human 指向漏掉的 `167672c0-18@1`，这是具体产品集成规格。

关键交叉核查：visible context **已有** “KudiFlow Lagos Food Tour: Island/Mainland Split (15 Restaurants)” 完整路线，以及用户同意 Hard Rock Cafe 换 Terra Kulture 的原文。不能说完全没检索到 Food Tour。它没有覆盖交互产品规格，但足以构成同产品候选；回答转去汇款还存在任务对象选择问题。保留 human RetrievalError，同时承认单一根因标签未排除下游 misuse。由“缺一份规格”推出“响应生成完全无责”也不成立。

### 3. 2de832600580ee80f603：漏检，通用可答不等于接续正确

Query 确认初始 prompt library 后问 sprint 下一关键步骤。Prediction 给 advanced CoT、练习、指标、反馈与扩充库的泛化建议。Source `e9a4572c-2@1` 是固定七天计划，`e9a4572c-5@1` 是已进行 Zero-Shot CoT 与日志的进度；gold 指向 Day 2 的 1.4 Few-Shot CoT、1.5 Self-Consistency/Majority Voting、1.6 Iterative Refinement/Debugging。Context 十项主要覆盖故事、CV、合同、滑雪与 promotion engine，缺这份 sprint 计划与进度。

Sufficiency 输出 A（足够）。可观察的失败是把能够提供合理领域建议误当成能够恢复既定任务下一步；不推断模型隐藏思考。该题没有合理拒答争议，已有来源可以补足真实计划。即使泛化答案有价值，不能替代遵循先前约定的任务契约。

### 4. 5959790f918d90a0b693：漏检，工具骨架正确但项目错了

Query 已明确 `api_client.py`、`asyncio`、`httpx`，要求立即给代码。Prediction 确实提供完整异步 HTTP 客户端、gather 与错误处理，却命名为 AltaySkiResortAPIClient，读取雪深、雪道整理、坡度、排队指标。Source `1713b69e-3@1` 的真实需求是 OpenAI/Anthropic 外部 LLM、多供应商抽象、突发高并发、云端/serverless Python 客户端。Retrieved context 有滑雪同步项目，另有 GPT-4 生成 Flask endpoint 的练习，后者不是多供应商客户端规格。

保留 RetrievalError。Human reason 中“缺 asynchronous httpx”过宽：这些已在 query；“缺 GPT-4 偏好”也不能解释为完全没见 GPT-4，因为 context 有三处练习提及。可靠的缺口是具体 API 的任务身份与设计约束。不能把参考实现所选 `tenacity` 每个细节都自动变成必须检索的旧事实。Sufficiency 为 C、misuse 为 B，显示该分解并未将本例识别成 memory。这个错例支持分别评价“通用代码能否写”“此代码是否属于当前项目”“项目身份能否从历史恢复”。

### 5. 7688ce879edd09fd420f：误报，当轮不需要参考答案扩展的那些记忆

Query 表达 NGN 50,000 每周 Hustle Insurance 承诺、收入高时加快、五周目标，并准备本周执行。Prediction 确认承诺、鼓励首笔落实与记录进度，贴合当轮请求。Gold 除确认外推进 KudiFlow 品牌/素材、WhatsApp 隐私、Facebook Business Manager、Apprentice Customer & Agent Onboarding、NaijaCoin 等。Human 认为多个 gold 细节不受 cited source 支持，标 AnnotationError。

Context 本来含多项 Hustle Insurance 和 Pay Yourself First 记录；不能简单说不足以确认这项承诺。Human reason 又提 evidence 未建立 50,000 承诺，但 query 自身提供了金额，不能要求所有问句事实再出现于旧 source。AnnotationError 的更强依据是 gold 多出的无根据要求，而不是金额不在旧 source。

此例最清楚地揭示 insufficient→retrieval 的逻辑漏洞：为完成参考答案所有扩展内容，可能需要更多历史；但用户没有要求这些扩展，回答不需要它们。不能由此认定检索有错。标 AnnotationError 也不是评判所有生成句绝对完美，只是没有该例 memory 归责依据。

### 6. 939277b1bf0f94a19ea4：误报，参考澄清与生成猜测应分开

Query 回来后要 re-establish baseline，问今天 protocol。Prediction 给详细十分钟阻力带训练。Context 的确有 under-10-minute resistance-band protocol、tech neck 与姿势目标，所以运动建议不是全无可见来源，但同时有很多其他任务，不能仅因此确定“今天”所指。

Gold 承接 noise anomaly 后反问要恢复哪个具体 protocol。Source `a09a520e-9@1` 只讨论过去的 disruption、恢复率与优化下次 iteration；human reason 认为没有今天计划，也未建立多个 protocol 或要求澄清的依据，因此标 AnnotationError。

独立判断：来源不足以确认今天协议很明确，但“所以问一句澄清是不合理”并非唯一可接受解释。歧义下澄清本身可能合理。此处应保留 annotation 分歧，而非把 human 标签偷偷改成 response 或 memory。反过来 AnnotationError 也不证明生成的详细运动方案正确；它可能把旧训练要求错当今天安排。本例没有模型拒答，只有参考答案的澄清行为；不能归入“模型合理拒答却被罚”。

## 逻辑间隙与可检验的新理解

“Retrieved context 不足以完整回答”只描述输入状态；“Retrieval 应归责”还需要至少三件事：当轮确实需要该信息、权威历史中存在可恢复的相应内容、缺失内容对这个回答错误有作用。第 1/3/4 例有离线来源支持；第 5 例连任务必要性都不成立；第 6 例目标解释和参考评价仍有分歧。第 2 例则说明 retrieval 与 response 问题可以共存。

当前由足够/不足到 memory/response 的分解没有单独容纳“任务指代不清”“参考答案无依据”“缺少任务必要性证据”。其中任何一种都可能让标签输出错误。也不能把所有非 memory 都当 response：本 eval 的 12 个非 memory 标签实际均为 AnnotationError。该类别在没有 gold/source 的在线输入中尤其难独立识别；事后看 annotation 的可解释性不能当线上可识别性。

因此新 insight 不是再补几个问句关键词，而是改变研究主张：B 的第一输出可是一条**具体待核验的信息缺口及用途**，不是已确认的检索故障；E 再查原会话/可达记录，确认存在、归属和对当轮请求的必要性，反馈给 B。可检验的目标应分别是缺口候选覆盖、无必要核验代价、核验后归责 precision，以及补回证据是否修复答案。未核验时不得直接把“信息不足”升级成记忆删除/失效。

还需要区别“离线 root-cause 分类”与“线上可操作反馈”：只有 query/context/answer 时，缺记录还是没有该记录、用户是在确认还是请求接续、参考是不是错误，可能不可辨识。允许输出这种有根据的不确定性，但必须报告覆盖和真实成本，不能把全弃权包装成高置信成果。这些是下一协议的方向，不是本六例已证明有效的方法，也不在当前 17 题修改 prompt 再追分。
