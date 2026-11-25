"""Report only settled native results and separately price the observed inference paths."""
from collections import Counter, defaultdict
import json

import audit_edit_size
import observe_decision_edit as observer
import run_decision_edit as run

NAMES = {
    run.GENERIC: "普通局部编辑",
    run.DECISION: "决策局部编辑",
    run.comparisons.GATE: "归档强 Gate",
    run.comparisons.RP: "归档 RP-Reasoner",
    run.comparisons.ZERO: "共享无历史成稿",
    run.comparisons.RULE: "RP 未判 C 用无历史成稿",
    run.comparisons.GENERIC: "V44 通用选稿",
    run.comparisons.REVIEW: "V41 强通用复核",
}
FIELDS = ("OPB", "UPB", "FM", "full_match")
ACTIVATION_NAMES = {
    "APPLIED_APPLIED": "两臂均应用",
    "NOT_APPLIED_APPLIED": "仅决策编辑应用",
    "APPLIED_NOT_APPLIED": "仅普通编辑应用",
    "NOT_APPLIED_NOT_APPLIED": "两臂均保留原稿",
    "UNAVAILABLE": "至少一臂编辑缺失或无效",
}


def match_row(label, method, result):
    m = result["match"]
    if not m["valid_cases"]:
        return f"| {label} | 0 | NA | NA | NA |"
    old, new = (m["scores"][name] for name in (method, run.DECISION))
    bounds = m.get("95pct_source_bootstrap")
    interval = f"[{100*bounds[0]:+.2f}, {100*bounds[1]:+.2f}]" if bounds else "NA"
    return (f"| {label} | {m['valid_cases']} / {m['n_source_groups']} | {old['matched']}/{old['positions']} | "
            f"{new['matched']}/{new['positions']} | {100*m['match_delta']:+.2f} {interval} |")


def severity(value):
    n = value["n"]
    return f"{value['left']:.3f} → {value['right']:.3f}（{n}）" if n else "NA"


def activation_pairs(rows):
    panels = defaultdict(list)
    for row in rows:
        if row["assignment"] == "NO_USABLE_DRAFT":
            continue
        methods = [row["edits"][m] for m in run.edit.METHODS]
        if any(item["status"] != "OK" for item in methods):
            name = "UNAVAILABLE"
        else:
            name = "_".join("APPLIED" if item["transaction"] == "APPLIED" else "NOT_APPLIED"
                            for item in methods)
        panels[name].append(row)
    return {
        name: {"assigned": len(sample), "match": run.v42.paired(sample, run.GENERIC, run.DECISION),
               **{field: run.comparisons.grade_pair(sample, run.GENERIC, run.DECISION, field)
                  for field in FIELDS}}
        for name, sample in panels.items()
    }


def render(result, extra, cost, scores, audit, activation):
    actions = result["edit_status"]
    text = [
        "# RPEval 局部编辑同题实验终态", "",
        f"全部 {result['assigned']} 道开发题已结算。{result['eligible']} 道有共享初稿。"
        f"冻结筛查 **{'通过' if result['screen_pass'] else '未通过'}**。"
        "这是已曝光开发数据，独立确认、人工行为核验以及跨基准新方法成绩仍待验证。", "",
        "## 共同有效原生分", "",
        "| 配对对照 | 同题 / 来源组 | 对手 Match | 决策局部编辑 Match | 差值 pp 与 95% 来源组区间 |",
        "|---|---:|---:|---:|---:|",
    ]
    for subset, label, methods in (
        ("eligible", "全部", run.CONTROLS),
        ("all_A", "全 A", (run.GENERIC, run.comparisons.RP)),
        ("contains_BC", "含 B/C", (run.GENERIC, run.comparisons.RP, run.comparisons.GATE, run.comparisons.RULE)),
        ("outside_documented_diagnostics", "排除诊断来源", run.CONTROLS),
    ):
        text.extend(match_row(f"{label} · {NAMES[m]}", m, result["metrics"][subset][m]) for m in methods)
    text.extend(match_row(f"排除诊断来源且含 B/C · {NAMES[m]}", m, values) for m, values in extra.items())
    text.extend(["", "## 原生保护项", "",
                 "每格给出对照均值、决策编辑均值及该指标的共同分母。OPB 表示过度使用，"
                 "UPB 表示使用不足，FM 表示可行性偏差。完整匹配使用原生整题字段，任务完整度仍需在相应基准上核验。", "",
                 "| 配对对照 | OPB | UPB | FM | 整题匹配 |", "|---|---:|---:|---:|---:|"])
    for label, metrics in (("含 B/C", result["metrics"]["contains_BC"]), ("排除诊断来源且含 B/C", extra)):
        for m in (run.GENERIC, run.comparisons.RP, run.comparisons.GATE, run.comparisons.RULE):
            text.append("| " + " | ".join([f"{label} · {NAMES[m]}", *(severity(metrics[m][f]) for f in FIELDS)]) + " |")

    text.extend(["", "## 冻结筛查", ""])
    for m, checks in result["screen"].items():
        failed = [k for k, passed in checks.items() if not passed]
        text.append(f"- {NAMES[m]}，" + ("均满足" if not failed else "未满足 " + "、".join(failed)) + "。")
    text.extend(["", "## 作用域与实际成稿", ""])
    paired = audit["paired_source_references"]["all"]
    text.append(f"- 两臂都有可编译回复的 {paired['roots']} 道题中，{paired['different_visible_answers']} 道成稿不同。"
                "源引用按原始作者标签分层，不能直接换算成误用或漏用分。")
    for m in run.edit.METHODS:
        arm = audit["by_stratum"].get(m + "/all", {})
        text.append(f"- {NAMES[m]}有 {actions[m].get('APPLIED',0)} 个实际应用，"
                    f"{actions[m].get('edit_budget',0)} 个大小回退。"
                    f"对同一回复做不改变拟议成稿的首尾字符扣除，有 {arm.get('budget_rejected_only_untrimmed',0)} 个可过大小限制，"
                    f"仅用于核验计数。原生逐题有效 Match 为 {scores[m]['has_match']}，复用旧分记录 {result['native_grade_reused'][m]}。")
    text.extend(["", "按实际应用状态分解的配对结果用于描述原生差值来自哪些成稿，冻结总体仍是主比较。", "",
                 "| 两臂成稿状态（指派题数） | 同题 / 来源组 | 普通编辑 Match | 决策编辑 Match | 差值 pp 与 95% 来源组区间 |",
                 "|---|---:|---:|---:|---:|"])
    for name, title in ACTIVATION_NAMES.items():
        data = activation.get(name)
        if data:
            text.append(match_row(f"{title}（{data['assigned']}）", run.GENERIC, data))
    text.extend(["", "## 请求与部署用量", "",
                 f"实际新增各阶段请求 {json.dumps(result['new_requests'], ensure_ascii=False)}。"
                 f"传输状态 {json.dumps(result['transport_status'], ensure_ascii=False)}。"
                 f"报告 {result['reported_tokens']:,} Token，未知用量 {result['unknown_usage']} 条。", "",
                 "以下为只比较成稿推理的同题用量，独立于评分账本。两种局部编辑及归档 Gate 各为两次推理。", "",
                 "| 对照 | 有效题 / 来源组 | 对照报告 Token | 决策编辑报告 Token | 同题 Match |",
                 "|---|---:|---:|---:|---:|"])
    for m, row in cost["matched_inference_cost_without_judge"].items():
        a, b = (row["methods"][name] for name in (m, run.DECISION))
        text.append(f"| {NAMES[m]} | {row['roots']} / {row['source_groups']} | {a['reported_tokens']['total_tokens']:,} | "
                    f"{b['reported_tokens']['total_tokens']:,} | {a['matched']}/{row['positions']} · "
                    f"{b['matched']}/{row['positions']} |")
    text.extend(["", "[冻结原生汇总](RESULTS.json) · [逐题原生成绩与回执](SETTLED.json) · "
                 "[细分保护项与用量](ADDITIONAL_AUDIT.json) · [真实编辑作用域和字符计数](EDIT_REFERENCE_AUDIT.json)"])
    return "\n".join(text) + "\n"


def main():
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise RuntimeError("Terminal analysis requires completed editor and native scorer receipts")
    plan = run.read(run.OUT / "FROZEN.json")
    settled = run.read(run.OUT / "SETTLED.json")
    rows, ledger = settled["rows"], settled["ledger"]
    if state["physical_requests"] != len(ledger) or sum(r["unit"]["stage"] == run.EDIT for r in ledger) != plan["request_caps"][run.EDIT]:
        raise ValueError("Physical stage receipts disagree with frozen settlement")
    result = run.read(run.OUT / "RESULTS.json")
    reflected = run.report(plan, rows, ledger)
    if result != json.loads(json.dumps(reflected)):
        raise ValueError("Native settlement differs from report replay")
    original = run.read(run.prior.OUT / "FROZEN.json")["roots"]
    audit = audit_edit_size.run_audit()
    subset = [r for r in rows if r["assignment"] != "NO_USABLE_DRAFT"
              and r["group"] not in plan["diagnostic_source_groups"] and set(r["labels"]) != {"A"}]
    extra = {m: {"match": run.v42.paired(subset, m, run.DECISION),
                 **{k: run.comparisons.grade_pair(subset, m, run.DECISION, k) for k in FIELDS}}
             for m in (run.GENERIC, run.comparisons.RP, run.comparisons.GATE, run.comparisons.RULE)}
    scores = {}
    for m in run.edit.METHODS:
        scores[m] = {"has_match": sum("match" in row["native"][m]["fields"] for row in rows),
                     "origins_or_statuses": Counter(row["native"][m].get("reuse") or
                         row["native"][m].get("status", "UNAVAILABLE") for row in rows)}
    cost = observer.costs(plan, original, rows, ledger)
    activation = activation_pairs(rows)
    additional = {"native_score_statuses": scores, "mixed_outside_documented_diagnostics": extra,
                  "deployment_cost": cost, "outcome_conditioned_activation_pairs": activation,
                  "new_model_requests": 0}
    for name, obj in (("EDIT_REFERENCE_AUDIT.json", audit), ("ADDITIONAL_AUDIT.json", additional)):
        run.probe.freeze(run.OUT / name, json.loads(json.dumps(obj)))
    text = render(result, extra, cost, scores, audit, activation)
    report = run.OUT / "TERMINAL.md"
    if report.exists() and report.read_text() != text:
        raise ValueError("Terminal Markdown differs from report replay")
    if not report.exists():
        report.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
