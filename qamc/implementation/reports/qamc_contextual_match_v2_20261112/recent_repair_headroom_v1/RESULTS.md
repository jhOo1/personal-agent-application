# 同一强稿上的近期修复空间核对

**停止继续扩大当前强稿后处理路线。** 将候选原文局部遮蔽、按当前任务条件分支、无历史对照引文修订、执行者视角推演四个已结算实验接起来。即使事后允许逐题挑选所有已实际生成的改稿，三个基准的主分也无净增。提高下一轮的终答表现需要产生当前改稿池中没有的有效方案。

由原冻结档案恢复专项强稿。跨档案重合时验证强稿正文哈希、评分向量和旗标状态一致。由实验结算文件读取方法、答复和评分。逐题去重确切成稿，保留缺失；同一成稿若有不同分数则不进入事后择优。每项分数与强稿的同题分母一致。没有将四个已曝光面板当作独立重复，未把调参、筛选结果或作者标签送入任何推理请求。

| 基准或轨道 | 题 / 来源组 | 有不同成稿及可比评分的题 | 实际不同且有分的改稿 | 强稿主分 | 保护项不退的事后最优 |
|---|---:|---:|---:|---:|---:|
| RPEval Match | 7 / 7 | 7 | 20 | 19/45 | 19/45 |
| BenchPreS AAR | 4 / 3 | 3 | 10 | 8/10 | 8/10 |
| PersistBench 迎合通过 | 4 / 4 | 3 | 9 | 1/4 | 1/4 |
| PersistBench 跨域通过 | 1 / 1 | 1 | 3 | 1/1 | 1/1 |
| PersistBench 严格有益使用 | 5 / 5 | 5 | 11 | 5/5 | 5/5 |

共 21 道不同题，90 个逻辑单元。35 个与强稿逐字相同，53 个确切改稿有分，2 个输出缺失，未补发。没有同题同文改稿的分数冲突。在撤销所有保护项的事后选择下，也没有一道改稿主分高于原强稿。RPEval 有 3 道在主分持平时改善 OPB 或 FM，其他记录保护项未退且没有评分旗标。三个例子是 `explicit/054`、亲子郊游 `explicit/076`、闺蜜生日题。后者仍为 0/7，不能把一次 OPB 下降写成主体问题已经解决。PersistBench 没有达到相同标准的次指标净益。严格有益和跨域切片的强稿原先已到满分，只能检查保护或报告行为改变。

保护项为 RPEval OPB/UPB/FM、BenchPreS MR/完整度/适用非加粗实现，PersistBench 的同轨原等级。使用项目既有适配评分。来源与样本数量有限，结果约束的是这些已生成的改稿和这条实验路线的研发优先级。它不排除其他改稿、更强骨干或不同条件下的潜在收益。

## 可比性排查

重新核对公开评分供应。Vercel 有 Kimi K2 Thinking 模型卡，页面列出 DeepInfra；实际匿名模型目录 HTTP 200，查到 `deepseek/deepseek-r1` 和 `openai/gpt-5-mini`，没有查到 `moonshotai/kimi-k2-thinking`。DeepInfra 的同名公开模型页当前返回 404。本次环境无所检查的 Vercel 或 DeepInfra 凭据，未派发推理，不能判断已认证账户的供应状态。原 Vertex 路线和项目适配分继续分开。PairPref 的论文可核对，未找到作者完整数据和评分发布，保留候选身份。 [Vercel 模型卡](https://vercel.com/ai-gateway/models/moonshotai/kimi-k2-thinking) · [供应商目录](https://ai-gateway.vercel.sh/v1/models) · [PairPref 论文](https://arxiv.org/html/2609.34526v1)

**下一研究选择。** 优先使用已经得到同题双裁判迎合收益的 SELECTED 路径做强对照，从生成前证据使用入手，验证一次真正执行到必要事实的改变。RPEval 保留 IPE-C 和 RP 重建作为误用与合法约束的对照，BenchPreS 继续约束交付完整度与适用表达。这里没有新增 Benchmark 替换或 SOTA 主张。 [PersistBench 同成稿双裁判](../persist_selected_crossjudge_fr3_v1/RESULTS.md)

## 复算

恢复原仓库私有结算回执后，从仓库根执行。标准输出只含可公开的聚合结果。可选 `--local-case-ids` 仅将诊断用题标写到标准错误。 [聚合 JSON](SUMMARY.json) · [只读代码](audit.py)

```bash
set -o pipefail
base=reports/qamc_contextual_match_v2_20261112
driver="$base/participant_execution_preflight_v1/run.sh"
launcher=$(sed '$d' "$driver")
bash -c "$launcher
exec ../qamc/.venv/bin/python \"\$1\"" "$driver" "$base/recent_repair_headroom_v1/audit.py" |
  cmp - "$base/recent_repair_headroom_v1/SUMMARY.json"
```
