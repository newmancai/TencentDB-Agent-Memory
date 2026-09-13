# 可迁移查询表示反馈：开发协议 v1

2026-09-13，模型运行前固定。候选假设：先前受控答案揭示的检索意图能否训练一个共享、有限容量的查询修正，而不是保存旧消息ID。文档与基座embedding模型冻结，旁路仅改查询表示，不改FTS/向量内核。此为B受控反馈的学习用途探针，不把检索本身当创新。

LoCoMo类别1/2/4引用精确的全部1438题；按SHA256(query-feedback-source-v1:+source)排序，前5会话feedback、后5validation。十会话均历史研究暴露，本次仅当前实验的来源隔离，非最终未见验收。沿用单消息speaker+text，不给模型参考ID。文档ID改为不含证据信息的位置ID。feedback同时编码Q、Q+Accepted answer:A；validation只编码Q，输入文件没有其答案。评估标签独立文件，不进入编码/拟合。

阶段一：冻结Qwen3-Embedding-0.6B，官方query instruction模板、last-token pooling、1024维L2归一化，原文单消息不改；每输入4096上限，不截断，超限单列并保持共同可比分母。查询instruction固定为Retrieve relevant dialogue messages that answer the question。直接比较feedback批次Q与Q+A检索all/any@10，并建立validation仅Q的冻结强基线。当前A的编码结果是后见代理，不是语义gold；先确认它在feedback是否有增量，不自动执行拟合。

若阶段一支持后见目标价值，阶段二固定一个共享残差映射：令X是feedback Q向量，D是同题Q+A向量减X，W=(X^T X+I)^(-1)X^T D，输出normalize(x+xW)。无截距、alpha=1，不搜参。对照冻结原向量、全体feedback平均残差平移、将D按固定hash循环错配后的同容量W。错配保留目标分布，区分通用校正与问题条件反馈。矩阵最多1024x1024，不存文档ID，验证可检索本来源全部原文。

全部方法共享冻结模型/文档和仅Q评估输入，top10预算，报告逐来源参考any/all与macro recall、词数、训练/编码/检索成本。错配、平均平移均用相同feedback可见信息。若学习不胜这些强控制，关闭当前残差映射配置，不在validation调alpha/维度/instruction/归一化。矩阵不能替代高置信反馈的语义验证；teacher增益也不等student可学。

这不是ReFIT复现：ReFIT在当次检索以reranker分布更新当前查询；这里检验先前已接受答案能否形成跨来源共享映射。当前尚未编码、拟合或运行模型。真实MemoryCore融合强基线、开关/加载失败/超时回退和内部移植仍需后续实现，不能以研究numpy检索替代完整验收。
