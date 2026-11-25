# QAMC 研究档案

QAMC 研究在候选记忆固定的条件下，何时使用历史、历史应影响哪个决定，以及怎样同时减少误用与漏用。当前主要评估 RPEval、BenchPreS 和 PersistBench。开发结果和发布协议可比的确认结果分开记录。

| 研究阶段 | 方法与结论 |
|---|---|
| Preference Is Not Permission | 早期研究检验历史习惯可能被当成新增权限。模拟计划、执行结果、服务缺失分别记录。 |
| QAMC v3、B 系列与 BACE | 比较读侧证据选择、决策绑定、覆盖保护、Strong Gate、单模型与独立 Allow/Deny。已有证据表明更多审查层不会自动带来终答增益。 |
| Style、Incremental、RPEval 与 PrefEval | 用实际应用衡量误用与漏用。RPEval 的小样本中 Incremental 优于原 Style，但来源少，不能推出多条合法偏好同时保留。 |
| 双 View、Matcher、C5 | 逐步隔离表示、选择和生成错误。C5 在 BenchPreS 局部减少误用，RPEval 终答落后 RP 重建版，未选为三基准冠军。 |
| IPE-C、强 Gate、PB_RUBRIC | 当前按基准保留三个强参照。IPE-C 在 RPEval 按任务在历史启用和仅任务端点间选择。Strong Gate 在 BenchPreS 先筛适用历史。PB_RUBRIC 在 PersistBench 用作者规则提示生成。三者不是已验证的统一 SOTA。 |
| AIR、身份绑定、引用指针、局部策略及候选路由 | 探索主体错配、历史曝光与选择。字面引文核验不能证明语义归属，旧稿路由也无法创造此前没有的合法实现。具体实验目录见索引。 |
| CDC、DCR、DREW | 三个完整开发对照。CDC 否决无增量；DCR 局部与共享证据持平，均弱于强稿；DREW 仅在项目生命周期一处获得 PersistBench 净收益，未达到跨来源晋级门槛。 |
| 当前后续方向 | 检验共享策略能否在强方法首次生成时改善真实终答。计划比较原子规则优化与同预算普通整块优化，按来源组隔离搜索和验证。该方向尚无新实验成绩。 |

- [全部归档目录索引](EXPERIMENT_CATALOG.md)
- [IPE-C 端点对照](reports/IPE-C-READOUT.md)
- [CDC](reports/CDC-RESULTS.md) · [DCR](reports/DCR-RESULTS.md) · [DREW](reports/DREW-RESULTS.md)

历史原始请求、回执、完整题目、模型配置及本机未提交改动保留在原实验工作区。本公开仓库收录核对过的归档材料；来源索引中的路径属于原仓库。

[已核对的历史结果时间线](RESULTS_TIMELINE.md)
