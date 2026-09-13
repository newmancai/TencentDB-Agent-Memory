# 独立代码审查：answer-feedback-v1

2026-09-13。仅阅读 `feedback.py`、`check_candidates.py`；未读开发/评估输出，未触碰模型或修改实验代码。未发现评估调用加载labels，亦未见current applicability直接放进提示；以下是具体问题和必须收窄的主张。

## 1. 候选按family+args全局合并，不是来源/作用域对象

`signature(rule)`只有id和args，`candidates`跨全部topic持久去重。同一规则参数在不同话题或撤销后重建，会复用原R号与首次来源轮次。`current`也按该signature判断是否有效。因此当前指标是**规则值集合的适用性**，不是某次要求出现的来源身份归责。例如topic A第2轮JSON被撤销，topic B第20轮再次要求JSON：候选仍指first_observed_turn=2，判其active可以算对，但这并未证明第2轮原要求对B有作用。

不必据此改正在进行的规则值实验；报告应明确按等值规则合并，不能声称已完成跨作用域原文来源定位或撤销实例归责。若下一阶段需要此主张，候选需有来源/作用域实例身份，而不是只换评分名称。

## 2. checker未知目前被消隐成无正例，可能虚增完整集合exact

`actionable_violation = key in current and ok is False`使active但checker异常的候选被排除出gold。`score`又直接按这个gold计算完整集合exact，并把oracle_current_plus_checker设为n/n；它没有检查当前active候选是否有checker_unknown。因此存在未知检查时，输出空集合可能被算作“完整无违反”正确，虽然事实只是该项未判定。

应在结果中明确主指标只针对**可观察checker子集**，并另列包含active checker_unknown的任务；不能把定义上界n/n当完整真值验证。当前是否实际发生需由主线程回执确认，本审查未读取结果。

## 3. 上游checker内部吞异常，外层try不保证故障被记为unknown

`check_candidates.py`只把传播出的异常转成None。但此前读过的官方format checker在内部广泛捕获异常返回False；部分辅助导入也吞异常继续执行。排除NLTK sentence模式解决了一个已知依赖，不代表其他False全是纯字面违规。报告只能称所固定checker实现的判定；尤其不要把这些标签直接叫无噪声语义gold。需要保留既有源码/版本和checker合同结果，不必因此扩展数据审计。

## 4. 同事实prose/structured成立，但输入上限可能造成不同可执行性

`examples_for`两种有标签表示确实表达同一candidate→bool映射，没有额外伪造证据；适合作为反馈形式对照。可是prose展开长于structured，完整两例又可能很长；相同32768上限下，可能某臂input_limit而另一臂运行。此时主指标差值包括token表示效率/可执行率，不能全归于更会理解反馈。代码保存error和inputTokens，但score只汇总unknown，未分input_limit、output_limit、unknown_or_invalid。应分项报告，避免将接口完成率当语义学习收益。保留全任务主结果，不后验删除受影响任务。

## 5. 有界训练选择可能选中纯格式/超限错误，并非语义归责错误

开发状态在`prediction != correct`时取首次两例，prediction=None的input_limit或输出失败同样可入选。方案是预设规则，未构成泄漏，但实际得到的反馈可能主要教结果格式或暴露标签，而不修复有效性推理。需记录两例原错误类型并限制结论。去标签臂同样得到经错误筛选的实例，属于含选择信息的对照，不能称完全无监督自然历史。

总体：四臂能够检验给定oracle历史规则候选+checker输出后，受控标签及其表示对**规则值级可归责选择**的增量作用。它不独立验证候选发现、原文证据定位、checker正确性或后续回答改善；开发及评估完整历史也不是部署成本已摊平的证明。
