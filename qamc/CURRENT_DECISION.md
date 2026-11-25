# QAMC 当前判断与下一次机制对照

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
