# QAMC 当前判断与下一次机制对照

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
