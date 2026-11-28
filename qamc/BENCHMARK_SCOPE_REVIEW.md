# 三个基准如何支撑同一个研究问题

当前建议以 PersistBench、RPEval 检验历史可见范围，以 BenchPreS 检验正式交付中的适用表达与完整度。保留全部历史分母。这个调整缩小论文可宣称的机制范围，三个基准仍须逐项报告。开发数据没有证明三者存在不可调和的标签冲突。

| 已曝光同题对照 | 可观察的结果 | 对机制的限制 |
|---|---|---|
| [RPEval 两端点](implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_two_endpoint_completion_v1/READOUT.md) | 274 题 1462 位，任务级选择 953，始终无史 874，始终有史 824 | 相对始终有史的净增集中在全 A；软偏好仍会漏用。 |
| [PersistBench 迎合](implementation/reports/qamc_contextual_match_v2_20261112/persist_same_actor_syc_crossjudge_v1/RESULTS.md) | 相同 Actor，逐条可见对整组可见，两个裁判在霸王龙展和学生欢迎邮件上同向改善，12 根各 2 胜 0 负 | 两个裁判看到相同答案，不能充当两次独立复制。[严格有益使用](implementation/reports/qamc_contextual_match_v2_20261112/persist_same_actor_protection_crossjudge_v1/RESULTS.md)有 6 根配对未知。 |
| [BenchPreS 固定来源](implementation/reports/qamc_contextual_match_v2_20261112/bench_gate_gepa_feedback_v1/FINAL.md) | 38 道共同题，强 Gate、数值反馈、属性反馈的 AAR 分别为 58、58、56 / 68；完整度总分 177、151、159 | 事实和表达要求需要落实在成稿。误用从 1/122 降到 0/122 的同时，完整度出现明显代价。 |

## 外部对照的可比范围

核对 [MemAdapter 固定版本的实验设置](https://github.com/DEEP-JLU/MemAdapter/blob/6b517dc90d4c7e0ebc4d2305684d45051f792cc9/README.md)及[模型客户端](https://github.com/DEEP-JLU/MemAdapter/blob/6b517dc90d4c7e0ebc4d2305684d45051f792cc9/methods/memadapter/model_client.py)。作者的本地 Qwen3-8B 使用 4-bit NF4、贪心解码和关闭思考的聊天模板。客户端默认输出上限 4096，可被环境或调用参数覆盖。项目[适配协议](implementation/reports/qamc_contextual_match_v2_20261112/persist_memadapter_release_v1/PROTOCOL.md)使用托管 qwen3.8-flash、温度 0、上限 8192。网关实际底层权重和思考模式未知。

[原始交付计数](implementation/reports/qamc_contextual_match_v2_20261112/persist_memadapter_release_v1/FINAL_EXTERNAL_DELIVERY.json)逐次汇总为 47 次部署，28 份成稿、16 次首阶段长度失败、2 次终答长度失败、1 次首阶段交付未知。该分母含重复部署，不能解释为 47 个独立任务。上述差异限制对外排名，也不能从长度失败反推出网关启用了思考。

## 范围决定的判据

机制主张限定为生成前改变历史可见范围。优先用相同 Actor、对称提示和同一评分比较误用及严格有益使用；独立确认前固定允许的质量损失和缺失处理。若正式研究问题包含如何把简明、客观等偏好落实在正式文书，BenchPreS 应继续作为主要评测。若主张仅限历史曝光，则将其作为边界评测并报告完整度。仅因某个已有得分较低不足以替换基准；替代必须提供当前评测缺少的可观察行为和可复现终答评分。当前无已验证可替代项。

本页使用已有开发结果；无新 Actor 或 Judge 调用，无封存数据访问。

## QAMC-v3.2 复议

评审同意 RPEval 主评、PersistBench 检验风险和有益使用、BenchPreS 检验表达与任务完整度。两个主基准支持共同研究问题，各自领先的算法尚未合并验证。[18 根严格有益使用的新部署](implementation/reports/qamc_contextual_match_v2_20261112/persist_utility_fresh_deployment_v1/RESULTS.md)给出了更强的反证：SELECTED 与 FULL 在 GPT 评分均 18 过；Qwen 评分中 SELECTED 为 14 过、3 败、1 未知，FULL 为 18 过。新部署复用已曝光来源；不得填补另一轮的缺失。当前没有证据显示保留全部有益使用。BenchPreS 的原强 Gate 已有较高的合法偏好实现率，边界评估仍应同时报告收益与代价。

## 对删减或替换的再裁决

已将三项最强反证提交 QAMC-v3.2 复议。当前决定为 RPEval 主评、PersistBench 检验风险与有益使用、BenchPreS 保留为正式交付与合法表达的边界评价。该分工形成于已看过开发结果之后；三项原始成绩仍分别报告。没有证据表明三个数据集在同一输入、主体和决策下要求互斥的正确答案。

- RPEval 的归档领先需要同时期重新生成来检验。若复跑没有稳定领先，应收窄对算法的主张。已曝光来源的重复部署与独立确认须分别报告。[其余 24 根的冻结协议](implementation/reports/qamc_contextual_match_v2_20261112/rpe_remaining_roots_deployment_v1/PROTOCOL.md)
- PersistBench 的三次空历史翻盘也可由始终关史取得。证明按任务判断有价值，需要与始终有史、始终无史和相同开启比例的对照比较，并单列严格有益使用的损失。跨裁判对同一答案的分歧仍需报告。
- BenchPreS 中 Gate 达到了三个现有端点在 26 题上的受保护 AAR 上界 38/44。这个上界只约束已存三稿；新生成的答案仍可能解决简明或客观表达。源证据已到达而成稿未落实，属于生成阶段的实际研究问题。拟合这两类表达需要另外证明任务事实与完整度得到保护。
- 若要替换基准，应先证明其评分持续无法区分事先定义的行为，并用同一正反例证明替代评测可区分、存在可复现强对照。当前没有这样的配对证据。若论文仍主张解决正式表达，BenchPreS 应恢复为主评价。
