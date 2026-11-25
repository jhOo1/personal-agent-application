"""Rejoin native development scores and locate unsolved common-score opportunities."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from qamc.common import sha
from ipe_missing_bound import verified_comparison

ROOT = Path(__file__).resolve().parent.parent
GATE, RP, IPE, RUBRIC = "GEPA_SELECTED_BOUNDS", "RPR_PAPER_FULL", "IPE_C", "PB_RUBRIC"
C5, PAPER, GEPA, ZERO = "GOAL_EFFECT_GEPA", "PAPER_SELECTIVITY", "PB_GEPA", "PB_NO_MEMORY"
RPE_PATH = "selective_path_frontier_v1/RESULTS.json"
PERSIST_PATH = "selective_path_frontier_v1/PERSIST_OPPONENTS.json"
BENCH_PAPER = "benchpres_matched_paper_v1/RESULT_ROWS.json"
PERSIST_PLAN = "persist_author_controls_v2/PLAN.json"


def read(path):
    return json.loads((ROOT / path).read_text())


def rpeval():
    result = defaultdict(list)
    for row in read(RPE_PATH)["rows"]:
        arms = {name: row["cells"].get(name) for name in (GATE, RP)}
        arms[IPE] = row["cells"].get(row["base"])
        if any(not cell or cell.get("matched") is None for cell in arms.values()):
            continue
        losses = {arm: row["positions"] - cell["matched"] for arm, cell in arms.items()}
        result[row["stratum"]].append({
            "uid": row["uid"], "group": row["source_group"], "positions": row["positions"],
            "shortfall": losses, "best_archive_shortfall": min(losses.values()),
            "judge_flags": {arm: cell["flags"] for arm, cell in arms.items() if cell["flags"]},
            "answer_hashes": {arm: cell["answer_sha256"] for arm, cell in arms.items()},
        })
    summary = {}
    for block, rows in result.items():
        common_fail = [r for r in rows if r["best_archive_shortfall"] > 0]
        clean = [r for r in common_fail if not r["judge_flags"]]
        summary[block] = {"roots": len(rows), "positions": sum(r["positions"] for r in rows),
                          "common_fail_roots": len(common_fail), "common_fail_groups": len({r["group"] for r in common_fail}),
                          "best_archive_shortfall": sum(r["best_archive_shortfall"] for r in common_fail),
                          "no_known_flag_roots": len(clean), "no_known_flag_groups": len({r["group"] for r in clean}),
                          "shortfall": {m: sum(r["shortfall"][m] for r in rows) for m in (IPE, RP, GATE)}}
    return {"summary": summary, "per_case": dict(result)}


def benchpres():
    data = verified_comparison()
    scores = dict(data["scores"])
    paper_rows = {r["uid"]: r for r in read(BENCH_PAPER)
                  if r["actor_status"] == "OK" and r["score"] is not None and r["method"] == PAPER}
    scores.update({(uid, PAPER): row["score"] for uid, row in paper_rows.items()})
    arms = (IPE, RP, GATE, C5, PAPER)
    strongest = (GATE, C5, PAPER)
    counts, clusters, hotspots = defaultdict(Counter), defaultdict(set), []
    all_arm_roots = []
    for uid, case in data["cases"].items():
        if not all((uid, method) in scores for method in arms):
            continue
        group = case["analysis_group_id"]
        all_arm_roots.append(uid)
        attributes = (scores[uid, method]["decisions"] for method in arms)
        for index, decisions in enumerate(zip(*attributes, strict=True)):
            pref, relevant = decisions[0]["preference"], decisions[0]["appropriate"]
            if any((d["preference"], d["appropriate"]) != (pref, relevant) for d in decisions):
                raise ValueError(f"Preference alignment changed: {uid}/{index}")
            applied = {m: d["label"] == "follow" for m, d in zip(arms, decisions, strict=True)}
            fail = {m: used != relevant for m, used in applied.items()}
            kind = "bold" if re.search(r"\bbold\s+text\b", pref, re.I) else "other"
            key = f"{'AAR' if relevant else 'MR'}/{kind}"
            counts[key].update(denominator=1, **{m: int(v) for m, v in fail.items()})
            if all(fail[m] for m in strongest):
                counts[key]["strong_common_fail"] += 1
                clusters[key].add(group)
                hotspots.append({"uid": uid, "group": group, "index": index, "kind": key,
                                 "source_text_sha256": sha(pref), "all_wrong": all(fail.values())})
            if fail[IPE] and not fail[GATE]:
                counts[key]["only_ipe_vs_gate"] += 1
    return {"common_roots": len(all_arm_roots), "classes": {k: {**v, "strong_common_fail_groups": len(clusters[k])}
                                                          for k, v in counts.items()},
            "strong_common_flags": hotspots, "all_arm_uids": all_arm_roots}


def persistbench():
    plan = read(PERSIST_PLAN)
    if plan["not_confirmation"] is not True or plan["new_samples"] != 0:
        raise ValueError("Expected the original development-only author panel")
    groups = {r["uid"]: r["group_id"] for r in plan["cases"] if r["benchmark"].lower() == "persistbench"}
    controls = {k: (RUBRIC, GEPA, GATE) for k in ("cross_domain", "sycophancy", "beneficial_memory_usage")}
    result = {}
    for row in read(PERSIST_PATH)["rows"]:
        cat = row["category"]
        field = "failure_strict_utility" if cat == "beneficial_memory_usage" else "failure_release"
        target = row["ipe_arm"]
        arms = dict(row["cells"])
        arms[IPE] = arms[target]
        if not all(m in arms for m in (*controls[cat], IPE)):
            continue
        sums = result.setdefault(cat, {"field": field, "per_case": []})
        status = {m: arms[m][field] for m in (*controls[cat], IPE)}
        public_only = arms.get(ZERO, {}).get(field)
        sums["per_case"].append({"uid": row["uid"], "group": groups[row["uid"]], "failure": status,
                                 "public_only_fail": public_only,
                                 "public_only_answer_hash": arms.get(ZERO, {}).get("answer_sha256"),
                                 "strong_common_fail": all(status[m] for m in controls[cat]),
                                 "answer_hashes": {m: arms[m]["answer_sha256"] for m in status}})
    for cat, table in result.items():
        rows = table["per_case"]
        table["roots"] = len(rows)
        table["groups"] = len({r["group"] for r in rows})
        table["failures"] = dict(Counter({m: sum(r["failure"][m] for r in rows)
                                         for m in (*controls[cat], IPE)}))
        joint = [r for r in rows if r["strong_common_fail"]]
        table["strong_common_fail_roots"] = len(joint)
        table["strong_common_fail_groups"] = len({r["group"] for r in joint})
        table["public_only_already_passes"] = sum(r["public_only_fail"] is False for r in joint)
    return result


def inventory():
    return {"rpeval": rpeval(), "benchpres": benchpres(), "persistbench": persistbench(),
            "source_file_sha256": {p: sha((ROOT / p).read_bytes())
                                   for p in (RPE_PATH, PERSIST_PATH, BENCH_PAPER, PERSIST_PLAN)},
            "new_requests": 0, "score_changes": 0}


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, indent=2, sort_keys=True))
