# QAMC 基准去留与算法优先级

**从共同晋级门槛移出 BenchPreS，保留原表和正式交付回归。PersistBench 承担风险与效用主结果，RPEval 承担混合偏好的机制验证。本次不换基准。** 先用两个主基准检验同一种可执行操作：固定给定历史，在生成前改变实际可见范围，并要求不适用的历史不再改变任务决定、适用的历史仍能改变行动。三个专项强稿继续保留。

该决定基于已曝光开发记录。历史三基准综合表、原分、失败和缺失仍按原定义存档。这次调整没有生成新的成绩。

## 已经复现的信号

| 基准 | 能确认的开发信号 | 当前限制 |
|---|---|---|
| RPEval | 两次部署的同 41 来源组共 226 位，IPE-C 对完整历史 RP 的 Match 是 126 对 125、139 对 115；OPB 是 41 对 58、37 对 61。 | UPB 同时从 36 到 49、从 38 到 45；不能把所有少用历史都算作收益。124 份完全无历史答卷中 37 份仍被判正 OPB，原分照录，历史诱发必须另核实。 |
| PersistBench | 固定 Actor 与同一选择回执，逐条可见比整组可见在霸王龙公共科普、学生欢迎邮件两个来源改善迎合，GPT-4.1 和 Qwen 在相同成稿上都给出 2 胜 0 负。 | 严格有益使用的新 18 根部署，GPT-4.1 下选择与全史均通过 18 根；Qwen 下选择 14 过、3 败、1 未知，全史 18 过。两个裁判不是两次生成复制，项目评分也未达到原 Kimi 托管协议。 |
| BenchPreS | 固定 Strong Gate 选中来源，38 道共同有效题的 AAR 为 58/68，完整度 177/38；数值反馈保持 AAR 但完整度降为 151/38，属性反馈为 56/68 和 159/38。 | 锁定版本 10 个画像中，37,050 个复用题目的同偏好比较没有适用标签翻转。简明和客观偏好有已送达而未落实的案例。它检验交付实现，无法提供同一偏好随情境翻转的直接证据。 |

[RPEval 重复部署](implementation/reports/qamc_contextual_match_v2_20261112/rpe_remaining_roots_deployment_v1/READOUT.md) · [无史负控制](implementation/reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/NO_HISTORY_RPE_GRADES.md) · [同 Actor 迎合](implementation/reports/qamc_contextual_match_v2_20261112/persist_same_actor_syc_crossjudge_v1/RESULTS.md) · [严格效用复验](implementation/reports/qamc_contextual_match_v2_20261112/persist_utility_fresh_deployment_v1/RESULTS.md) · [BenchPreS 固定证据](implementation/reports/qamc_contextual_match_v2_20261112/bench_gate_gepa_feedback_v1/FINAL.md) · [标签结构核对](implementation/reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/BENCHMARK_DECISION_20261128.md)

真实的效用反例是 PersistBench 的桌游聚会。选史保住成员身份和红绿色觉需求，漏掉主人有猫、参与者严重猫过敏两条需要联用的事实。全史回答给出了避猫措施。GPT-4.1 两稿都判通过，Qwen 只给全史通过。这个例子能核实信息与行动差异，不能从单次生成拆出任何一条来源的独立因果贡献。[成稿与来源核验](implementation/reports/qamc_contextual_match_v2_20261112/persist_utility_fresh_deployment_v1/CASE_READOUT.md)

## 为什么暂不再加一轮融合

DQS 已实测，候选隔离仅触发 1 个来源且没有改变原生主分。RPEval 同题 14/28 对专项强稿 20/28；BenchPreS 完整度 19/20 对 20/20，MR 7/14 对 1/14；PersistBench 迎合通过 1/2 对 2/2。后续软偏好回看中，同数量排序臂没看七条目标来源仍有六项具体行动，恢复来源后是七项，未证实原分净增。继续融合、补召回或加用途字段缺少当前端到端依据。[DQS 实测](implementation/reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/DECISION_QUARANTINED_SYNTHESIS_RESULTS.md) · [软偏好回看](implementation/reports/qamc_contextual_match_v2_20261112/rpeval_soft_realization_audit_v1/RESULTS.md)

## 换什么才有价值

- **PairPref** 固定偏好与请求，再改变场景，是最直接的候选。论文和案例可读，完整作者数据与可运行评分入口仍未核实。取得后先复现作者 Mitigate 强对照并报告成对生成覆盖和模棱两可答复的排除率。[作者论文](https://arxiv.org/html/2609.34526v1)
- **PrefEval** 已有公开数据与 Reminder 等基线。它主要检验长上下文中的识别、记忆和遵循；用它替换会改变论文问题，无法直接补足适用性反转。[作者仓库](https://github.com/amazon-science/PrefEval)
- **PCA-Bench** 可用于比较冲突和任务质量的定义。作者固定源文本和请求并改变画像偏好；该配对轴与固定历史、改变情境不同。公开可执行数据与评测仍未核实。[作者论文](https://arxiv.org/abs/2610.39550)

## 下一验收与止损

1. 复用已有同 Actor、同信号的 FULL、EMPTY、GROUP、SELECTED 成稿。优先检查严格有益根与确有非空曝光差异的混合根，先看原始请求和最终行动，再揭示评分。真实保护项包括 RPEval 的挂画及布艺限制，以及 PersistBench 严格有益使用任务的场地或行动约束。保留无法判定、不出稿和裁判分歧。
2. 只在新机制能改变至少两个独立来源的实际行动并同时保护合法需求时，派发同预算的新对照。PersistBench 比全史强防御与同信号整组开关；RPEval 比 IPE-C 与 RP 重建路径。BenchPreS 保留 Strong Gate 对照，检查 AAR、MR 和完整度。
3. 如果风险收益只有一位裁判认可，或依赖删掉合法信息，论文收为风险与效用的实证权衡。若主张要覆盖同一历史的情境反转，必须通过可执行的成对评测资格再增补。现无共同冠军、正式 SOTA 或独立确认。

QAMC-v3.2 已有回复支持二主一边界。最新复议要求其用真实证据挑战换榜、单主与融合方案。对话状态与实验评分分别记录。
