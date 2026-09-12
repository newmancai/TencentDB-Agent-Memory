# 自然反馈行为：受控监督迁移 v1

2026-09-13，首次运行前写定。主张仅限观察到的反馈行为分类，不代表反馈事实正确、记忆故障归责或后续任务改善。E 不参与。

复用 feedback-audit 固定版本及既有对齐适配。全部有标签 LMSYS 事件训练、全部有标签 WildChat 事件测试；7 个未知事件保留但不训练/评分。按会话隔离。数据历史已审计，尚未对本分类器测试；不宣称来源从未被人工见过。

输入为当前用户消息及之前最后两条消息，按角色标记；每条最多 8192 字符，超长保留前后各 4096。原文保留在本地观察文件。所有臂同一输入，无未来消息、标签文本、来源字段或会话 ID 特征。输出六个原始类别 NEG_1..4/POS/NEU；未核实官方映射前不猜类别名称。

第一步固定廉价强基线：word TF-IDF 1–2 gram（最多20000特征）+ char_wb TF-IDF 3–5 gram（最多30000），各自sublinear_tf、min_df=1；LogisticRegression C=1、class_weight=balanced、max_iter=2000、random_state=20260913。总特征上限50000，学习状态为词表/IDF/线性权重，测试期不更新。没有超参搜索。LMSYS内部固定GroupKFold五折作诊断，各折独立拟合全部预处理；之后全LMSYS拟合并一次测试WildChat。多数类基线由训练标签确定，只是下限，不是强语义基线。

报告六类macro-F1、accuracy、每类P/R/F1/support、NEG聚合TP/FP/FN/TN、多类Brier、最大概率与错误关系、拟合/推理耗时、输入裁剪数、特征数量。按WildChat会话配对bootstrap1000次（seed20260913）给macro-F1相对多数类差的描述性95%区间；缺少某类的重采样仍按固定六类计分。该区间不证明对所有来源泛化或高置信。

后续冻结语义打分器/有界学习头仍需事前固定，必须用相同监督和输入，不能看WildChat错误改prompt/阈值。此首步即使超过多数类，也不宣布B目标达成；它只建立后续必须面对的廉价学习参照。

运行：`python run.py --data ADAPTED_DIRECTORY --out OUTPUT_DIRECTORY`，依赖scikit-learn==1.7.2、numpy==2.2.6、scipy==1.15.3。原始数据和完整引用不入PR；结构化分数及ID级预测可入PR。

## 第二步：冻结语义分数与反馈更新（打分前写定）

已看第一步TF-IDF聚合结果，未检查其测试逐例错误；以下是预定语义路线的具体实现，不再声称WildChat从未评估过。不会依据当前或后续WildChat分数调整类别、输入、prompt、正则或门槛。

官方类别映射已从[固定数据卡](https://huggingface.co/datasets/yuhan-nlp/multiturn-feedback/blob/5339f4d77871636030bf4e43ff26b0756cb1fb2d/README.md)核实：NEG_1重述，NEG_2指出问题并纠正，NEG_3指出问题未纠正，NEG_4澄清，POS正反馈，NEU无反馈。负类优先级按论文：2>3>4>1。

固定本地Qwen3-4B-Instruct-2507，输入与TF-IDF完全相同；系统提示给六类定义和上述优先级，无示例。单次forward取首输出位置A–F六个单token logits；不自由生成解释。冻结臂直接argmax。六类内归一化概率仅是受限分数，并非“模型选择输出字母”的总概率，更不是正确率。记录六token全词表概率质量。

反馈更新臂仅学习六维log_softmax分数到类别的映射：StandardScaler与class_weight=balanced、C=1的LogisticRegression（max_iter2000、seed20260913）。LMSYS内固定GroupKFold5，各折独立标准化/拟合；最终全LMSYS拟合，WildChat只评分。没有新的prompt/示例搜索；学习状态有界为六维标准化参数和六类线性头。比较冻结语义、更新语义、同标签TF-IDF；同语义打分缓存复用，因此反馈臂成本是共有打分加拟合/推理，而非重复生成。这个校准/类别映射实验不能证明模型学会了新的故障归责。

语义程序只接收ID与visible正文，不接收标签、来源或group。后处理读取分离标签训练/评分。输入超32768时记error，不截断/重试；若发生，先报覆盖而不偷偷丢例。六类macro-F1仍为主指标，另报正确性配对和按会话bootstrap更新相对冻结的区间。保持原始标签，所有负结果保存。

## 解释性强参照补充（语义聚合结果后）

看到学习头macro-F1小幅提升且区间跨零、Brier明显降低后，补简单temperature scaling作为概率收益归因参照。明确不是新的未见评估。只用LMSYS标签最小化平均NLL，一个标量T在[0.1,10]有界拟合；不根据WildChat调范围/目标或再调学习头。固定原logits/T，argmax不变。若已解释大部分概率改善，则不将学习头概率变软称为新语义能力。
