# 首次生成策略追加的离线验收

原始请求变换已实现，搜索和确认窗口尚未冻结。最多三条不重复的单行规则，总 UTF-8 字节数不超过 1024。原子操作每次 ADD、REPLACE 或 DELETE 一条。原始请求指纹不符即停止。空策略与无历史分支原样返回；有史分支仅修改唯一系统消息，其余请求字段保持原值。这里验收的是请求构造，尚无模型成绩。

| 历史路径 | 核验请求数 |
|---|---:|
| RPEval 有史 RP | 137 |
| RPEval 重建并精确旁路的 task-only | 158 |
| BenchPreS Strong Gate | 43 |
| PersistBench PB_RUBRIC | 50 |

这些是可核验历史报文的数量，可能不是独立来源组或完整分母。验收对模型零调用，不重跑已有单元，不触碰封存集。用原研究仓库根及 Python 3.12 执行：

```sh
b=reports/qamc_contextual_match_v2_20261112
p=src:.:scripts
for d in authority_compilation_v1 decision_visibility_v42 counterfactual_decision_v41 joint_preference_planning_v1 decision_edit_preflight anchored_decision_patch_v1 strong_actor_boundary_audit_v1 execution_feedback_policy_v1 transactional_reassembly_v1 ipe_c_full_exposed_panel_v1; do
  p="$p:$b/$d"
done
PYTHONPATH="$p" python "$b/native_residual_v1/check_original_wires.py"
```

完整归档、历史入口和评分收据通过私有工作区恢复。下一步冻结按来源和画像隔离的面板以及同预算策略优化对照，再实现评分与逐组晋级判断。

## 冻结面板接线

`build_jobs.py` 对选定分割重验面板、基线成稿哈希和有史 Actor 报文，并检查公开输入合同及请求容量。在上述 PYTHONPATH 下，通过 stdin 输入 JSON 单行规则数组，位置参数选 `search` 或 `confirmation`。命令仅输出数量。实际核验每侧非空候选各构造 17 个请求，RPEval 6、BenchPreS 4、PersistBench 7，复用 3 个无史端点。空策略复用 20 项，零新请求。尚未运行搜索、生成或评分。

## 候选评分接线

`evaluate_nro_policy.evaluate` 将一份候选策略交给三套原始 Actor 和冻结评分协议。Actor 与 Judge 回执须逐键匹配原请求哈希。未生成、交付未知及缺分保留；逐字相同答案在同题固定评分合同下复用，空策略不派发。基准分批保留原始模型和采样参数，评分使用原评分入口。

离线使用替身回执打通了三种评分报文。组外开发侧一个非空候选最多 17 个 Actor 请求；当所有候选答复都不命中复用时，构造 6 个 RPEval、24 个 BenchPreS、7 个 PersistBench 评分请求。评分替身返回未知时，仅保留三个未修改无史端点的原分。这里没有真实模型调用或新增分数。
