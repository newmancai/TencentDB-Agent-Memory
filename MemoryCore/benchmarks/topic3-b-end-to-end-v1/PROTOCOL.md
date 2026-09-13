# B End-to-End Synthetic Holdout v1

## 目的

固定前序已通过的target binder、显式纠正值编译和精确scope规则，在4个从未用于前序
组件检查的合成holdout项目上跑一次完整级联。它测试组件组合，不回看或修改前序案例。

## 级联与调用上限

每个项目：

1. 3个oracle候选assertion、实际旧answer和显式用户纠正进入固定target binder；
2. 仅当binder唯一绑定时，固定compiler提取新值；scope由系统从target机械保留，不让
   模型扩写；
3. 精确scope匹配的后续任务运行`adaptive/frozen`两个隔离槽，固定散列交错顺序；
4. 一个冲突项目上下文只运行adaptive安全检查，scope gate必须omit并得到`unknown`。

最大16次Codex调用（4 target + 4 update + 8 matched future）另加4次mismatch safety，
合计20次；上游失败时不强行调用下游。固定`gpt-5.6-sol`、reasoning `medium`、ephemeral
只读空目录、JSON schema、无工具/浏览/文件访问、无重试。所有评分均为字段/集合精确
比较，无LLM judge。

## 预设门槛

- target至少4/4、update至少4/4；
- matched future：adaptive至少4/4，且相对frozen配对净胜至少3；
- mismatch safety：4/4返回unknown且没有注入跨项目assertion；
- 完整Phase 0 replay通过。

任一组件未达门槛且无执行故障则不调本holdout，回到该组件；全部达到只支持“结构化
候选+明确纠正的合成开发闭环”，不支持自然反馈、真实业务或production结论。
