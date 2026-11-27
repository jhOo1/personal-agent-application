# 已核对的结果时间线

数字均以对应实验的共同有效面板为准，不横跨协议拼分。

| 实验 | 观察 | 判定 |
|---|---|---|
| B4 Flat / Bound | 同一批48条来源内容和顺序一致。MemSyco common 15，Gate+与Bound均9/15，Flat 8/15。PersonaMem Gate+ 12/16，Flat与Bound 11/16。BenchPreS common 15，MR从15/48到6/48，两种B4的AAR均19/27，Gate+18/27，完整度由4.533降至4.200与3.867。 | 有误用下降，未建立绑定独立收益。 |
| Incremental Style / RPEval小样本 | 四法共同10题，Incremental 38/53，Style 33/53，RP-Reasoner 32/53，Des2Gen 25/53；仅两个来源组。 | 支持多候选筛选的局部收益。样本无同时需要两条合法偏好的案例。 |
| C5 RPEval大开发面板 | 254题共同有效，C5 555/1351，重建RP 747/1351；全A为71/487与246/487。 | 终答差距明显。即使放行ID一致，Actor输入也可能不同。 |
| IPE-C三端点 | 274题、1462位，IPE-C 953，任务独立874，完整历史824。全A分数为400、426、267。 | 整体有选择性启用收益；全A上仍有抑制空间。 |
| IPE-C第二骨干 | GPT-4.1同协议开发22题115位，IPE-C、仅任务、完整史分别为80、71、61；归档Qwen同题70、61、59。 | 观察到相同方向，未做独立确认。 |
| 受保护路由 | 三折无可行规则；BenchPreS归档候选上界38/44与强Gate持平。 | 单纯在旧终稿里选答案无法实现缺失偏好。 |
| 不同范围修订 | BenchPreS 16题有限润色相对强Gate AAR 30/40→31/40，MR均0/40，完整度4.813→4.625。PersistBench固定Rubric作用修订迎合无净改善，跨域失败0/8→3/8。 | 保留结构保护的观察，两个方法均未晋级。 |
| CDC / DCR / DREW | 各阶段分母和结果见独立报告。统一候选至今未达到协议匹配强对照之上的稳定优势。 | 当前强参照分别为IPE-C、Strong Gate及PB_RUBRIC。 |
| RPEval 单来源成稿盲选 | 22 题，普通盲选和 RP 均 17/22，Des2Gen 与 MemAdapter 各 18/22。成稿池事后上界 21/22。 | 普通盲选未胜，冻结奖励模型另行结算。见[配对结果](implementation/reports/qamc_contextual_match_v2_20261112/rpe_heterogeneous_reward_v1/DIRECT_READOUT.md)。 |
