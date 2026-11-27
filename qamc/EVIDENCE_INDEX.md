# 文件与实验核验索引

原仓库锚为 `fd8b855be`。以下“原路径”相对该仓库根。公开 `implementation/` 保留源目录布局，但仅收录审核通过的代码和报告。目录全集见[实验目录](EXPERIMENT_CATALOG.md)。

| 主题 | 公开入口 | 原路径与恢复材料 |
|---|---|---|
| B5 | [选择器](implementation/src/qamc/coverage_selector.py)、[提示](implementation/prompts/coverage_selector.md) | `reports/qamc_coverage_revision/{RESULTS.md,PAIRED_ANALYSIS.md,SCORER_AUDIT.md,FROZEN_CONFIG.json,MANIFEST_48.jsonl}`；逐题数据仅私有。 |
| C5 与论文方法差距 | [历史时间线](RESULTS_TIMELINE.md)、[强对照索引](STRONG_METHODS.md) | `reports/qamc_contextual_match_v2_20261112/paper_baseline_validation_156_v1/` 中各阶段评审与失败归因；具体 254 题同分母的原始汇总文件定位 UNKNOWN。 |
| IPE-C | [端点报告](reports/IPE-C-READOUT.md)、[复现入口](implementation/reports/qamc_contextual_match_v2_20261112/ipe_c_two_endpoint_completion_v1/complete_endpoints.py) | `reports/qamc_contextual_match_v2_20261112/ipe_c_two_endpoint_completion_v1/{FROZEN.json,RESULTS.json,RPEvalJudge_MANIFEST.json}`。旧端点及精确哈希在结果内。估计器模板与融合依赖见原仓库 `proposals/qamc_rpreasoner_paper/{appendix_prompts_v1.json,engine.py}`；公开代码快照未导出该目录。 |
| BenchPreS 风格与评分 | [对照报告](implementation/reports/qamc_contextual_match_v2_20261112/recipient_style_preservation_v1/READOUT.md) | 同名原目录中的 `RESULTS.json`、`SUMMARY.json`、`TEXT_CHECKS.json` 仅私有。 |
| BenchPreS 三次采样 | [冻结协议](implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/PROTOCOL.md)、[完整结算](implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/FINAL_READOUT.md)、[逐项缺失边界](implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/FINAL_FIELDWISE.json) | 同名原运行目录的计划、完整请求、评分与账本仅私有。新机按[当前恢复条件](MIGRATION.md#当前-benchpres-实验)核验。 |
| PersistBench 及共同失分 | [作者对照结算](implementation/reports/qamc_contextual_match_v2_20261112/persist_author_controls_v2/TERMINAL_RESULTS.md)、[机会盘点](implementation/reports/qamc_contextual_match_v2_20261112/strong_opponent_opportunity_v1/READOUT.md) | 机会盘点原目录的 `INVENTORY.json`、`WITNESSES.json` 仅私有。原 Kimi/Vertex 有效同协议结果 UNKNOWN。 |
| CDC / DCR / DREW | [CDC](reports/CDC-RESULTS.md)、[DCR](reports/DCR-RESULTS.md)、[DREW](reports/DREW-RESULTS.md) | 原目录依次为 `counterfactual_commitment_v1`、`decision_conditioned_realization_v1`、`archive_edit_opportunity_v1`，都在 `reports/qamc_contextual_match_v2_20261112/` 下；完整 `FROZEN.json`、`EXECUTION.json`、`RESULTS.json`、`READOUT.json` 及请求清单仅私有。结算提交依次为 `c17882cd2`、`ca4d4823b`、`adb2231e7`。 |
| RPEval 同一决定的候选供给 | [冻结协议](implementation/reports/qamc_contextual_match_v2_20261112/matched_alternative_rpeval_v1/PROTOCOL.md)、[逐组分数及账本摘要](implementation/reports/qamc_contextual_match_v2_20261112/matched_alternative_rpeval_v1/METRICS.json) | 原仓库冻结代码 `acf98f997`、结算 `14b80b0e5`。同名 `runs/qamc_contextual_match_v2_20261112/` 子目录下有 `CandidateSupply/`、`CandidateAnswer/`、`MultiCandidateJudge/`、`SingleDetailJudge/`、`LOCKED_ANSWERS_PRIVATE.json`、`GRADES_PRIVATE.json` 和 `LEDGER.json`。公开只含汇总、提示和驱动，整批已结算不重发。 |
| 原始请求与故障 | 公开报告的分母和账本摘要 | `runs/qamc_contextual_match_v2_20261112/<实验目录>/<阶段>/` 中的 SQLite 与回执。未打包目录或外部服务账本状态 UNKNOWN。 |

公开可阅读方法、代码、提示和汇总，但缺完整回执时无法确认每个请求或重新运行依赖归档的对照。私有恢复后可按同版本逐题核验，运行前仍需验证依赖、模型服务、单元状态和外部数据授权。完整公开下载路径不存在，见[私有恢复说明](MIGRATION.md)。
