# 强方法与论文对照

| Benchmark | 当前项目强参照 | 代码定位与协议 |
|---|---|---|
| RPEval | IPE-C | 任务独立与完整历史端点，按冻结策略选择最终回答。见实现目录的 `ipe_c_*`、RP-Reasoner 重建脚本，以及 [端点结果](reports/IPE-C-READOUT.md)。 |
| BenchPreS | Strong Gate | 按当前任务判断历史适用性后生成消息。参见 BenchPreS 论文桥接、固定强稿风格实验和三基准机会盘点。 |
| PersistBench | PB_RUBRIC | 使用作者 rubric 的归档强参照。参见 `persist_author_controls_v2` 和作者复现、评分适配脚本。项目适配评分与作者榜单不宜直接比较。 |

这些方法是当前项目中的强参照。历史小样本、评分适配和旧稿复用结果还不足以认证统一 SOTA。外部论文比较须核对模型、样本、Judge 和聚合协议。

最近的 CDC、DCR、DREW、TATR 和组外路由实现、协议与分析已保留在 [实现目录](implementation/README.md)。数据和原始回执按 [迁移说明](MIGRATION.md) 获取。
