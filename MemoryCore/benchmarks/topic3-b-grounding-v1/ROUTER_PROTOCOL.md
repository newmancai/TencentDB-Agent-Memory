# 受控反馈学习选择审核方式 v1

运行前固定。排除此前200+24题和30配对全部端点，从剩余有效同答案/同证据配对每会话固定新seed hash取至多10对。整会话按SHA256(router-split-v1:+group)排序，前5为feedback、后5为validation；无端点/会话跨当前划分。十会话历史均曾参与研究，本次仅未用于此前探针的题，不能称未见来源泛化。

两臂原普通ABC与联合ABC原样复用，不改prompt，不加入gold；联合候选只用可见speaker。每对两端两臂完整prompt均<=4096才共同入队，否则整对unknown。不裁剪。离线跑两臂是为了获得受控反馈/评估，部署选择只跑一臂；两臂调用次数均1但token成本不同，实际报告。

固定调用前六特征：问题词数、log1p答案词数、log1p消息数、问题中可见speaker名字数、答案词在问题点名speaker消息中的最大覆盖、在其他speaker消息中的最大覆盖。仅text字段作词覆盖，不读QA类别/positive标签/模型输出；中文/复杂指代能力不作假设。

学习目标是feedback队列中联合是否比原更正确（+1/0/-1），DecisionTreeRegressor(max_depth=2,min_samples_leaf=10,random_state=20260913)，预测>0选联合，否则原；不搜索参数。深度2至多4叶，状态可导出。参照always原、always联合、feedback整体选较好固定臂（平局原），及同六特征/同复杂度DecisionTreeClassifier直接判QA标签，避免把便宜词面判别能力算路由创新。

validation先冻结路由再计算gold指标。报告共同覆盖、混淆/误报、配对相对反馈选出的固定臂、所选路径/成本、训练反馈调用量。完整双臂评估成本与未来所选单臂估计成本分开。QA代理标签不是独立packet gold，所有学习只称受控开发验证。不得根据validation改特征/阈值/树深或筛题；负结果关闭此配置，E不扩。
