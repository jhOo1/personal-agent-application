# 在新环境接续 QAMC

公开 GitHub 档案提供研究索引、协议和成果摘要。实际续跑还需要从私有渠道复制源仓库 Git bundle 及实验工作区压缩包。包中可能包含完整评测文本、封存集或原始回执。请通过有访问控制的渠道传输。

## 恢复

将 `qamc-head.bundle`、`workspace-overlay.tar.gz`、`SHA256SUMS` 放在同一个目录。使用新建目录恢复，以免覆盖新环境中的其他工作。

```sh
shasum -a 256 -c SHA256SUMS
git init qamc-recovered
git -C qamc-recovered bundle verify "$(pwd)/qamc-head.bundle"
git -C qamc-recovered fetch "$(pwd)/qamc-head.bundle" HEAD
git -C qamc-recovered switch -c recovered FETCH_HEAD
git -C qamc-recovered rev-parse HEAD  # expected fd8b855bece3a8aadabb008ee4e0ca6c727833d5
tar -xzf workspace-overlay.tar.gz -C qamc-recovered
```

如需还原原工作树暂存状态，在解包前使用包内 `staged.patch` 与 `unstaged.patch`，依次执行 `git apply --index` 和 `git apply`。仅用于恢复文件内容时直接解包即可。

创建新虚拟环境，并按照源项目 `pyproject.toml` 和 `requirements.lock.txt` 安装依赖。另行配置目标机的模型凭据、私有服务地址和网关参考配置，重新核对模型别名、协议及依赖路径。迁移包未测试新环境的联网调用。原机的虚拟环境不能作为跨机器依赖。

## 当前 BenchPreS 实验

下方 `fd8b855be` 私有包是 DREW 阶段快照。要迁移当前三次采样对照，应另取结算提交 `0350aaeb0` 的源工作区快照和原始账本。新快照需包含 `scripts/run_qamc_benchpres_three_draw.py`、它依赖的源仓库 `proposals/` 模块、已校验的历史输入资产，以及整个 `runs/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/`。其中 `PLAN_PRIVATE.json`、各批次的请求清单、回执与 SQLite，以及 `PACING.json` 共同记录执行进度。公开库只有协议、代码快照和脱敏汇总。当前私有快照在新机器上的完整恢复尚未验收。

1. 六批已结算。新机使用只读回放，保留所有已派发结果和缺失。
2. 核对 [PREFLIGHT](implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/PREFLIGHT.json) 中的计划哈希、固定输入以及原账本中的服务指纹。在恢复后的源项目运行 `PYTHONPATH=src:.:scripts python scripts/report_qamc_benchpres_three_draw.py`，核对已结算批次、评分状态和调用量。
3. 使用[结算脚本](implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/settle_repeat.py)重放完整分母和账本。31 条交付未知按结算保留。原账本缺失时，从原机或私有备份恢复。

冻结范围见[三次采样协议](implementation/reports/qamc_contextual_match_v2_20261112/benchpres_repeat_matched_v1/PROTOCOL.md)。旧私有包经验证的范围仍见下文。

## DREW 快照恢复点

- 归档强基线为 IPE-C、Strong Gate、PB_RUBRIC。历史请求、已有答案、已结算分数及失败保留在实验目录与账本中。
- DREW 已结算并关闭通用版。该阶段结果见 [DREW 结果](reports/DREW-RESULTS.md)。
- 首先离线读取冻结方案与结果，再检查新环境的 API 与评分协议。已有有效实验直接复用。保留交付未知记录，避免误重发。

## 交接验收记录（2026-11-25）

- 公开材料在只含 Git 暂存内容的独立目录中验收。79 个本地 Markdown 目标可解析，CDC、DCR、DREW 的 Prompt 与预算 JSON 可读，恢复分支和证据入口可定位。此为无会话依赖的文件验收。
- 原始结算记录只读核验了三轮各 24 个分派根，以及 214、132、161 个真实请求记录。无实验请求、无补评分。
- 两个私有包的 SHA-256 均通过。bundle 验证及独立检出指向 `fd8b855be`。另读取完 overlay 目录，确认含依赖锁、DREW 结果及原始 SQLite。此次未完整解包到目标机，未验收依赖安装或远端网关。
- 原实验工作区核验时有 96 个暂存新增和 5 个已跟踪修改，均保留。包内补丁用于恢复该快照对应状态；包之外的工作区、外部资源和未核实历史分支为 UNKNOWN。

### 独立 Codex 冷启动问答

在只含公开 Git 文件的新临时目录启动了新 Codex 会话，使用只读权限，要求仅根据当前目录答题。它以相对路径正确说明了论文假设、IPE-C 整题路由与逐条筛选的区别、三套强参照与评分差异、结论边界、精确复用和恢复顺序。结果与原报告和已核验代码一致。此次只运行文档评审，未调用实验模型或评分器。

评审指出公开快照缺 RP 估计模板和融合依赖、逐题原始证据及三条强路径的统一运行合同。已补写可见代码入口与原仓库依赖路径。历史报告的“下一步”仅适用各自阶段，当前恢复点以 [HANDOFF](HANDOFF.md) 为准。新策略窗口的面板、阈值和预算仍未冻结。
