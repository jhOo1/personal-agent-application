"""Render paired terminal results and independent source-group witnesses for V44."""
import analyze_fixed_answer_choice_v44 as audit
from qamc.common import sha

run, task = audit.run, audit.task
G, E = audit.GENERIC, audit.EVIDENCE
LABELS = {
    audit.RP: "RP-Reasoner 重建版", G: "本轮同调用通用选择", audit.REVIEW: "V41 强通用复核",
    audit.GATE: "强 Gate", audit.ZERO: "无历史成稿", audit.RULE: "RP 未判 C 时切换无历史",
}


def summary_row(name, metric):
    left, right = tuple(metric["scores"])
    a, b = (metric["scores"][key] for key in (left, right))
    lo, hi = metric["95pct_source_bootstrap"]
    return (f"| {name} | {metric['valid_cases']} / {metric['n_source_groups']} | "
            f"{a['matched']}/{a['positions']} | {b['matched']}/{b['positions']} | "
            f"{metric['match_delta'] * 100:+.2f} [{lo * 100:+.2f}, {hi * 100:+.2f}] |")


def create_readout(result, sensitivity, cost, prior_control):
    lines = ["# V44 固定成稿比较终态", "",
             f"结算 233 道已曝光开发题。{result['eligible_roots']} 道有两份候选，另 6 道无历史成稿缺失。"
             " 两臂输入、可见顺序、模型、候选成稿、原生评分全部匹配。区别限于系统提示中的比较方法。",
             "", "| 对照 | 共同题 / 来源组 | 对照 Match | V44 证据核验 | 差值 pp 与来源组 95% 区间 |",
             "|---|---:|---:|---:|---:|"]
    for left, name in LABELS.items():
        lines.append(summary_row(name, result["comparisons"]["eligible"][left]["match"]))
    lines.extend(["", "## 分层约束与机制检验", "",
                  "| 与同调用通用选择配对 | 共同题 / 来源组 | 通用 Match | 证据核验 Match | 差值 pp 与来源组 95% 区间 |",
                  "|---|---:|---:|---:|---:|"])
    for key, label in (("all_A", "作者全 A"), ("contains_BC", "含作者 B/C"), ("less_exposed", "较少直接曝光")):
        lines.append(summary_row(label, result["comparisons"][key][G]["match"]))
    shared = result["strict_common"]
    values = sensitivity["source_choice_counts"]["all"]
    lines.extend(["", f"七法共同有效 {shared['n']} 道、{shared['source_groups']} 个来源组。"
                  f" 两臂均输出选择 {values['paired_choices']} 道，其中 {values['different_source']} 道选了不同成稿。"
                  f" 原生有效的两法差值为 {values['delta']:+d} 位，按现有评分争议范围得到 "
                  f"{values['sensitivity_low']:+d} 至 {values['sensitivity_high']:+d}。原分照存。",
                  "", "含 B/C 的严重度字段按各自共同分母计算。以下为相对通用选择的差值，降低为好。"])
    fields = result["comparisons"]["contains_BC"][G]
    for field in ("OPB", "UPB", "FM"):
        values = fields[field]
        lines.append(f"- {field}，共同 {values['n']} 道，{values['left']:.3f} → {values['right']:.3f}，"
                     f"每题差 {values['delta']:+.3f}。")
    ceiling = sensitivity["nondeployable_guarded_ceiling"]["all"]
    lines.extend(["", f"两份成稿及严重度共同有效的 {ceiling['roots']} 道题，"
                  f"RP 为 {ceiling['rp_matched']}/{ceiling['positions']}。利用原生分事后择优，"
                  f"在含 B/C 题上逐题限制 UPB 和 FM 不高于原 RP，可得到 "
                  f"{ceiling['guarded_best']}/{ceiling['positions']}。这是基于已评分答案的理论对照。"])
    checks = result["advancement_checks"]
    outcome = "通过开发筛查" if result["statistical_screen_pass"] else "未通过开发筛查"
    lines.extend(["", f"冻结判定为**{outcome}**。"
                  " 各主对照未达到的检查为 " +
                  "，".join(f"{LABELS[m]}（{'、'.join(k for k in details if not details[k]) or '无'}）"
                            for m, details in checks.items()) + "。独立行为验证和独立确认仍待完成。",
                  "", "## 评分归因负对照", "",
                  f"已保存的 {prior_control['all_A']['roots']} 道真正无历史的全 A 成稿，"
                  f"仍有 {prior_control['all_A']['all_zero']} 道原生整题零分。warm-dinner 的 explicit/089 与 implicit/088"
                  " 复用同一生成请求和同一成稿，原生分分别是 4/4 与 0/4。见 [完整负对照](TASK_PRIOR_CONTROL.md)。",
                  "", "## 实发与成本", "",
                  f"逻辑选择 454，逐字复用 2，物理回执 **{result['physical_requests']}**。"
                  f" {len(result['retained_failures'])} 个保留失败或交付未知，"
                  f"已报告 **{result['reported_tokens']:,} Token**，未知用量 {result['unknown_usage']}。"
                  " 没有新增生成和评分请求。"])
    runtime = cost["common_matched_and_cost"]
    if runtime["common_roots"]:
        lines.append(f"同题原生 Match 和生成用量齐全的 {runtime['common_roots']} 道中，独立运行"
                     f"（含两份候选成稿和前置预测）报告用量为 RP "
                     f"{runtime['cost'][audit.RP]['totals']['total_tokens']:,}、V41 强通用复核 "
                     f"{runtime['cost'][audit.REVIEW]['totals']['total_tokens']:,}、本轮通用选择 "
                     f"{runtime['cost'][G]['totals']['total_tokens']:,}、证据核验 "
                     f"{runtime['cost'][E]['totals']['total_tokens']:,} Token。")
    lines.extend(["", "[完整原生分与回执](COMPLETED.json) · [来源组配对和判定](RESULTS.json) · "
                  "[评分争议](SENSITIVITY.json) · [独立成本](STANDALONE_COST.json) · "
                  "[跨基准离线验收](TRANSFER_PREFLIGHT.md)"])
    return "\n".join(lines) + "\n"


def witnesses(rows, sensitivity):
    plan = run.read(run.stage.prior.OUT / "FROZEN.json")
    drafts = task.saved_drafts(plan)
    roots = {r["uid"]: r for r in plan["roots"]}
    indexed = {r["uid"]: r for r in rows}
    selected = {}
    for name in ("all_A", "contains_BC"):
        for sign in (-1, 1):
            subset = [w for w in sensitivity["scored_choice_disagreements"]
                      if w["stratum"] == name and w["match_delta"] * sign > 0]
            groups = set()
            for item in sorted(subset, key=lambda row: (-abs(row["match_delta"]), row["uid"])):
                if item["group"] not in groups:
                    groups.add(item["group"])
                    selected[item["uid"]] = item
                if len(groups) == 2:
                    break
    data = []
    for uid, item in selected.items():
        r, root = indexed[uid], roots[uid]
        rp = root["archived"][audit.RP]["answer"]
        baseline = drafts[root["task_wire_sha256"]]["answer"]
        request = run.contract.packet(root, rp, baseline)
        for method in run.ARMS:
            if sha(run.contract.execute_choice(request, r["choices"][method]["raw"])) != r["choices"][method]["answer_sha256"]:
                raise ValueError("Witness choice no longer yields the archived answer")
        data.append({**item, "shared_request_body": request, "author_labels_for_evaluation_only": r["labels"],
                     "choices": r["choices"], "native": {m: r["native"][m] for m in (audit.RP, audit.ZERO, G, E)}})
    return data


if __name__ == "__main__":
    result = run.read(run.OUT / "RESULTS.json")
    sensitivity = run.read(run.OUT / "SENSITIVITY.json")
    cost = run.read(run.OUT / "STANDALONE_COST.json")
    task_only = run.read(run.OUT / "TASK_PRIOR_CONTROL.json")
    bundle = run.read(run.OUT / "COMPLETED.json")
    if result["state"] not in ("COMPLETE", "SETTLED_WITH_RETAINED_DELIVERY_UNKNOWN"):
        raise ValueError("Only terminal results may be rendered")
    run.probe.freeze(run.OUT / "NATIVE_WITNESSES.json", witnesses(bundle["rows"], sensitivity))
    print(create_readout(result, sensitivity, cost, task_only), end="")
