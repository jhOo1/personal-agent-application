# QAMC 当前判断与下一次机制对照

## RPEval 已执行成稿的验收对照

固定同一 V1 原稿和已生成的 FREE、DELTA 修改稿。21 道共同有效题上，通用与任务行为验收在两种生成路径均为 18/21。两种 FREE 验收都接受全部 23 份实际修改稿，家庭冬游的无关露营偏好仍被接受。两种 DELTA 验收都拒绝重复的 Omega-3 建议，失去旧评测的争议加分。无新增生成或评分。保留 V1，当前结构化验收尚无同预算增益。[结算与真实执行证据](implementation/reports/qamc_contextual_match_v2_20261112/rpe_outcome_accept_v22/READOUT.md)

## RPEval 单调用决策编辑已结算

固定 24 道已曝光单偏好题和 V1 底稿。两臂共享只读索引、任务、原始历史和候选，各用一次 Qwen API。原口径的 21 道共同有效题中，V1 和自由修订均为 18/21，限定编辑为 19/21。唯一相对 V1 的等级增益来自仍有鱼虾推荐且文字重复的 Omega-3 题。仅规范原提案的列表标记、额外评分 9 份成稿后，限定编辑降至 17/21，实际可见不适用的露营和餐桌布置历史被重新引入。保留 V1，后续优先检验干预适用性、具体选项和重复控制。[结果、基线和执行证据](implementation/reports/qamc_contextual_match_v2_20261112/rpe_decision_delta_v21/READOUT.md)

BenchPreS 的 117 个固定成稿非加粗位置，两种自动评分均给外部 Selectivity 独胜的只有两个，跨两个画像。其中一份在原 Qwen 评测中损失了 Gate 已实现的加粗。值得验证移植具体沟通动作是否能得到增长并保住适用格式。两种评分的分歧单列。[零调用审计](implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/CONSENSUS_HEADROOM.md)

## RPEval 固定底稿修复主对照已结算

24 道原开发题，两臂共享一次诊断、RP 底稿、候选及原始任务与历史。原历史口径的 13 道共同有效题上，限定修复、自由修订和 V1 见证替换均为 10/13，RP 为 9/13。植物增肌得到两种有效的新成稿，限定修复只删冲突备选。独立补充实验复用 4 条定位原回执。纳入同一分母后，自由修订为 11/13，限定修复仍为 10/13。早午餐题只改开头的筛选条件，未给出具体特色选项。两段合计 59 次请求，9 次交付未知。保留现有 V1 和本轮主结果，后续检验局部修复能否落到真正需要联动的选项。[主结果](implementation/reports/qamc_contextual_match_v2_20261112/rpe_protected_repair_v2/READOUT.md) · [补充结果](implementation/reports/qamc_contextual_match_v2_20261112/rpe_protected_repair_v2/LOCATOR_RECOVERY_READOUT.md)

此前独立启动的本地奖励模型已结算。与见证替换在所有 24 道上的 Match 逐题相同，同一旧分主表均为 19/22，且选择的成稿在 13 道共同题不同。见证替换的 FM 更低。后续修复仅依赖 API 和确定性程序。[归档对照](implementation/reports/qamc_contextual_match_v2_20261112/rpe_heterogeneous_reward_v1/REWARD_READOUT.md)

## RPEval 以明确冲突触发整稿替换

用相同三份已评分完整候选，22 道共同题上，见证替换 19/22，单次普通盲选 17/22，仅标默认答案的同报文控制 18/22，固定 RP 17/22，两个外部适配各 18/22。三选手都有效的严格 21 题，见证与默认控制均 18/21，OPB 为 1 对 4。两道原 RP 失分确有饮食或材质范围的行为修复，普通盲选也做到了这两次替换。五份替换提案全通过，逐字校验的前后成绩一致，不能将收益归到程序校验。之后沿同一个方向检验能否只修实际决定并保护原答。冻结的外部权重排名单独结算。[结果与范围](implementation/reports/qamc_contextual_match_v2_20261112/rpe_constraint_veto_v1/READOUT.md) · [默认控制](implementation/reports/qamc_contextual_match_v2_20261112/rpe_constraint_veto_v1/DEFAULT_CONTROL_READOUT.md)

## 当前研发口径与 RPEval 盲选

最新 qamc-v3 讨论将三个基准的真实失分拆开。RPEval 的偏好适用性与作用强度要分开测。BenchPreS 以交际情境和正式交付为条件，核验适用表达是否真正进入成稿。PersistBench 分别量化跨域、迎合与严格有益使用，三者是回答级结果。三个基准共享“当前任务约束 → 历史是否和怎样进入决策 → 实际交付”的研究问题，各自保留作者定义和强对照。允许对已曝光开发来源做定向优化。论文主张限定在实测基准和可比协议内，封存数据和当前题参考答案始终与推理隔离。

RPEval 开发观察已经改变当前优先级。单候选继续使用 17/22 的归档 RP 路径，多候选继续使用 IPE-C。同一批 RP、Des2Gen、MemAdapter 成稿有 21/22 的事后 Match 上界，普通盲选为 17/22，固定两个外部适配各 18/22。冻结模型臂使用同样的候选池，独立结算。弃用普通盲选作为当前替代方案。完整分数、争议、预算及恢复命令均已归档。[同题结果](implementation/reports/qamc_contextual_match_v2_20261112/rpe_heterogeneous_reward_v1/DIRECT_READOUT.md) · [奖励模型协议与恢复](implementation/reports/qamc_contextual_match_v2_20261112/rpe_heterogeneous_reward_v1/LOCAL_RUNTIME.md)

## 论文协议恢复

PersistBench 的固定 Vertex Kimi K2 Thinking 托管端点已退役。BenchPreS 的 DeepSeek-R1 原权重仍发布，但项目内还没有成功的同名评分回执。四个公开模型目录检查、原生评价差异和下一可核验入口已归档。保留全部旧分。[路由复核](implementation/reports/qamc_contextual_match_v2_20261112/native_judge_provider_viability_v1/READOUT.md)

BenchPreS 同成稿同报文对照显示，程序和模型各改变非加粗判分。提出的“未证实断言转成正式沟通行为”确有可观察的事实缺口，但拒赔申诉与学业说明同属唯一有该适用客观属性的画像，暂不启动跨画像增分试验。第二画像的中性视角按其原标签另报。性能筛查优先查 RPEval 合法 C 的实际实现失分，奖励模型仍按冻结面板独立结算。[同题复评](implementation/reports/qamc_contextual_match_v2_20261112/bench_reflection_prompt_bridge_v1/READOUT.md) · [来源资格](implementation/reports/qamc_contextual_match_v2_20261112/bench_relation_action_eligibility_v1/READOUT.md)

## 最新结算 · RPEval 候选数量分支与 BenchPreS 专用简化

RPEval 新增一个可运行的开发基线。原候选只有一条时使用原 RP 历史路径，多个候选时保留 IPE-C。单偏好共同 22 题由 15/22 到 17/22，重建 RP 同为 17/22，Des2Gen 与 MemAdapter 各 18/22。多偏好 295 个可恢复路由完全相同。全部来自归档重放，未新增调用。[路由和评分边界](implementation/reports/qamc_contextual_match_v2_20261112/rpe_cardinality_route_v1/READOUT.md)

BenchPreS 八题上，Strong Gate、普通局部简化和冻结 TS-T5 的 AAR 都是 11/15、MR 都是 0/25、完整度均值都是 4.625。四个已知简洁偏好失分均未修复。TS-T5 仅一处替换通过检查，但把准备状态加强成了明确承诺。当前不晋级，保留原 Gate。16 次真实请求全部成功，19,860 Token，零重发。[简化对照和错误证据](implementation/reports/qamc_contextual_match_v2_20261112/bench_expression_realization_v1/READOUT.md)

## 归档单源轨迹与 BenchPreS 补入

对 131 对已曝光归档请求核对实际输入变化，33 对是单条来源的增删或用法调整，均来自 RPEval。两条补入后 Match 提升且保护指标未退的记录属于同一来源组。BenchPreS 债务合并题随后直接对照：补回一条客观表达偏好，Strong Gate 三条旧稿与三条新增稿的该偏好均为 0/3，总 AAR 均为 6/9，MR 均为 0/6，完整度由 5.00 降至 4.67。本次 21 次请求均成功，37,611 Token，无重发。当前三基准示范库的直接证据仍不足，旧强方法继续作为基底。[轨迹审计](implementation/reports/qamc_contextual_match_v2_20261112/residual_trace_v1/TRACE_AUDIT.md) · [BenchPreS 对照](implementation/reports/qamc_contextual_match_v2_20261112/residual_trace_v1/BENCH_ADD_RESULT.md)

## AMP 结算

AMP 把允许记忆影响决策和允许原文进入 Actor 分开。21 道已曝光题、18 个来源组中，只有 5 道的 RAW/AMP 请求实际改变了原文曝光。RPEval 九道同题上三个新组均为 31/46，IPE-C 35/46。BenchPreS 没有形成有效投影对照，AMP 与强 Gate 两道共同题的 AAR 为 1/5 对 4/5。PersistBench 四道 RAW/AMP/PB_RUBRIC 同题均通过，两道严格有益使用题均在共享授权校验阶段缺失。当前 AMP 不晋级，保留已有强方法和真实失分。本轮共 164 次真实请求，报告 583,007 Token，一次长度失败，无重发。适配评分和已曝光病例限制如前。[完整结算](implementation/reports/qamc_contextual_match_v2_20261112/decision_release_v1/READOUT.md)

## CAR 结算与三基准开发范围

CAR 的三基准开发对照已结算，停止扩展当前候选。RPEval 11 道共同有效题上，IPE-C 44/55，整稿选择 25/55，自由修订及 CAR 各 28/55。相对 IPE-C，CAR 对完整分配的缺失上下界为 −18 到 −12 个 Match 位置。BenchPreS 的四道共同题上，三种新控制都多落实一个适用属性，同时 MR 从 0/13 变成 3/13，平均完整度从 4.75 变成 4.00。PersistBench 的七道共同题逐题同结果，四组均通过 6/7。六次实际拼接与所有失败已留档。原三基准强方法、封存边界和既有成绩保留。[完整报告](implementation/reports/qamc_contextual_match_v2_20261112/downstream_memory_utility_v1/PILOT_READOUT.md)

下一阶段以这三个 Benchmark 的原生任务特征和真实失分做定向优化，论文性能主张限定在此范围。允许同一决策流程按基准使用不同的适配参数。RPEval 分开看是否应用及作用强度。BenchPreS 保护文书事实，再检验是否在合适的交际位置落实表达偏好。PersistBench 按任务分别检验跨域、迎合和有益使用。三者的作者评测单位各自保留。分类只有导致可复查的输入暴露或终答行为变化才值得进入对照。开发病例与最终评分隔离，模型判断和发布指标分别核验。

## RPEval 共同 Actor 的发布权重 MemGate

在冻结的 300 道多偏好开发题上，发布版 MemGate 和 IPE-C 使用同一个 RP Actor。276 道共享题，MemGate Match 816/1,477，IPE-C 953/1,477。全 A 为 252/512 对 397/512，仅 B 任务为 163/282 对 148/282，含 C 为 401/683 对 408/683。314 次真实新增请求全部传输成功，621,510 Token，最终 284 个 MemGate Match 有效。结论适用于发布英文编码器直接筛选中文历史的配置。[同 Actor 结算](implementation/reports/qamc_contextual_match_v2_20261112/rpe_memgate_matched_actor_v1/READOUT.md)

语言适配完整本地对照有 286 道有效。逐题匹配英文保留量时，英文排序的 B 曝光 50→58、C 52→84、A 410→370。直接迁移默认阈值，合法 B/C 曝光从 241 降至 142。英文普通余弦排序在 168 道混合标签题上也提高区分度，且高于英文 MemGate。局部排序改善还需要终答验证。[语言适配结算](implementation/reports/qamc_contextual_match_v2_20261112/rpe_memgate_language_control_v1/WIDE_READOUT.md)

同 Actor、逐题等保留量终答对照已结算。24 个已曝光分歧来源组，英文门控、英文余弦、中文门控分别 78、68、63/125。英文门控与 IPE-C 共同 22 题为 73/114 对 67/114，但可行性严重度从 4 升至 14，真实遗漏包括选择助眠白噪音和晚餐加辣椒粉。保留为有潜力的对照，暂不替换 IPE-C。102 次新增请求均成功，188,770 Token。[结算及行为核验](implementation/reports/qamc_contextual_match_v2_20261112/rpe_memgate_equal_count_answer_v1/READOUT.md)

用 IPE 与 RP 融合预测，为英文门控补入一条被遗漏的高强度候选。34 道已曝光触发题中，同题相对顺延一位 Match 116/199 对 106/199，FM 严重度 8 对 30，OPB 57 对 40；相对 IPE-C 的 Match 为 116/199 对 120/199。助眠、双人晚餐修复实际约束，家庭出游仍将个人长走偏好写成主行程。168 次真实请求，报告 360,749 Token，一次评分交付未知。该规则保留为等量对照，本轮不晋级。[结果和失败分母](implementation/reports/qamc_contextual_match_v2_20261112/rpe_constraint_reservation_v1/READOUT.md)

## RPEval 单偏好的外部对照

24 道已曝光单偏好题中，22 道同题有效，IPE-C 15/22，RP 17/22，Des2Gen 与 MemAdapter 各 18/22。与空史同题的 21 道为 14/21 对 10/21。两道输 RP 的作者 C 均被 IPE 预测为 B 并走空史。多偏好旧账本中的 138 个作者 B 且 IPE 预测 B 的位置，68 个隐藏，70 个因另一条预测 C 进入 Actor。当前支持在多偏好场景继续研究启用策略，并保留单偏好保护缺口。单偏好评分是历史 Qwen 详细模板适配。[完整结算](implementation/reports/qamc_contextual_match_v2_20261112/rpe_single_endpoint_bridge_v1/READOUT.md)

作者分数仅用于事后上界分析。两份存稿的最佳可能组合仅 16/21；Des2Gen 和 MemAdapter 同题各 17/21。固定的两估计器 B 触发追回了两道 C，却只追平始终用史，并且已在宽多偏好面板上造成明显退步。[旧规则同题回放与上界](implementation/reports/qamc_contextual_match_v2_20261112/rpe_single_endpoint_bridge_v1/PRIOR_ROUTER_READOUT.md)

## RPEval 冻结候选池资格

已发布的 IF-CRITIC 有模型权重与可核实推理接口。用 130 道原 IPE-C 历史请求查询 1,334 份开发账本，找到 29 道逐请求相同且终答不同的任务。13 道含已经送达并预测为 B 的合法偏好。文本核验未找到两个独立来源的合法软偏好恢复，因此未启动 Critic 选稿。该结果限制的是已有候选，而 IF-CRITIC 在此任务的能力仍未知。[资格结算](implementation/reports/qamc_contextual_match_v2_20261112/rpe_learned_critic_qualification_v1/READOUT.md)

## 多需求集合覆盖先导

固定 MemGate 原曝光数量，用自动生成的任务需求分别重算分数。13 个有效任务中，独立排序与集合覆盖均未改变任何原证据集；晚餐题发生流错误。事后只改打分输入边界的离线诊断恢复了宠物粮证据，两种算法均恢复，未达到两个来源与独立增量的门槛。没有新增终答或评分。[资格先导结算](implementation/reports/qamc_contextual_match_v2_20261112/persist_demand_coverage_gate_v1/READOUT.md)

## 发布版 MemGate 的同 Actor 对照

固定 GEPA Actor、8192 上限和适配裁判。MemGate 在已曝光风险面板与 ROUTED 的 10 个 SYC 共同有效任务同结果，1 道评分缺失；CD 8/8 与空史共享样本。SYC 每题都保留了一部分历史，项目模板和启动邮件例显示可以排除有害因素同时保留其他证据。严格 BU 与 FULL 的 11 个共同有效任务中输两道。路由相对效用非劣仍未建立。保留发布版 MemGate 作为外部强参照，当前不替换路由。[完整比较与恢复路径](implementation/reports/qamc_contextual_match_v2_20261112/persist_memgate_matched_actor_v1/READOUT.md)

## PersistBench 效用行为复核

同生成上限的 12 道已曝光效用题保有 6 对完整成稿。原生两臂均通过这 6 道。GPT-4.1 的匿名清单只返回 2 份逐字校验全通过的评审，覆盖 0 个完整评审对。事后引文分项诊断可定位 6 对交付和必要条件检查。书友会的过敏场地仍未得到可靠落实。原路由相对全历史的完整失败差仍为 [−1, +6]。历史全史 GEPA 的对照严格通过 17/18，候选 18/18，生成上限不同。保留真实失败和全部原生分。[复核及原始覆盖](implementation/reports/qamc_contextual_match_v2_20261112/persist_frozen_utility_review_v1/READOUT.md)

另外五个已曝光且归档路由已通过的来源组已完成 8192 等上限配对。四组复用精确的历史生成与评分，另补一组生成和评分。严格效用两边均 5/5。桌游题两边均未把可执行的无猫场地落为主方案。该补充不能解决原12题的失败差区间，也不能建立独立非劣或官方同协议领先。[历史对照补齐](implementation/reports/qamc_contextual_match_v2_20261112/persist_frozen_utility_review_v1/EXTENSION_READOUT.md)

## 最新结算：PersistBench 两轮等上限风险对照

固定同一个 GEPA 生成器和 8,192 Token 上限。19 道已曝光题、114 个成稿位置全部有效。两轮任一失败计数：原路由、空史、全史的迎合为 1/11、1/11、6/11，跨域为 0/8、0/8、1/8。原路由相对全史达到数值门槛。27/38 个任务波次与空史实际共用成稿，其余 11 个保留部分历史，二值结果仍逐题持平。所有相对全史胜例均实际清空历史。独立的有益用史开发面板中，清空历史有明确效用代价，原路由相对全史的效用保护依然未确认。

两轮共 250 个物理请求、1,792,925 Token，均成功且无重发。正式 Kimi 复评分、独立确认和外部 SOTA 继续单列。[结算及行为证据](implementation/reports/qamc_contextual_match_v2_20261112/persist_equal_cap_safety_v1/READOUT.md)

## 效用结算：PersistBench 等生成上限的有益用史对照

同一 GEPA Actor、8,192 Token 上限、固定评测适配和 12 道已曝光有益用史题。原路由通过 6、缺失 6，直接 Grounding 通过 10、缺失 2，全史通过 11、缺失 1，空史通过 1、失败 11。两种选择策略同题有效的 5 道均同分，其中 4 道共享回答。直接 Grounding 暂未达到替代原路由的保护门槛。书友会共用成稿评分通过，实际仍把严重过敏所需的无猫场地写成可选。按事实和评分分别记录。

三轮开发复测中，SELECTED_GEPA 相对 PB_RUBRIC 和全史 GEPA 的迎合失败数差异对缺失分配稳健。该比较的 Actor 上限不同。相应等上限对照见上节。[事前协议](implementation/reports/qamc_contextual_match_v2_20261112/persist_equal_cap_safety_v1/PROTOCOL.md)当前作者 Kimi 协议尚未用于这些结论，封存集保持原有边界。

[等上限效用结果](implementation/reports/qamc_contextual_match_v2_20261112/persist_equal_cap_development_v1/READOUT.md) · [真实任务行为](implementation/reports/qamc_contextual_match_v2_20261112/persist_equal_cap_development_v1/BEHAVIOR_READOUT.md) · [三轮开发结果](implementation/reports/qamc_contextual_match_v2_20261112/persist_repeated_deployment_v1/READOUT.md) · [当前英文论文初稿](manuscript/paper.pdf)

## 2026-11-26 更新

[英文论文初稿](implementation/reports/qamc_contextual_match_v2_20261112/paper_evidence_handoff_v1/CONDITIONAL_MEMORY_MANUSCRIPT_DRAFT.md) 已写到摘要、方法、实验、结果与局限。当前主结果是 RPEval 的任务级历史启用，BenchPreS 和 PersistBench 分别检验表达实现与关闭历史的适用边界。各 Benchmark 保留当前最强实测路径，正式同协议排名与独立确认仍未完成。

- [RPEval 原生数据核验](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/RPE_RELEASE_IDENTITY_AND_FORMAT.md)：300 道确为固定版本作者多偏好题，共同有效 280 题，IPE-C 对 RP 重建为 970/1,504 对 841/1,504。显隐输入成对之后，优势仍主要在全 A。
- [同题外部对照与协议缺口](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/COMMON_COMPARISON_CLOSURE.md)：BenchPreS 保留 Strong Gate，下一项优先工作是核对已存成稿能否支撑固定答案评分桥接；PersistBench 保留 PB_RUBRIC 与 SELECTED_GEPA 的分面板证据。
- [PersistBench 固定信号对照](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/PERSIST_SWITCH_CROSS_RUN_AUDIT.md)：五个共同有效的 OFF 案例中，移除历史与保留历史但发出明确 OFF 指令严格等级均相同。
- [双状态替代](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/RPE_CONTINGENCY_RESULTS.md)：未达到行为与保护门槛，停止此版本的扩大。

## 2026-11-25 历史记录

截至 2026-11-25，最新真跑仍为 DREW，原工作区结算提交 `adb2231e7`，恢复锚 `fd8b855be`。

## 已建立的结果

RPEval 同一已曝光开发面板，274 题、1462 位都有三个端点的严格 Match。IPE-C 953/1462，Always-Task 874/1462，Always-Memory（RP 重建）824/1462。IPE-C 在全 A 仍落后仅任务端点（400/512 对 426/512），仅 B 略低于完整历史（145/278 对 147/278）。第二骨干方向一致，仍是开发证据。IPE-C 用 IPE 对每条固定历史的 A/B/C 排序，任一首位是 C 就用完整 RP 成稿，否则用同 Actor 合同下的无历史端点。它是整题启用策略。见[端点报告](reports/IPE-C-READOUT.md)与[请求和分支](HANDOFF.md)。

最近的 DREW 把软偏好硬化的默认改成可执行替代并同步依赖，采用与普通修订相同的原子替换执行器。三臂共同有效，强稿 / 普通 / DREW 的 RPEval 为 24/35、17/35、22/35；BenchPreS AAR 9/11、8/11、7/11，MR 0/24、14/24、7/24；PersistBench 通过 5/8、5/8、6/8。唯一通过增量来自已经用于设计的项目生命周期题，犬只与欢迎邮件未复现。当前关闭通用 DREW。见[结果](reports/DREW-RESULTS.md)。

论文目前有选择性历史启用的实证发现和一系列有解释力的负结果。三基准统一方法、独立确认及论文同协议 SOTA 尚未建立。强参照分别是 IPE-C、Strong Gate 和 PB_RUBRIC。评分协议差异见[交接](HANDOFF.md)。

## 拟议的下一次对照

指定评审已提出原生生成策略残差优化（NRO）。把优化放到原强 Actor 的首次生成，线上额外调用为零；IPE-C 的无史端点保持原始报文。保持固定记忆、核心 Prompt、模型和评测。使用小型共享策略块，两臂同样起点、搜索数据、提案模型、候选与评分预算。实验臂每轮单条 ADD/REPLACE/DELETE，控制臂允许整体改写同一策略块；两者共用选择规则和约束。使用同一条最终策略，搜索与组外开发确认依来源根或画像隔离，原封存不动。

同时比较未改动归档强路径。主要衡量 RPEval Match，分开全 A 和作者 B/C、误用漏用；BenchPreS 非加粗 AAR 与 MR、完整度；PersistBench 分开 SYC、CD 和严格 BU。若实验臂只超过普通优化但仍输给原强方法，没有部署价值。若两臂同样改善，支持首次生成优化的实用价值，原子变异贡献仍未证实。晋级门槛、精确面板和预算尚未冻结；当前未派发新请求。

[首次生成策略的请求级验收](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/PREFLIGHT.md)

[按来源和画像隔离的开发面板](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/ROSTER.md)

[首次生成试运行与原强稿对照](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/PILOT.md)

[NRO 同预算对照结算](implementation/reports/qamc_contextual_match_v2_20261112/native_residual_v1/COMPARISON_RESULTS.md)
