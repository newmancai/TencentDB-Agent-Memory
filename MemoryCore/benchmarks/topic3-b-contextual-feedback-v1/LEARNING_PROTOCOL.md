# CUPID 有界纠正示例学习 v1

运行前固定：从上一历史视图实验每个persona按SHA256(cupid-feedback-example-v1:ID)取一条，共2条。状态保存该例完整用户历史、已有用户原话组草稿及原独立审查意见和官方参考要求；容量2。它是受控监督驱动的上下文示例状态更新，不是模型权重训练或自然用户直接纠正。审查意见可能有误，参考不是逐句适用gold；不把示例质量先验称为高置信。

排除前14个开发persona，按SHA256(cupid-feedback-learning-v1:persona)取4个新开发persona，每个全部3变体，共12题。未使用验证侧调参；这是开发跨persona对照，不是独立最终验收。冻结提示沿用compare_views.SYSTEM，不按新结果修改。

四臂：request只当前请求；frozen当前请求+全部用户历史；unlabelled增加两个开发例的相同原始输入及旧草稿；feedback在相同示例上附已有受控纠正。不学习找session，不改检索候选，不用E。新任务隐含factor、目标偏好、checklist与变体不进推断。训练参考仅限两开发例，禁止混入新任务答案。

四臂相同模型Qwen3-4B-Instruct-2507、greedy、24k输入硬上限、256新token/100词提示。按任务轮换运行顺序。后三臂新任务证据相同，监督信息和消耗token不相同；只称相同目标证据和预算上限，不称严格等消耗。纠正相对去标签的差别是干预变量；请求单独组用于识别请求已有信息，不能作为唯一弱基线。无例外截断补跑，输入超限或输出截断结构化保留。

审查在生成完成后匿名四组，提供原文和官方当前参考。分别判断目标内容full/partial/absent、可见的强度/来源/范围错误，比较feedback与frozen和unlabelled；请求已有要求不计为记忆新增信息。助手语义意见非官方grader，保留未决和独立复查分歧；部分覆盖不自动算错误。按persona和variant检查应变与不应变，不能把变体当自然连续时间流。12题/4persona不作统计泛化。完整模型成本报告，前期开发调用和助手标注成本单列，不能当免费学习。

复现：

```bash
python feedback_learning.py prepare --root CUPID_LOCAL_ROOT --out NEW_LEARNING_DIR
CUDA_VISIBLE_DEVICES=0 python feedback_learning.py run --out NEW_LEARNING_DIR --model /path/to/Qwen3-4B-Instruct-2507
```

prepare依赖固定prepare、events、views及scope-audit生成的文件。状态与完整输入仅留本地，PR保留选择ID、开发纠正出处和生成结果。研究runner未实现MemoryCore运行时off/fallback；frozen臂只为研究对照，不冒充基座开关验收。学习有收益后再接原生B旁路，不能以当前runner代替可移植交付。
