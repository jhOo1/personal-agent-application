# 在新环境接续 QAMC

公开 GitHub 档案提供研究索引、协议和成果摘要。实际续跑还需要从私有渠道复制源仓库 Git bundle 及实验工作区压缩包。包中可能包含完整评测文本、封存集或原始回执。请通过有访问控制的渠道传输。

## 恢复

将 `qamc-head.bundle`、`workspace-overlay.tar.gz`、`SHA256SUMS` 放在同一个目录。使用新建目录恢复，以免覆盖新环境中的其他工作。

```sh
shasum -a 256 -c SHA256SUMS
git init qamc-recovered
git -C qamc-recovered fetch ../qamc-head.bundle HEAD
git -C qamc-recovered switch -c recovered FETCH_HEAD
tar -xzf workspace-overlay.tar.gz -C qamc-recovered
```

如需还原原工作树暂存状态，在解包前使用包内 `staged.patch` 与 `unstaged.patch`，依次执行 `git apply --index` 和 `git apply`。仅用于恢复文件内容时直接解包即可。

创建新虚拟环境，并按照源项目 `pyproject.toml` 和 `requirements.lock.txt` 安装依赖。另行配置目标机的模型凭据、私有服务地址和网关参考配置，重新核对模型别名、协议及依赖路径。迁移包未测试新环境的联网调用。原机的虚拟环境不能作为跨机器依赖。

## 恢复点

- 归档强基线为 IPE-C、Strong Gate、PB_RUBRIC。历史请求、已有答案、已结算分数及失败保留在实验目录与账本中。
- DREW 已结算并关闭通用版。下一窗口是强基线首次生成的共享策略优化，尚未发出请求。详见 [DREW 结果](reports/DREW-RESULTS.md)。
- 首先离线读取冻结方案与结果，再检查新环境的 API 与评分协议。已有有效实验直接复用。保留交付未知记录，避免误重发。
