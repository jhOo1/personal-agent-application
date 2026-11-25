"""Settle native scores and actual generation costs without making model calls."""
from argparse import ArgumentParser
from collections import Counter
import json
from statistics import median
from unittest.mock import patch

from deployment_cost import FIELDS, numeric_cost, old_cost
from qamc.common import sha

import analyze_planning as diagnostics
import audit_seed_revision
import audit_source_scope
import run_joint_planning as joint
import run_seed_control as seed

RP, GATE, RULE, REVIEW, ZERO = (
    joint.parent.comparisons.RP, joint.parent.comparisons.GATE, joint.parent.comparisons.RULE,
    joint.parent.comparisons.REVIEW, joint.parent.comparisons.ZERO,
)
NAMES = {joint.MODEL: "模型规划", joint.SOLVED: "联合求解", RP: "RP-Reasoner 重建", GATE: "强 Gate",
         RULE: "C 规则", REVIEW: "V41 强复核", ZERO: "无历史初稿", seed.edit.METHOD: "RP 成稿最小修订"}
FIELDS_NATIVE = ("OPB", "UPB", "FM", "full_match")


def checked_settlement(path, *, planner_key):
    state = joint.read(path / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError(f"Run is still {state['state']}: {path.name}")
    frozen, settled = (joint.read(path / name) for name in ("FROZEN.json", "SETTLED.json"))
    ledger, rows = settled["ledger"], settled["rows"]
    roster = frozen[planner_key]
    if not (len(rows) == len({row["uid"] for row in rows}) == frozen["assigned"]
            and {row["uid"] for row in rows} == roster.keys()):
        raise ValueError("Settled rows do not match the frozen roster")
    stage_counts = Counter(row["unit"]["stage"] for row in ledger)
    receipt_keys = {(row["unit"]["stage"], row["request_sha256"]) for row in ledger}
    if (len(ledger) != state["physical_requests"] or len(receipt_keys) != len(ledger)
            or any(count > frozen["request_caps"].get(stage, 0) for stage, count in stage_counts.items())
            or {digest for stage, digest in receipt_keys if stage == joint.PLAN} != set(roster.values())):
        raise ValueError("Settlement request accounting does not match the freeze")
    if any(row["status"] == "PENDING_DELIVERY_UNKNOWN" for row in ledger):
        raise ValueError("Pending delivery requires visible settlement first")
    return frozen, rows, ledger


def replay_readonly(module):
    """Compare the same JSON representation written by the frozen runner."""
    files = []

    def verify(path, rebuilt):
        if module.read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Replayed artifact differs after JSON serialization: {path.name}")
        files.append(path.name)

    with patch.object(module.probe, "freeze", verify):
        module.main("report")
    return files


def merge_seed(main, control):
    output = []
    for a, b in zip(main, control, strict=True):
        fields = ("uid", "group", "labels", "positions", "less_exposed")
        if any(a[k] != b[k] for k in fields):
            raise ValueError("RP revision settlement is misaligned with the joint run")
        output.append({**a, "native": {**a["native"], seed.edit.METHOD: b["native"][seed.edit.METHOD]},
                       "seed_revision": b["revision"]})
    return output


def subsets(rows, frozen):
    excluded = set(frozen["diagnostic_source_groups"])
    return {
        "all": rows,
        "outside_documented_diagnostics": [r for r in rows if r["group"] not in excluded],
        "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in rows if set(r["labels"]) & {"B", "C"}],
        "B_without_C": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
        "contains_C": [r for r in rows if "C" in r["labels"]],
    }


def score_matrix(panel, methods):
    shared_match = [row for row in panel if all(row["native"][m]["fields"].get("match") for m in methods)]
    shared = {f: [row for row in shared_match
                  if all(isinstance(row["native"][m]["fields"].get(f), (float, int)) for m in methods)]
              for f in FIELDS_NATIVE}
    outcome = {"assigned": len(panel), "common_match_cases": len(shared_match),
               "common_match_source_groups": len({row["group"] for row in shared_match}),
               "positions": sum(row["positions"] for row in shared_match),
               "common_metric_cases_on_match_intersection": {f: len(sample) for f, sample in shared.items()},
               "methods": {}}
    for method in methods:
        values = [row["native"][method]["fields"]["match"] for row in shared_match]
        if any(value["positions"] != row["positions"] or not 0 <= value["matched"] <= row["positions"]
               for row, value in zip(shared_match, values, strict=True)):
            raise ValueError("Native Match position count disagrees with the frozen rubric")
        outcome["methods"][method] = {
            "matched": sum(value["matched"] for value in values),
            **{f: (sum(row["native"][method]["fields"][f] for row in sample) / len(sample) if sample else None)
               for f, sample in shared.items()},
        }
    return outcome


def seed_against_archives(panels):
    revised = seed.edit.METHOD
    return {
        name: {
            control: {"match": joint.v42.paired(sample, control, revised),
                      **{field: joint.parent.comparisons.grade_pair(sample, control, revised, field)
                         for field in FIELDS_NATIVE}}
            for control in (RP, GATE, REVIEW, RULE)
        } for name, sample in panels.items()
    }


def metadata_recovery_ceiling(rows, recovery):
    """Give only the metadata-recoverable rows hypothetical perfect Match."""
    recovered = {"cases": 0, "positions": 0, "additional_net_matches_at_most": 0}
    observed = {"cases": 0, "positions": 0, "net_matches": 0}
    for row in rows:
        base = row["native"][RP]["fields"].get("match")
        revised = row["native"][seed.edit.METHOD]["fields"].get("match")
        if not base:
            continue
        if revised:
            observed["cases"] += 1
            observed["positions"] += row["positions"]
            observed["net_matches"] += revised["matched"] - base["matched"]
        elif recovery.get(row["uid"]) == "APPLIED":
            recovered["cases"] += 1
            recovered["positions"] += row["positions"]
            recovered["additional_net_matches_at_most"] += row["positions"] - base["matched"]
    return {"observed": observed, "hypothetical": recovered,
            "net_matches_at_most": observed["net_matches"] + recovered["additional_net_matches_at_most"]}


def generation_costs(rows, main_ledger, seed_ledger):
    def index(ledger):
        return {(rec["unit"]["stage"], rec["request_sha256"]): rec for rec in ledger}

    def cost(records, stage, digest):
        rec = records.get((stage, digest))
        return numeric_cost(rec["usage"]) if rec is not None and rec["status"] == "OK" else None

    main, control = index(main_ledger), index(seed_ledger)
    original = joint.read(joint.prior.formal.OUT / "PLAN.json")
    roots = {row["uid"]: row for row in joint.read(joint.prior.OUT / "FROZEN.json")["roots"]}
    methods = [joint.MODEL, RP, GATE] + ([seed.edit.METHOD] if seed_ledger else [])
    recorded = {method: [] for method in methods}
    direct_seed = []
    for row in rows:
        root = roots[row["uid"]]
        rp_cost = old_cost(original, root, RP)
        if seed_ledger:
            revision = cost(control, seed.PLAN, row["seed_revision"].get("request_sha256"))
            if (rp_cost is not None and revision is not None
                    and all(row["native"][method]["fields"].get("match") for method in (RP, seed.edit.METHOD))):
                direct_seed.append((row["group"], rp_cost, rp_cost + revision))
        if not row["native"][joint.SOLVED]["fields"].get("match"):
            continue
        allocated = cost(main, joint.PLAN, row["planning"].get("request_sha256"))
        if allocated is None:
            continue
        amounts = {}
        for method in (joint.MODEL, joint.SOLVED):
            reply = row["actors"][method]
            actor = cost(main, joint.ACTOR, reply.get("request_sha256"))
            amounts[method] = allocated + actor if actor is not None else None
        amounts.update({RP: rp_cost, GATE: old_cost(original, root, GATE)})
        if seed_ledger:
            amounts[seed.edit.METHOD] = amounts[RP] + revision if revision is not None and amounts[RP] is not None else None
        for method in methods:
            scores = [row["native"][side]["fields"].get("match") for side in (method, joint.SOLVED)]
            if all(value is not None for value in (amounts[method], amounts[joint.SOLVED], *scores)):
                recorded[method].append((row["group"], amounts[method], amounts[joint.SOLVED]))
    def summarize(cells, left, right):
        return {
            "cases": len(cells), "source_groups": len({cell[0] for cell in cells}),
            "costs": {side: {"totals": {f: sum(row[i][f] for row in cells) for f in FIELDS},
                             "median_total": median(row[i]["total_tokens"] for row in cells) if cells else None}
                      for i, side in enumerate((left, right), 1)},
        }

    return {**{method: summarize(cells, method, joint.SOLVED) for method, cells in recorded.items()},
            "RP_vs_RP_seed_revision": summarize(direct_seed, RP, seed.edit.METHOD)}


def usage(ledger):
    parsed = [numeric_cost(record["usage"]) for record in ledger]
    failures = Counter((r["unit"]["stage"], r["status"], r.get("error"), r.get("http_status"))
                       for r in ledger if r["status"] != "OK")
    return {"requests": len(ledger), "stage_counts": Counter(r["unit"]["stage"] for r in ledger),
            "transport_states": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "missing_any_token_field": sum(value is None for value in parsed),
            "automatic_retries": sum(r.get("automatic_retries") or 0 for r in ledger),
            "failures": [{"stage": stage, "status": status, "error": error, "http_status": code, "requests": count}
                         for (stage, status, error, code), count in failures.items()]}


def settle():
    frozen, rows, ledger = checked_settlement(joint.OUT, planner_key="planner_wires_sha256")
    results = joint.read(joint.OUT / "RESULTS.json")
    if json.loads(json.dumps(joint.report(frozen, rows, ledger))) != results:
        raise ValueError("Native results differ from the frozen report replay")
    _, controls, revision_ledger = checked_settlement(seed.OUT, planner_key="wire_sha256")
    rows = merge_seed(rows, controls)
    methods = (joint.SOLVED, joint.MODEL, RP, seed.edit.METHOD, GATE, REVIEW, RULE, ZERO)
    panels = subsets(rows, frozen)
    edit_audit = audit_seed_revision.audit()
    return {
        "assigned": len(rows), "independent_confirmation": frozen["independent_confirmation"],
        "artefact_sha256": {path.name: sha((path / "SETTLED.json").read_bytes()) for path in (joint.OUT, seed.OUT)},
        "common_native_tables": {name: score_matrix(sample, methods) for name, sample in panels.items()},
        "frozen_primary_pairs": results["metrics"], "frozen_screen": results["screen"],
        "against_rp_seed_minimal_revision": diagnostics.seed_comparison(rows),
        "rp_seed_revision_against_archives": seed_against_archives(panels),
        "rp_seed_edit_audit": edit_audit,
        "rp_seed_metadata_recovery_ceiling": metadata_recovery_ceiling(
            controls, edit_audit["task_only_role_metadata_replay"]["per_case"]),
        "answer_metrics_by_intervention": diagnostics.answer_summary(rows),
        "source_scope_audit": audit_source_scope.audit(),
        "physical_usage": {"joint": usage(ledger), "rp_seed_revision": usage(revision_ledger)},
        "deployment_cost_without_judges": generation_costs(rows, ledger, revision_ledger),
        "rp_seed_revision_status": Counter(row["seed_revision"]["status"] for row in rows),
        "interpretation": "All native comparisons are development results on frozen exposed sources. "
                          "Physical costs count each new receipt once; deployment adds logical generation stages.",
    }


def format_number(value):
    return "—" if value is None else f"{value:.3f}"


def markdown(results):
    text = ["# 联合规划与 RP 最小修订结果", "",
            "全部为已曝光开发题。每个分层使用该表所有方法共同有效的 Match 题。"
            "误用、漏用、可行性和整题指标另取该交集内各自的完整回执。", ""]
    panel_names = {"all": "全部", "outside_documented_diagnostics": "排除既有诊断来源",
                   "all_A": "全 A", "contains_BC": "含 B/C", "B_without_C": "有 B 无 C", "contains_C": "含 C"}
    for key, data in results["common_native_tables"].items():
        cases = data["common_metric_cases_on_match_intersection"]
        text.extend([f"## {panel_names[key]}", "",
                     f"共同 Match 题 {data['common_match_cases']}/{data['assigned']}，"
                     f"来源组 {data['common_match_source_groups']}。"
                     f"OPB、UPB、FM、整题指标有效题分别为 {cases['OPB']}、{cases['UPB']}、"
                     f"{cases['FM']}、{cases['full_match']}。", "",
                     "| 方法 | Match | OPB | UPB | FM | 整题匹配比例 |",
                     "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for method, values in data["methods"].items():
            cells = [NAMES[method], f"{values['matched']}/{data['positions']}",
                     *(format_number(values[field]) for field in FIELDS_NATIVE)]
            text.append("| " + " | ".join(cells) + " |")
        text.append("")
    text.extend(["## 所有共同评分可用题上的配对差值", "",
                 "| 对照 | 同题 | 联合求解减对照 Match（百分点） | 95% 来源组区间 |",
                 "| --- | ---: | ---: | ---: |"])
    pairs = {method: cells["match"] for method, cells in results["frozen_primary_pairs"]["all"].items()}
    pairs[seed.edit.METHOD] = results["against_rp_seed_minimal_revision"]["all"]["match"]
    for method, pair in pairs.items():
        delta = f"{100 * pair['match_delta']:+.2f}" if "match_delta" in pair else "—"
        lo, hi = pair.get("95pct_source_bootstrap", (None, None))
        interval = f"[{100 * lo:+.2f}, {100 * hi:+.2f}]" if lo is not None else "—"
        text.append(f"| {NAMES[method]} | {pair['valid_cases']} | {delta} | {interval} |")
    text.extend(["", "## RP 修订与归档对照", "",
                 "每行的 Match 和保护指标各自使用共同有效数据。保护指标括号内为对应题数。", "",
                 "| 对照 | Match 同题 | RP 修订减对照百分点 | 95% 来源组区间 | OPB 差 | UPB 差 | FM 差 |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for method, metrics in results["rp_seed_revision_against_archives"]["all"].items():
        pair = metrics["match"]
        delta = f"{100 * pair['match_delta']:+.2f}" if "match_delta" in pair else "—"
        lo, hi = pair.get("95pct_source_bootstrap", (None, None))
        interval = f"[{100 * lo:+.2f}, {100 * hi:+.2f}]" if lo is not None else "—"
        protects = [f"{metrics[field]['delta']:+.3f} ({metrics[field]['n']})"
                    if "delta" in metrics[field] else "—" for field in ("OPB", "UPB", "FM")]
        text.append("| " + " | ".join([NAMES[method], str(pair["valid_cases"]), delta, interval, *protects]) + " |")
    text.extend(["", "## 实际请求", "",
                 "| 实验 | 新请求 | 报告 Token | 存在未知用量字段 |",
                 "| --- | ---: | ---: | ---: |"])
    for key, label in (("joint", "联合规划及同计算控制"), ("rp_seed_revision", "RP 成稿修订")):
        data = results["physical_usage"][key]
        text.append(f"| {label} | {data['requests']} | {data['reported_tokens']:,} | {data['missing_any_token_field']} |")
    text.extend(["", "### 未成功的物理请求", "",
                 "| 实验 | 阶段 | 账本状态 | 错误 | HTTP | 请求数 |",
                 "| --- | --- | --- | --- | ---: | ---: |"])
    for key, label in (("joint", "联合规划及同计算控制"), ("rp_seed_revision", "RP 成稿修订")):
        for row in results["physical_usage"][key]["failures"]:
            values = [label, row["stage"], row["status"], row["error"] or "—",
                      str(row["http_status"] or "—"), str(row["requests"])]
            text.append("| " + " | ".join(str(value).replace("|", r"\|") for value in values) + " |")
    retries = sum(data["automatic_retries"] for data in results["physical_usage"].values())
    text.extend(["", f"两项实验共记录 {retries} 次自动重发。配对评分的分母见上表。"])
    return "\n".join(text) + "\n"


if __name__ == "__main__":
    options = ArgumentParser(description=__doc__)
    mode = options.add_mutually_exclusive_group()
    mode.add_argument("--markdown", action="store_true")
    mode.add_argument("--verify-primary", action="store_true")
    mode.add_argument("--verify-seed", action="store_true")
    args = options.parse_args()
    if args.verify_primary or args.verify_seed:
        module = joint if args.verify_primary else seed
        print(json.dumps({"verified": replay_readonly(module), "live_requests": 0}, ensure_ascii=False, indent=2))
    else:
        result = settle()
        print(markdown(result) if args.markdown else json.dumps(result, ensure_ascii=False, indent=2))
