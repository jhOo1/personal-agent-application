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

[同候选前提提交对照](implementation/reports/qamc_contextual_match_v2_20261112/feasibility_commit_v1/RESULTS.md)已结算。守卫与模型自由选择在八个来源的终答均逐字相同，不晋级，不改基准分工。

[PersistBench 等量备用证据实测](implementation/reports/qamc_contextual_match_v2_20261112/persist_reserve_exposure_v1/RESULTS.md)得到一个对原先选择的 Qwen 严格效用净胜，GPT-4.1 持平，未达到扩大门槛。

[当前任务选择与旧史冲突](implementation/reports/qamc_contextual_match_v2_20261112/persist_task_commitment_v1/RESULTS.md)在一个已知跨域来源复现了自动修复，严格有益使用四题沿用原证据，未达扩大门槛。

[当前选择保护三基准筛查](implementation/reports/qamc_contextual_match_v2_20261112/task_commitment_transfer_screen_v1/RESULTS.md)完成，每基准 8 个来源。三条触发均与普通复核相同，强稿均未收到对应历史。停止这一通用过滤分支。

[BenchPreS 整句压缩与完整度对照](implementation/reports/qamc_contextual_match_v2_20261112/bench_discourse_compaction_v1/RESULTS.md)已结算。删句主分持平，全文改写多实现两个偏好却损失两分完整度，保留 Strong Gate。

[RPEval 两骨干两裁判交叉复评](implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_crossed_judge_v1/RESULTS.md)表明 IPE-C 相对全史的优势在四个条件下方向一致，但相对无史的正差在 Qwen 评分下反转。原分保留，双裁判结果单列。

[RPEval 合法偏好行动核验](implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_focal_action_v1/RESULTS.md)在两个生成骨干上定位了相同三个软偏好落实缺口。独立模型交付未知与 Qwen 次级诊断分开。

[RPEval 备用终答局部行动转移](implementation/reports/qamc_contextual_match_v2_20261112/ipe_verbatim_action_transfer_v1/RESULTS.md)已结算。原稿 46/86、同槽改写 45/86、原文转移 44/86；三个已知软偏好缺口都没有被选作修改目标。

[RPEval 合法软偏好同位置干预](implementation/reports/qamc_contextual_match_v2_20261112/ipe_soft_action_oracle_v1/RESULTS.md)复用两种 Actor 的原答，人工分别补入符合记忆或同样具体的一般行动。只有卧室配色在 Qwen 评分下相对一般行动有独特 Match 净胜，GPT-4.1 无此提升。不把诊断当作自动算法成绩，不再扩大同类局部编辑。

重新检查替代项。PairPref 固定偏好与请求、改变场景，1,227 对同时支持选择和自由生成，能直接补上适用性翻转；本次仍未核实作者全数据和可运行评分发布，维持候选身份。[论文](https://arxiv.org/abs/2609.34526) · [作者 Mitigate 对照](https://arxiv.org/html/2609.34526v1#A6.SS6)

MemSyco-Bench 公开 1,550 题及校验清单。若论文主张转为当前证据优先或主体作用域，Candidate 价值在 Contextual Scope Control 与 Memory–Evidence Conflict。全面替换会削弱正式交付覆盖，并与 PersistBench 的风险侧部分重合。目前不替换。[作者数据卡](https://github.com/XMUDeepLIT/MemSyco-Bench/blob/main/data/README.md)

已请求 QAMC-v3.2 反驳二主一边界以及以上换榜条件。发送接口接受请求，截至本次记录未核实新回复。公开归档包含诊断代码、评分汇总与协议，精确模型收据和原始请求仅在原实验仓库的本地运行数据中。

[PersistBench 同选择信号下的真实遮蔽与显式提醒](implementation/reports/qamc_contextual_match_v2_20261112/persist_matched_reminder_v1/RESULTS.md)已结算。两臂 10 个来源在 GPT-4.1、Qwen 下均为 3/4 迎合通过、3/3 跨域通过、3/3 严格有益使用通过。歌单题仅在评分严重度上改善，误选的私人忌讳仍影响最终曲目。没有证据支持把遮蔽单列为性能贡献。后续新方案必须与同信号全史提醒比较，并保护任务绑定事实。旧三抽、外部对照、原有三基准档案全部保留。

[PersistBench 选择器历史消息角色对照](implementation/reports/qamc_contextual_match_v2_20261112/persist_selector_role_transport_v1/RESULTS.md)已结算。七个双臂有效选择中三题改变准入；没有双裁判共同风险净胜。助手消息在霸王龙展牌题放行私人信念并影响展牌，用户消息在纪念日晚餐题漏掉原来正确使用的伴侣菜品偏好。原选择器和全史提醒强对照继续保留，不扩大角色切换路线。三条解析失败和一条 Actor 交付未知分开计入。

[三基准同来源片段保护与隔离](implementation/reports/qamc_contextual_match_v2_20261112/protected_clause_exposure_v1/RESULTS.md)结算。五题真正触发，原生适配分无净胜。RPEval 同题 13/24→12/24；两道实际触发的 PersistBench 风险题同分失败，且罗马行程的评分理由误报了已消失的分手内容，其他私人细节仍真实存在。BenchPreS 与严格有益使用沿用原稿，不能用于证明真实修改时的保护性。不再扩大此片段隔离规则。

[基于当前任务条件的备选动作对照](implementation/reports/qamc_contextual_match_v2_20261112/task_condition_branches_v1/RESULTS.md)已结算。十二题五触发，两臂共享同一候选和 Actor 可见历史。要求保留条件分支使 RPEval Match 13/24→12/24、BenchPreS 完整度 10/10→9/10；PersistBench 只触发两道严格有益使用且均持平。项目模板、公园聚会和全部 PersistBench 风险根沿用旧稿，因此该触发器未覆盖原来的错误决定。停止扩大，保持各基准强参照。

[归档无历史答复引文与局部修订](implementation/reports/qamc_contextual_match_v2_20261112/foil_anchored_decision_repair_v1/RESULTS.md)完成。引文版改 4/12 道，普通复核改 11/12。RPEval 与 IPE-C 同为 8/23，BenchPreS AAR 由 Strong Gate 的 4/5 降至 3/5，PersistBench 各类别与 PB_RUBRIC 持平。野餐人数、项目生命周期两个关键错例沿用原稿。没有一道主分超过原强稿，关闭该修订规则。保留二主一边界和原三基准档案。

[三臂融合候选空间复算](implementation/reports/qamc_contextual_match_v2_20261112/fusion_candidate_tradeoffs_v1/RESULTS.md)核实了 QAMC-v3.2 建议的关键干预已实测。18 个冻结来源中 16 个三臂有分，各分项最佳值分散的 RPEval 和 BenchPreS 来源分别为 2 和 1；没有任何融合终答主分超过同题候选和强稿。零新增请求，复用原对照。

[生成前执行推演](implementation/reports/qamc_contextual_match_v2_20261112/participant_execution_preflight_v1/RESULTS.md)在 9 个开发来源完成。执行组把桌游场地是否可行写为先决条件，项目适配的严格效用分仍持平。三臂 RPEval 6/18，BenchPreS AAR 强稿 4/5 对两臂 3/5，PersistBench 迎合均 0/2。野餐和项目模板继续出现将个人历史强化为共享要求。停止扩大当前提示，保留场地行为证据。

[近期四种修复的逐题上界](implementation/reports/qamc_contextual_match_v2_20261112/recent_repair_headroom_v1/RESULTS.md)核对 21 个已曝光题的 90 个逻辑单元。53 份有评分的确切改稿没有一份提高专项强稿的同题主分；3 道 RPEval 仅有次指标改善。停止扩大现有强稿后处理路线，下一阶段优先使用已观察到抗迎合收益的 SELECTED 路径做生成前证据控制对照。新核对的 Vercel 匿名模型目录未列出 Kimi K2 Thinking，未取得已认证的可比评分回执。

[同序联合证据块](implementation/reports/qamc_contextual_match_v2_20261112/joint_evidence_block_v1/RESULTS.md)实测 8 个 PersistBench 来源，6 对新成稿。严格有益使用 Qwen 3/4→4/4，GPT-4.1 均 4/4，旧 RESERVE 与 FULL 已 4/4。唯一净胜的桌游成稿去掉了不适合四人的推荐，但仍未把猫过敏事实落实为场地前置条件。当前分块结构不扩大。

[桌游人数与场地前提的固定成稿对照](implementation/reports/qamc_contextual_match_v2_20261112/board_game_action_factorial_v2/RESULTS.md)在同一归档稿分别修复两项行动。不论只修游戏、只修场地还是全修，Qwen 都是 2→3；GPT-4.1 全部为 3。Qwen 的通过不能验证两个问题都已解决。它也无法唯一解释上一轮联合块的分差。6 个新评分、0 Actor，原评分保留。
