# 审查片段示例学习 v1（运行前固定）

沿用前一轮模型、SYSTEM提示、用户历史证据、greedy、24k输入/256新token上限及100词提示。排除18个已用于此前开发实验/语义审计的persona，按SHA256(cupid-fragment-learning-v1:persona)取4新开发persona，每个全部3变体，共12题。先固定任务后运行，不按结果选择变体或修改示例。

四臂：frozen无开发示例；unlabelled两个旧开发完整用户历史+旧草稿；feedback相同历史/草稿加受控参考及原审查；reviewed相同两个开发历史+经审查接纳的连续生成片段及来源ID、遗漏说明。前3臂复用上一轮实现；仅替换request-only参照为reviewed。当前请求单独参照已在前轮诊断，不作为本轮唯一对手。

所有臂目标任务历史相同，候选固定不改检索/E；训练材料表示、监督信息和实际token成本不同。reviewed相对feedback的干预是生成后审查选择的组合，不能归因为完全自动压缩或某条纯算法规则。第二个片段仍有覆盖限制，明确传入limits，未改为完整gold。训练历史都保留，不同时额外裁掉示例上下文。

按题轮换运行顺序。记录全部调用和错误，不重试追分。新任务reference、factor、group、variant不进入模型；two-example来源与新persona隔离。学习是在受控教师反馈下构造有上限的示例状态，不是权重训练或模型自动产生的高置信监督。

两名独立助手分别匿名审查6题，按源文支持、当前目标内容及强度/范围实质错误分层；不因无引用单独决定语义排序，参考外内容不自动算错。审查意见非官方grader，保留分歧与部分覆盖；按persona与variant报告，不把变体视为真实连续事件。目标是检验新状态相对冻结和同示例对照的收益，尚未接原生off/fallback。

```bash
python fragment_learning.py prepare --root CUPID_LOCAL_ROOT --out NEW_FRAGMENT_DIR
CUDA_VISIBLE_DEVICES=0 python fragment_learning.py run --out NEW_FRAGMENT_DIR --model /path/to/Qwen3-4B-Instruct-2507
```

依赖前述适配、learning/state与compiled/reviewed-state。新结果不与上一轮12题直接相减；前期2例编译6266输入/241输出/7.892秒、旧开发生成及未计量教师成本须另外披露。
