# 可复现普通能力对照 v1

目的：前一独立助手诊断存在可利用的证据信息，但计算预算不可比。本实验测量两个固定本地模型处理同一原话的能力及实际成本，**不是 B 学习实验**。不根据旧六题筛选模型或改提示。

- CUPID 来源、切分继承 README；排除已用 24 开发 persona，用 `cupid-strong-baseline-v1:` SHA256 排序选择 2 个新开发 persona，完整保留各 3 变体，共 6 题。验证 persona 不用于模型选择。
- Qwen3-4B-Instruct-2507 与 Qwen3-30B-A3B-Instruct-2507；后者固定 HF revision `0d7cf23991f47feeb3a57ecb4c9cee8ea4a17bfe`。选择同一非思考系列作预先指定容量诊断，不声称只有参数量不同或必然更好。
- 复用 `compare_views.SYSTEM`、逐题用户原话历史及消息 ID，无示例；当前目标 reference、factor、variant、persona 不进入提示。各模型使用自己的官方 tokenizer/template，保存实际提示，报告差异。
- greedy、BF16、SDPA、输入上限 24000、输出上限 256 token、提示要求最多 100 词；不静默截输入、不重试失败、不因超词数删除结果。多卡只分片权重，不改变任务信息。
- 两模型顺序运行，30B GPU-only 自动分片、每 GPU 权重内存预算 20GiB；记录实际 placement、加载时间、生成时间、输入/输出 token、错误、词数、p50/p95。不同硬件占用和计算成本，不称同算力或同部署成本。
- 匿名逐题审阅：可见用户要求保留、原话支持/适用范围、引用、reference 覆盖分别记录；主比较计胜/负/平及未决。预选 hash 前两题交叉复核；保留全部分歧和失败，不把参考缺项直接当违令或记忆故障。
- 两 persona 仅能力诊断，不给六变体当独立样本推导泛化置信区间。普通模型即使改善，也不计入 B 收益；后续 B 须在同一冻结基座上比较受控反馈学习与无学习/无标签对照，使用新 persona。
- user-only 无法恢复“这个版本很好”等评价对象时，标为不可判，不用隐藏 reference 补对象后惩罚模型。除逐题结果外按 persona 汇总，不把相关变体当独立证据。
- OOM 等运行异常会中止 runner；保留日志及已完成回执，未完成题留在六题分母，不报已完成子集为完整运行。4B 既有本地目录未含 revision 元数据，另存实际文件 SHA256；不事后假定其等于最新 HF revision。

运行：`strong_baseline.py prepare --root <cupid-evidence> --out <new-folder>`，然后对 `<new-folder>/4b` 和 `/30b` 分别 `run --model <local-model>`，30B 添加 `--shard-gpus`。模型下载成本和失败也单独保留。

官方依据：[模型卡](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507/blob/main/README.md)、[Qwen 快速开始](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/quickstart.md)。模型卡能力主张不替代本地测量。
