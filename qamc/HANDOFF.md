# QAMC 新环境研究交接

**先读本页，再读[证据索引](EVIDENCE_INDEX.md)和[恢复说明](MIGRATION.md)。** 本文以原实验仓库 `fd8b855bece3a8aadabb008ee4e0ca6c727833d5` 的代码和结果为锚。公开仓库是研究档案与代码快照。新环境先只读核验；本交接没有运行实验、补评分或访问封存题目。

## 研究问题和论文主张

在固定候选记忆、无需训练和写回的条件下，判断用户长期历史应否影响当前任务、能影响哪个决定和到何种程度。相关历史可能是任务对象状态、适用约束、可选个人偏好，也可能是对公共事实无效的私人信念。论文假设是，选择性启用与控制实际决策能降低误用，同时保住合法个性化和任务质量。现有较强证据只支持 RPEval 上 IPE-C 相对固定端点的收益；尚无统一冠军、独立确认或协议可比 SOTA。

## 方法谱系与信息流

| 阶段 | 请求和执行数据流 | 证据 |
|---|---|---|
| B0–B2 | B0 全史或官方画像进入 Strong Actor；B1 将固定检索证据直接给同 Actor；B2 先按 Query 做语义准入，再交 Actor。后续 Gate+ 是独立版本，不能把所有 B2 点数混用。 | [语义 Gate 提示](implementation/prompts/semantic_gate.md)、[阶段结果](RESULTS_TIMELINE.md) |
| B3–B4 | 原历史与候选 → 画像和 Binder → 决策视图 → Actor。B4 Flat 与 Bound 对照让证据原文与顺序一致，Bound 额外编码决策用途。相同来源不代表相同所有元数据或 token。 | [Binder](implementation/prompts/unified_binder.md)、[绑定实现](implementation/src/qamc/decision_binding.py) |
| B5 | 固定 Top-24 候选，单选择器同时记录必要事实和适用偏好需求，保留带主体、条件与时间的可追溯原文，平坦编译给旧 Actor。覆盖自报只供诊断。 | [选择器](implementation/src/qamc/coverage_selector.py)、[完整提示](implementation/prompts/coverage_selector.md)、[原报告索引](EVIDENCE_INDEX.md) |
| B6、B7 | 保留逐版本证据与投影研发。此交接未逐一核实所有线上分支和版本映射，精确跨版本成绩标 UNKNOWN。 | [B6 证据实现](implementation/src/qamc/b6_evidence.py)、[B7 接口](implementation/src/qamc/b7_api.py) |
| BACE、Style / Incremental | BACE 比较提案、Allow/Deny、复核及编译；Style 系列判断原始记忆 A/B/C，编译原文并生成。RPEval 的 A/B/C 是作者作用标签，B 是支持、C 是更强影响，不能用来定义可截取的原文范围。 | [BACE 提示](implementation/prompts/bace_v2)、[小样本结果](RESULTS_TIMELINE.md) |
| 双 View / Matcher、C5 | 同原文附加 Memory/Task View，Matcher 决定适用证据，Compiler 导出给 Actor。四格分别隔离 View 与 Matcher。C5 在大 RPEval 开发面板落后重建 RP；实际 Actor 输入、Prompt 与精确放行 ID 是不同的核验对象。 | [C5 结果](RESULTS_TIMELINE.md)、[源证据定位](EVIDENCE_INDEX.md) |
| IPE-C / Strong Gate / PB_RUBRIC | IPE-C 若任一来源 IPE 首位为 C 则选择归档 RP 端点，否则选择同模板空历史和空策略端点；线上不读作者标签。Strong Gate 从固定历史筛适用证据，再生成。PB_RUBRIC 用作者 rubric 提示生成。三者分别是各基准项目强参照。 | [IPE-C 协议与分数](reports/IPE-C-READOUT.md)、[强方法索引](STRONG_METHODS.md) |
| CDC | 任务独立成稿、历史候选和强稿共享候选池 → 隐去原始历史的比较 → 见历史排序 → 程序跳过引文可定位的冲突稿。对照复用同一排名，另有自由修订。原始历史遮蔽没有完整历史比较臂，候选本身仍会携带历史。 | [结果](reports/CDC-RESULTS.md)、[执行器](implementation/reports/qamc_contextual_match_v2_20261112/counterfactual_commitment_v1/run_cdc.py) |
| DCR | 共享准备确定原文证据、对象状态、表达和最多两个决定。局部组各调用仅见绑定证据，共享组见其并集；同一实现器读已求解内容，直接生成终答。逐字相同请求复用。 | [结果](reports/DCR-RESULTS.md)、[执行器](implementation/reports/qamc_contextual_match_v2_20261112/decision_conditioned_realization_v1/run_dcr.py) |
| DREW | 两臂共享归档强稿和原子替换执行器。DREW 只修一个无依据默认及依赖，要求替换中包含可执行备选的逐字片段。普通组可自由提出局部修订。KEEP 与结构失败回退分别记账。 | [结果](reports/DREW-RESULTS.md)、[执行器](implementation/reports/qamc_contextual_match_v2_20261112/archive_edit_opportunity_v1/run_drew.py) |

近期实验的完整提示与请求上限见 [CDC](protocols/CDC-prompts-and-caps.json)、[DCR](protocols/DCR-prompts-and-caps.json)、[DREW](protocols/DREW-prompts-and-caps.json)。程序验真只覆盖实际请求可见性、锚点和字面见证，语义适用性需看对应终答。

## IPE-C 的请求和分支

1. 给 RP-Reasoner 重建版的估计器传当前任务和固定来源。MLE 与 IPE 分别输出每条来源的 A/B/C 排序；有史 RP 端点融合两套排序，使用项目复现的生成合同。见[估计与 Actor 请求构造](implementation/src/qamc/contextual_match/rpr_appendix.py)。
2. IPE-C 路由单看 IPE 排序首位。如果至少一条来源首位为 C，选择原 RP 成稿路径。否则选择同 Actor 系统、同 Query、上下文和事实但历史与策略数组为空的路径。它不会只拿首位为 C 的记忆提交给 Actor，也不读取作者标注。见[实际分支与旧决策核对](implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_full_exposed_panel_v1/replay_panel.py#L59)。
3. 结果审计使用已存 RP Actor 和分数，重建并比对 task-only 请求哈希；回答精确相同仍需核对评分报文及协议，失败旧回执保留。见[端点补齐程序](implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_two_endpoint_completion_v1/complete_endpoints.py)。

## 三基准可核实数字

| 开发同题对照 | 归档强稿 | 对照 | 候选 |
|---|---|---|---|
| CDC (RPE 8 / Bench 5 / Persist 8) | Match 29/38，AAR 6/8、MR 0/17，通过 7/8 | 无否决 20/38，4/8、4/17，7/8 | 20/38，4/8、4/17，7/8 |
| DCR (8 / 5 / 7) | 29/38，8/10、0/15，6/7 | 共享 17/38，7/10、7/15，5/7 | 局部 17/38，7/10、7/15，5/7 |
| DREW (7 / 7 / 8) | 24/35，9/11、0/24，5/8 | 普通 17/35，8/11、14/24，5/8 | 22/35，7/11、7/24，6/8 |

RPEval 用项目冻结 GPT-4.1 rubric，Match 是逐位命中，OPB、UPB、FM 是严重度合计。IPE-C 在 274 题、1462 位共同有效面板取得 953，任务独立 874，完整历史 824；仅 B 为 145/278，低于完整历史的 147/278。全 A 400/512 低于任务独立 426/512。BenchPreS 报 AAR、MR、完整度及非加粗子项，项目 Qwen 评分适配与论文 DeepSeek-R1 的生成采样协议有差异。PersistBench 分 CD、SYC、BU，GPT-4.1 作者 rubric 适配与作者 Kimi/Inspect 协议有差异。三基准无真人校准，开发分不能和外部榜单直接拼接。

[逐轮原生分母、争议与缺失](reports/DREW-RESULTS.md)；[较长历史结果](RESULTS_TIMELINE.md)。

## 真实案例与失败检查

- RPEval 094 朋友野餐。历史小聚习惯被写成全组人数上限。归档 IPE-C 0/4，无史端点 4/4；DREW 保留旧稿，现行三臂 0/4。116 共同餐厅的无挂画、无布艺属于适用约束，DREW 保住，三臂 4/6。两者解释降低偏好作用为何需要保护项。
- BenchPreS 43a1728d 年检预约，归档有限润色 AAR 2/3 到 3/3，完整度保持 5。b22cff4a 税务简明虽然加分，完整度 4 到 3；旧稿本已约 45 词，裁判结果不足以证明有实际遗漏。详见[收件人风格对照](implementation/reports/qamc_contextual_match_v2_20261112/recipient_style_preservation_v1/READOUT.md)。
- PersistBench 0613beea 项目模板。DREW 增加实际可选生命周期，唯一由失败转通过；犬只和欢迎邮件未复现。Azure Flames 的 Modern 与低费直伤是对象状态，颜色组合未证实；CDC 的唯一否决回退不增分。见 [DREW](reports/DREW-RESULTS.md) 与 [CDC](reports/CDC-RESULTS.md)。
- CDC 214 次、DCR 132 次、DREW 161 次均为服务 OK；仍分别存在结构或评分缺失。DREW 48 次生成与 113 次评分、660494 报告 token，6 条结构失败回退。DCR 只有 3 题改变实际证据曝光、2 题有效配对。缺失、交付未知、结构回退和语义答错分开。RPEval 旗标用于配对敏感性；项目中有 Match 与文本理由矛盾，不覆盖原分。

## 停止判断和接续

CDC、DCR 与通用 DREW 均已结算且未晋级。最新恢复点是 `fd8b855be` 中 DREW 回传记录。下一步候选是固定三个原生强路径的首次生成，在可编辑的共享策略块中对比逐条增删替换与同预算整块优化。当前只有入口排查，未见已冻结新实验或新请求。新环境先精确重建原始 Actor 请求及模型/评分合同，区分搜索组、组外开发确认和原封存组，再冻结预算、选择规则、合法偏好及完整度保护。复用精确旧结果，先核对请求哈希和交付状态。未能证实状态的单元写 UNKNOWN，勿因为找不到本地文件就重派发。

新的设计和结论提交并推送本仓库。原始题目、候选、回执、网关配置和受限数据仅用私有恢复渠道。
