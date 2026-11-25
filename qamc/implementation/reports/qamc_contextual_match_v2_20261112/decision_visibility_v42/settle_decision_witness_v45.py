"""Settle the wide V45 run and render its unchanged native grades and ablation."""
import json

import analyze_decision_witness_v45 as a
import audit_decision_witness_v45 as source_audit
import cost_decision_witness_v45 as cost_audit


NAMES = {
    a.GENERIC: "V44 同调用通用选择",
    a.RP: "归档 RP-Reasoner 重建版",
    a.REVIEW: "V41 强通用复核",
    a.C_PRIOR: "RP 未判 C 时选无历史成稿",
    a.GATE: "归档强 Gate",
    a.ZERO: "无历史成稿",
    a.SHAPE: "同回复仅检查格式",
    a.ANCHORED: "V45 引文核验",
}


def pair_row(name, other, pair):
    scores = pair["scores"]
    n = pair["valid_cases"]
    if not n:
        return f"| {name} | 0 | 未有效评分 | 未有效评分 | — |"
    left, right = scores[other], scores[a.ANCHORED]
    interval = pair.get("95pct_source_bootstrap")
    bounds = "—" if interval is None else f"[{100 * interval[0]:+.2f}, {100 * interval[1]:+.2f}]"
    return (f"| {name} | {n} / {pair['n_source_groups']} | {left['matched']}/{left['positions']} | "
            f"{right['matched']}/{right['positions']} | {100 * pair['match_delta']:+.2f} {bounds} |")


def severity_text(values):
    n = values["n"]
    return f"{values['delta']:+.3f}（{n}）" if n else "NA"


def render(result, audit, cost):
    ctx = result["compiler"]
    header = [
        "# V45 决策证据核验终态", "",
        f"派发覆盖 {result['physical_requests']} 个冻结请求。开发面板有 {result['assigned']} 道题，"
        f"{result['eligible']} 道能比较两份已生成成稿。增加生成请求和评分请求各 0 次。"
        "归档原生评分随逐字一致的成稿复用。", "",
        f"冻结开发筛查 **{'通过' if result['screen_pass'] else '未通过'}**。"
        "所有比较均为已曝光开发数据。真实使用是否正确与独立确认仍须分别验证。", "",
        "## 总体同题原生对照", "",
        "| 对照 | 有效题 / 来源组 | 对照 Match | V45 Match | 差值 pp 与来源组 95% 区间 |",
        "|---|---:|---:|---:|---:|",
    ]
    all_rows = [pair_row(NAMES[m], m, result["comparisons"]["eligible"][m]["match"]) for m in a.CONTROLS]
    strata = [
        "", "## 主要对照的分层", "",
        "| 分层与对照 | 有效题 / 来源组 | 对照 Match | V45 Match | 差值 pp 与来源组 95% 区间 |",
        "|---|---:|---:|---:|---:|",
    ]
    for panel, title in (("all_A", "全 A"), ("contains_BC", "含 B/C"), ("less_exposed", "较少直接曝光")):
        strata.extend(pair_row(f"{title} · {NAMES[m]}", m, result["comparisons"][panel][m]["match"])
                       for m in (a.GENERIC, a.RP, a.C_PRIOR))
    severity = [
        "", "## 合法 B/C 的保护项", "",
        "以下为 V45 减对照的每题原生字段差。各列括号内为各自共同分母。负值表示严重度下降。", "",
        "| 对照 | OPB | UPB | FM |", "|---|---:|---:|---:|",
    ]
    for method in (a.GENERIC, a.RP, a.REVIEW, a.C_PRIOR):
        fields = result["comparisons"]["contains_BC"][method]
        severity.append("| " + " | ".join([NAMES[method], *(severity_text(fields[f]) for f in ("OPB", "UPB", "FM"))]) + " |")

    n_compiled = result["witness_status"].get("COMPILED", 0)
    c_rule = audit["counts"].get(f"{a.C_PRIOR}:all", {})
    diagnostics = [
        "", "## 核验和实际差异", "",
        f"- 编译成功 {n_compiled} 道。模型提出 {ctx['proposed']} 条证据，"
        f"程序接纳 {ctx['accepted']} 条。相对同回复仅检查格式的版本，逐字引文验证实际改变 "
        f"{ctx['different_from_shape_only']} 道的成稿选择。"
        "原文核验只判定引文是否存在，作用域语义仍由模型判断。",
        f"- 相对默认 C 规则，改变 {ctx['different_from_C_prior']} 道的选择。已冻结的评分争议判别"
        f"适用于其共同评分集合。原生净差为 {c_rule.get('delta', 0):+d} 位，逐题争议上下界合计 "
        f"[{c_rule.get('min_delta', 0):+d}, {c_rule.get('max_delta', 0):+d}] 位。原生分保留。",
    ]
    for method, conditions in result["prespecified_screen"].items():
        failed = [key for key, passed in conditions.items() if not passed]
        outcome = "全部达到" if not failed else "未达到 " + "、".join(failed)
        diagnostics.append(f"- {NAMES[method]}的冻结条件{outcome}。")
    usage_pairs = cost["paired_cost_and_native_match"]
    usage = [
        "", "## 成本和账本", "",
        f"- V45 本阶段报告 {result['reported_tokens']:,} Token，未知用量 {result['unknown_usage']} 条。"
        f"传输状态为 {json.dumps(result['transport'], ensure_ascii=False)}。"
        f"结构状态为 {json.dumps(result['witness_status'], ensure_ascii=False)}。",
        f"- 独立部署成本以 {usage_pairs['common_roots']} 道同时具备原生分和用量的题比较。"
        "V45 和 V44 通用选择各需五次推理，包含 RP 的三次流程、无历史成稿和一次比较。"
        "C 规则在可用策略后只需生成一份成稿，同原 RP 均为三次推理。",
        "", "| 方法 | 部署报告 Token | 原生 Match |", "|---|---:|---:|",
        *(f"| {NAMES[m]} | {cells['totals']['total_tokens']:,} | "
          f"{usage_pairs['matched'][m]}/{usage_pairs['positions']} |"
          for m, cells in usage_pairs["cost"].items()),
        "", "[最终分数](RESULTS.json) · [题级答案选择与原分](SETTLED.json) · "
        "[选择差异与评分争议](SOURCE_AUDIT.json) · [独立成本](STANDALONE_COST.json)",
    ]
    return "\n".join(header + all_rows + strata + severity + diagnostics + usage) + "\n"


def main():
    plan, rows, ledger = a.collected()
    result = a.summarize(plan, rows, ledger)
    if result["state"] != "COMPLETE" or len(ledger) != plan["witness_request_cap"]:
        raise RuntimeError("Terminal analysis requires the complete frozen dispatch")
    source, cost = source_audit.audit(rows), cost_audit.evaluate(rows, ledger)
    out = a.run.OUT
    for name, value in (("SETTLED", {"rows": rows, "ledger": ledger}), ("RESULTS", result),
                        ("SOURCE_AUDIT", source), ("STANDALONE_COST", cost)):
        a.run.probe.freeze(out / f"{name}.json", json.loads(json.dumps(value)))
    target, text = out / "TERMINAL.md", render(result, source, cost)
    if target.exists() and target.read_text() != text:
        raise ValueError("Prior terminal Markdown differs from deterministic replay")
    if not target.exists():
        target.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
