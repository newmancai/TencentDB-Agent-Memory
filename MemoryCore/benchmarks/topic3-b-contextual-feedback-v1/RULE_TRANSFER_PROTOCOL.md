# 冻结规则的新persona迁移 v1

30B普通能力对照受下载影响，本实验并行运行，不替代或修改它。测试已生成规则能否在同一冻结4B基座上产生B增量价值，不等待更大模型再选择有利结果。

排除包括strong-baseline在内的26个已用开发persona。以`cupid-rule-transfer-v1:` SHA256排序取4个新persona，保留全部三变体，共12题。任务按`rule-transfer-task:`排序并循环轮换四臂次序。persona才是独立来源，不据12变体声称统计泛化；126最终验证persona不用于调参。

四臂固定：frozen无经验；rules_unlabelled为旧观察/草稿编译的规则；rules_feedback为同观察加受控纠正编译的规则；feedback直接读取相同旧观察/草稿及纠正。规则原样使用，不追加人工规则、不按新题编辑。新题完整user-only历史和当前请求完全相同，无reference/factor/type/group入推断。两个规则臂格式及容量上限相同；实际长度不同，直接反馈臂输入更长，不称严格等token/同可见训练信息。核心区分：纠正是否比无纠正规则有用；编译规则是否比直接反馈具有质量/成本价值。

Qwen3-4B-Instruct-2507 BF16/SDPA、greedy、输入24000/输出256 token上限、SYSTEM原样要求100词。每题每臂一次，不重试/删除失败。48调用，输出超词/截断分开报告。另计2次编译12100输入/238输出/8.755s；如有摊平主张，单列训练成本与部署假设，不能只比较短prompt。

匿名审查先源文要求/范围/引用和偏好排序，再单列reference覆盖；同题A/B/C/D随机映射，不给模型路径/成本。预选排序前4题交叉审查，保留未决/分歧，不改gold、不把参考缺项直接当违令。source-only缺失父回复对象时不可用reference补。100词无需罗列全部条件性细节；主比较rules_feedback分别对frozen、rules_unlabelled、feedback的胜/负/平/未决，按persona展示。

实验只验证受控反馈编译的冻结状态迁移，非自然用户反馈发现真值、权重训练或Native Gateway off/fallback。E不变。负结果只能界定当前两例规则编译配置，不关闭全部GEPA/ACE/B方向，也不回到这12题追提示。
