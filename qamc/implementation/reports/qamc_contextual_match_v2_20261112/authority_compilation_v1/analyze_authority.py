"""Summarize paired scores without model calls or changes to historical grades."""
from collections import Counter
import json
from pathlib import Path

from qamc.common import ROOT, parse_object, sha
from qamc.contextual_match.rpeval_author_aggregation import replay

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GATE, RP, IPE = "GEPA_SELECTED_BOUNDS", "RPR_PAPER_FULL", "IPE_C"
ARMS = ("GENERIC", "AUTHORITY")
METRICS = ("match", "full_match", "OPB", "UPB", "FM")
AUTHOR = ROOT / "literature/qamc_pa_v1/RPEval/generation_task/eval_multi.py"


def read(path):
    return json.loads(path.read_text())


def rpe_tables(rows, strata):
    by_uid = {(r["uid"], r["method"]): r for r in rows}
    prior = {row["uid"]: row for row in read(BASE / "selective_path_frontier_v1/RESULTS.json")["rows"]}
    archived = {row["uid"]: row for row in read(BASE / "counterfactual_rpeval_v41/FROZEN.json")["roots"]}
    task_only = {row["uid"]: row for row in read(BASE / "counterfactual_rpeval_v41_task_only/RESULTS.json")["roots"]}

    def value(uid, arm, metric):
        if arm in ARMS:
            score = by_uid[uid, arm]["score"] or {}
            return score.get(metric)
        ref = prior[uid]
        cell = ref["cells"].get(ref["base"] if arm == IPE else arm)
        if cell is None:
            return None
        if metric == "match":
            return {"matched": cell["matched"], "positions": ref["positions"]}
        if metric == "full_match":
            return int(cell["matched"] == ref["positions"])
        return cell["fields"].get(metric)

    def raw(uid, arm):
        if arm in ARMS:
            return by_uid[uid, arm]["judge"]["answer"]
        name = prior[uid]["base"] if arm == IPE else arm
        return (task_only[uid]["task_only"]["raw"] if name == "TASK_ONLY"
                else archived[uid]["archived"][name]["raw_judge"])

    tables = {}
    for subset in ("all", "all_A", "B_only"):
        chosen = sorted(uid for uid, stratum in strata.items() if subset in ("all", stratum))
        tables[subset] = {}
        for rival in ("GENERIC", GATE, RP, IPE):
            arms = (rival, "AUTHORITY")
            result = {}
            for metric in METRICS:
                observations = [(uid, [value(uid, arm, metric) for arm in arms]) for uid in chosen]
                common = [(uid, both) for uid, both in observations if None not in both]
                scores = [both for _, both in common]
                if metric == "match":
                    values = {arm: [sum(row[i][key] for row in scores) for key in ("matched", "positions")]
                              for i, arm in enumerate(arms)}
                    result["author_aggregation"] = {arm: replay(AUTHOR, [
                        {"uid": uid, "judge_result": parse_object(raw(uid, arm))}
                        for uid, _ in common], True)["author_summary"] for arm in arms} if common else {}
                else:
                    values = {arm: sum(row[i] for row in scores) for i, arm in enumerate(arms)}
                result[metric] = {"uids": [uid for uid, _ in common], "values": values}
            tables[subset][rival] = result
    return tables


def summary():
    result = read(HERE / "RESULTS.json")
    panel = {cell["uid"]: cell for cell in read(HERE / "FROZEN.json")["panel"]}
    by_uid = {(r["uid"], r["method"]): r for r in result["rows"]}
    if len(by_uid) != 2 * len(panel):
        raise ValueError("Missing frozen answer slots")
    status = Counter()
    answer_checks = []
    for uid, cell in panel.items():
        for arm in ARMS:
            row = by_uid[uid, arm]
            status[f"{cell['benchmark']}/{arm}/{row['actor_status']}"] += 1
        authority = by_uid[uid, "AUTHORITY"]
        answer = authority["answer"]
        generic = by_uid[uid, "GENERIC"]["answer"]
        public = result["public"].get(uid)
        operations = json.loads(authority["raw_personal_response"]) if answer else None
        answer_checks.append({
            "uid": uid, "benchmark": cell["benchmark"], "stratum": cell["stratum"],
            "fixed_passages": sum(block["kind"] == "fixed" for block in public["blocks"]) if public else None,
            "available_decision_slots": sum(block["kind"] == "decision" for block in public["blocks"]) if public else None,
            "decisions": [op["id"] for op in operations["decisions"]] if operations is not None else None,
            "emphasis": [op["id"] for op in operations["emphasis"]] if operations is not None else None,
            "changed_public_draft": answer != "\n\n".join(block["text"] for block in public["blocks"])
            if answer and public else None,
            "same_answer": answer == generic if answer and generic else None,
            "answer_hashes": {arm: sha(by_uid[uid, arm]["answer"]) if by_uid[uid, arm]["answer"] else None
                              for arm in ARMS},
        })
    rpe = {uid: cell["stratum"] for uid, cell in panel.items() if cell["benchmark"] == "RPEval"}
    return {
        "rpeval": rpe_tables(result["rows"], rpe), **result["comparisons"], "answer_checks": answer_checks,
        "actor_status": status, "requests": result["request_counts"], "reported_tokens": result["reported_tokens"],
        "unknown_usage": result["unknown_usage"],
        "transport_status": Counter(r["status"] for r in result["ledger"]),
        "usage_by_stage": {
            stage: {"known_tokens": sum((r["usage"] or {}).get("total_tokens") or 0
                                         for r in result["ledger"] if r["unit"]["stage"] == stage),
                    "unknown": sum("total_tokens" not in (r["usage"] or {})
                                   for r in result["ledger"] if r["unit"]["stage"] == stage)}
            for stage in result["request_counts"]
        },
        "independent_confirmation": False,
    }


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2, ensure_ascii=False))
