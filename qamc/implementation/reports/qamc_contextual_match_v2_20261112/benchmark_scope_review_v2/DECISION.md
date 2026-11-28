# 三基准范围复核

保留三套历史成绩。下一轮主张聚焦生成前的历史暴露控制，RPEval 检验任务级启停，PersistBench 检验减少错误用史时能否保持有益用史，BenchPreS 检验正式交付及表达实现。这是看过开发结果后的范围建议。两项主评测各自沿用的强策略尚未成为一个验证过的共同算法。

- [共同动作空间的事后可行性](https://github.com/jhOo1/personal-agent-application/commit/60a70d1)：同一映射在聚合保护下可达 875/1219、38/44、41/42；238 种摘要仅 5 种跨域出现，不能据此证明可以预测。
- [按来源留出的真实回放](https://github.com/jhOo1/personal-agent-application/commit/9eafcab)：794/1219、20/44、33/42，三个强参照为 814/1219、38/44、38/42。停止继续拟合该摘要规则。
- [扩展 BenchPreS 候选的审计](https://github.com/jhOo1/personal-agent-application/commit/a84aa84)：26 题上，Gate 已实现 38/44 个合法属性，额外外部答案的事后上界为 40；逐题保护误用、非加粗属性和完整度后为 39。用现有成稿做更复杂的选择，余量很小。

评审提出两点修正。将生成前暴露的范围也纳入研究问题，保留非空选择可能有效的案例。考虑替换评测时，应说明部署可见信息不足以区分所需动作，或评分协议无法可靠测量所声称的行为；将难以提分单独作为理由没有证据支持。后续独立确认前应冻结该范围、外部对照、保护指标和缺失处理。

本次附加核验只读既有 PersistBench 元数据。原研究仓库同级报告目录中，paired_regret_policy_v1/MATRIX.json 的 58 个 PersistBench UID 与 persist_selected_gepa_completion_v1/SUMMARY.json 的 7 个 UID 取并集为 58。全部可在 persist_public_source_census_v1/PUBLIC_CENSUS_COHORT.json 的 500 个 UID 中映射到组。将这些组与 persist_public_source_near_screen_v1/CURRENT.json 中 remaining_metadata 的组求交，交集为零。旧筛查的 270 行、253 个组是历史上界。这次只排除了两份指定名册造成的额外交叉，不能认证未曝光。没有打开预留题、挑选新题或发起模型实验。
