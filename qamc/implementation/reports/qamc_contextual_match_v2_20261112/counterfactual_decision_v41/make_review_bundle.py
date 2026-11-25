"""Render a self-contained V41 handoff from the frozen public and terminal evidence."""
from argparse import ArgumentParser
import csv
from io import StringIO
import json
from pathlib import Path

from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from behavior_probe import prepare
from deployment_cost import run as deployment_cost
from intervention import final_requests, task_only_request
from policy_error_lineage import collect_lineage
from run_v41 import ARMS, GATE, NATIVE, OUT, RP, baseline, formal, read
from settle_terminal import settle
from task_condition_pairs import audit_pairs
from trace_cost import samples

HERE = Path(__file__).resolve().parent
METHODS = (GATE, RP, *ARMS)
DISPLAY = dict(zip(METHODS, ("强 Gate", "归档 RP", "决策差分", "强通用复核"), strict=True))
WITNESSES = ("rpeval/formal_multi_v1/explicit/020", "rpeval/formal_multi_v1/explicit/038",
             "rpeval/formal_multi_v1/explicit/085", "rpeval/formal_multi_v1/implicit/048")


def block(value, language="json"):
    body = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return f"\n\n````{language}\n{body}\n````\n"


def score_csv(rows):
    file = StringIO(newline="")
    writer = csv.writer(file, lineterminator="\n")
    fields = ("OPB", "UPB", "RII", "FM", "VG", "full_match")
    writer.writerow(("uid", "source_group", "author_labels", "less_exposed_subset",
                     *(m + "." + k for m in METHODS for k in ("match", *fields, "answer_status"))))
    for row in rows:
        values = []
        for method in METHODS:
            scored = row["native"][method]["fields"]
            match = scored.get("match")
            status = row["answers"].get(method, {}).get("status", "ARCHIVED_OK")
            values.extend((f"{match['matched']}/{match['positions']}" if match else "",
                           *(scored.get(k, "") for k in fields), status))
        writer.writerow((row["uid"], row["group"], row["labels"], row["in_sensitivity"], *values))
    return file.getvalue()


def ledger_csv(receipts):
    file = StringIO(newline="")
    writer = csv.writer(file, lineterminator="\n")
    writer.writerow(("wave", "stage", "uid", "method", "status", "elapsed_seconds", "prompt_tokens",
                     "completion_tokens", "total_tokens", "retries", "request_sha256"))
    for row in receipts:
        unit, usage = row["unit"], row["usage"] or {}
        writer.writerow((row["wave"], row["stage"], unit["root_id"], unit["method"], row["status"],
                         row.get("elapsed_seconds"), usage.get("prompt_tokens"), usage.get("completion_tokens"),
                         usage.get("total_tokens"), row["automatic_retries"], row["request_sha256"]))
    return file.getvalue()


def abbreviated_comparisons(result):
    panel = result["primary_panel"]["pairs"]
    entries = []
    for subset, evidence in panel.items():
        for name, pair in evidence.items():
            entries.append({"stratum": subset, "pair": name, "paired_roots": pair["valid_cases"],
                            "paired_source_groups": pair["n_source_groups"],
                            "original_scores": pair["scores"],
                            "match_delta": pair.get("match_delta"),
                            "cluster_interval": pair.get("95pct_source_bootstrap"),
                            "all_frozen_score_delta_count_bounds": pair["all_frozen_delta_bounds_counts"],
                            "metrics_separate_valid_pairs": pair["separate_metric_pairs"]})
    return entries


def render(preview=False):
    result = settle()
    if not preview:
        if not result["primary_panel"]["complete"] or result != read(OUT / "TERMINAL.json"):
            raise ValueError("Release requires an exact current terminal settlement")
    plan, rows, ledger = samples()
    if len(rows) != result["primary_panel"]["completed"]:
        raise ValueError("Primary panel advanced during report build. Repeat against a stable cut.")
    roots = {root["uid"]: root for root in plan["roots"]}
    index = {row["uid"]: row for row in rows}
    pick = prepare(preflight=preview)
    if pick["completed_roots"] != len(rows):
        raise ValueError("Selected evidence belongs to another cut")
    selected = dict.fromkeys([*pick["picked"].values(), *(u for u in WITNESSES if u in index)])
    missing = next((row["uid"] for row in rows if row["trace"]["draft_status"] != "OK"), None)
    if missing is not None:
        selected[missing] = None
    anchors = {(row["uid"], row["method"]): row for row in read(formal.OUT / "RESULT_ROWS.json")
               if row["uid"] in selected and row["method"] in (GATE, RP)}
    cuts = [f"# QAMC V41 {'阶段预览' if preview else '终态方法复盘'}\n\n"
            f"已结算 {len(rows)}/{len(roots)} 个已曝光 RPEval 开发题。未读取封存集合。"
            "请从完整大面板判断机制收益。一处修复只用于归因。先区分两种复核相对归档 RP 的共同增益，"
            "以及同输入同调用配置下显式差分的增量。核对实际 Token 和合法 B/C。"
            "请提出一个能覆盖主要失分、比现有强通用复核更强的可证伪替代，并给出同题对照与停止规则。"
            "真实性和来源组重复性比增加组件重要。\n"]
    if not preview:
        cuts.append("\n" + (OUT / "TERMINAL_READOUT.md").read_text())
    common = result["common_four_arms"]["all"]
    cuts.append(f"\n四法共同有效为 {common['roots']} 道，{common['groups']} 个来源组。\n\n"
                "| 方法 | 共同原生 Match |\n|---|---:|\n"
                + "".join(f"| {DISPLAY[method]} | {common['matches'][method]}/{common['positions']} |\n"
                          for method in METHODS))
    cuts.append("\n## 预定判据及四法共同分母\n" + block(
        {"four_method_common": result["common_four_arms"], "numeric_rules": result["numeric_rules"],
         "transport_statuses": result["primary_panel"]["counts"],
         "final_contract_statuses": result["answer_status"],
         "completed_physical_requests": len(ledger),
         "total_reported_tokens": result["primary_panel"]["reported_tokens_in_completed_waves"],
         "unknown_usage": result["primary_panel"]["unknown_usage_in_completed_waves"],
         "frozen_sha256": result["frozen_sha256"], "waves": result["waves"]}))
    cuts.append("\n## 各对照配对和评分敏感性\n" + block(abbreviated_comparisons(result))
                + block(result["verified_wire_and_judge_checks"]["pairs"]) + block(result["native_label_bounds"]))
    condition = audit_pairs()
    if condition["completed_roots"] != len(rows):
        raise ValueError("Task-family replay belongs to another cut")
    for value in condition["pairs"].values():
        value.pop("task_deltas")
        value.pop("leave_one_source", None)
    cuts.append("\n## 相同任务、不同历史条件\n" + block(condition))
    lineage = collect_lineage()
    if lineage["completed_roots"] != len(rows):
        raise ValueError("Policy lineage belongs to another cut")
    cuts.append("\n## 归档前置策略错误与复核处置记录\n" + block(lineage))
    costs = deployment_cost()
    if costs["completed_roots"] != len(rows):
        raise ValueError("Costs belong to another cut")
    cuts.append("\n## 实际 Token、时延和无缓存的部署成本\n"
                + block(result["cost_and_traces"]) + block(costs))
    cuts.append("\n## 冻结规则、复核 Prompt、编译与验证\n"
                + (HERE / "EXECUTION.md").read_text()
                + block((HERE / "intervention.py").read_text(), "python"))
    for name in ("mle", "ipe", "generator"):
        path = formal.ROOT / "proposals/qamc_rpreasoner_paper" / (name + ".md")
        cuts.append(f"\n### 归档 RP {name} Prompt\n" + block(path.read_text(), "text"))
    cuts.append("\n## 跨基准证据边界\n" + (HERE / "TRANSFER_REPLAY.md").read_text())
    cuts.append("\n" + (HERE / "SCOPE_SUPPORT.md").read_text())
    for name, path in (
        ("BenchPreS 同配置论文提示对照", OUT.parent / "benchpres_matched_paper_v1" / "RESULTS.md"),
        ("PersistBench 同评分器开发对照", OUT.parent / "persist_saved_answer_alignment_v1" / "RESULTS.md"),
    ):
        cuts.append(f"\n### {name}\n" + path.read_text())
    blind_path = OUT / "behavior_diagnostic" / "SUMMARY.json"
    cuts.append("\n## 行为盲评\n" + (block(read(blind_path)) if blind_path.is_file()
                                      else "当前包无已结算的独立盲评。人工复标为 0。\n"))
    drafts = {}
    for entry in result["waves"]:
        drafts.update(read(OUT / f"wave_{entry['wave']:02d}" / "DRAFT_RESULTS.json"))
    for uid in selected:
        row, root = index[uid], roots[uid]
        draft = drafts[root["task_wire_sha256"]]["answer"]
        anchor_inputs = {m: anchors[uid, m]["actor_request"] for m in (GATE, RP)}
        for method, wire in anchor_inputs.items():
            validate_public_request(wire)
            if sha(wire) != root["archived"][method]["actor_sha256"]:
                raise ValueError("Archive receipt mismatch")
        fresh = final_requests(root, archived_draft=root["archived"][RP]["answer"], task_only_draft=draft) if draft else {}
        for arm, wire in fresh.items():
            validate_public_request(wire)
            if sha(wire) != row["trace"]["review_sha256"][arm]:
                raise ValueError("Review receipt mismatch")
        zero = task_only_request(root)
        validate_public_request(zero)
        grade, reuse = baseline.grade_jobs({"roots": [root]}, {uid: row["answers"]})
        for _, _, wire in grade:
            validate_public_request(wire)
        shared = next(iter(fresh.values()))["messages"][1]["content"] if fresh else None
        cuts.append(f"\n## 原生案例 {uid}\n" + block({
            "author_A_B_C": row["labels"], "public_task": root["public_task"],
            "source_group": root["group"], "original_memory": root["original_sources"],
            "archived_predicted_policy": root["archived_policy"], "archived_answer": {
                name: item["answer"] for name, item in root["archived"].items()},
            "archived_actor_request": anchor_inputs, "task_only_exact_request": zero,
            "task_only_draft": draft, "draft_status": row["trace"]["draft_status"],
            "shared_exact_review_user_message": shared,
            "review_system_and_controls": {arm: {**wire, "messages": wire["messages"][:1]}
                                           for arm, wire in fresh.items()},
            "final_review_request_sha256": row["trace"].get("review_sha256"),
            "answers_and_visible_application_records": row["answers"],
            "original_native_judge_fields_and_raw_scores": row["native"],
            "native_judge_requests": {arm: wire for _, arm, wire in grade},
            "native_answer_reuse": reuse[uid],
        }))
    cuts.append("\n## 全部已结算逐题分母和原始指标\n" + block(score_csv(rows), "csv"))
    cuts.append("\n## 真实请求账本\n" + block(ledger_csv(ledger), "csv"))
    return "".join(cuts), len(rows), len(selected)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    text, roots, examples = render(args.preview)
    with args.path.open("x", encoding="utf-8") as handle:
        handle.write(text)
    print(f"{roots} rows, {examples} original cases, {len(text.encode())} bytes, sha256={sha(text)}")


if __name__ == "__main__":
    main()
