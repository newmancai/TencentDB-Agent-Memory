# B Assertion Update Compilation v1

在target binding v1已正确绑定的8个合成开发纠正上，固定target assertion，要求Codex只
提取替代值并原样保留target scope。4个binder已拒绝的案例不调用编译器，避免在unknown
上强造记忆。

固定`gpt-5.6-sol`、reasoning `medium`、8个ephemeral只读空目录会话；输出为
`{target_id,value,scope}`，deterministic checker要求target、值和scope三项完全匹配。
失败不重试，不修改target案例、prompt或标签。target trace复制为前缀，compiler decision、
新assertion和outcome追加后必须通过Phase 0 replay。

预设门槛为7/8精确通过。达到只允许进入一次有界端到端组合；不表示自然反馈抽取、长期
状态冲突处理或生产写入已解决。低于门槛且无执行故障则停止该编译配置。
