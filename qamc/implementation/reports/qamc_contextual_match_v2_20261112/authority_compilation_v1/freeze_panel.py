"""Select the development comparison by public lineage and fixed hash, without scores."""
import json
from pathlib import Path

from qamc.common import sha

from authority import public_wire
from preflight import public_roots

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SEED = "qamc-authority-compilation-v1"


def read(relative):
    return json.loads((BASE / relative).read_text())


def rank(value):
    return sha([SEED, value])


def representatives(rows, group_key, count):
    result = {}
    for row in sorted(rows, key=lambda row: rank(row["uid"])):
        result.setdefault(row[group_key], row)
    if len(result) < count:
        raise ValueError("Insufficient independent development roots")
    return list(result.values())[:count]


def freeze():
    roots = {root["uid"]: (name, root) for name, root in public_roots()}
    rows = []
    bench = read("benchpres_matched_paper_v1/PLAN.json")["cases"]
    bench = [r for r in bench if r["uid"] in roots and r["independent_confirmation"] is False]
    for case in representatives(bench, "analysis_group_id", 4):
        rows.append((case["uid"], case["analysis_group_id"], "BenchPreS"))
    persist = read("persist_author_controls_v2/PLAN.json")["cases"]
    allowed = [r for r in persist if r["uid"] in roots and r["role"] == "DEV"]
    for category in ("sycophancy", "beneficial_memory_usage"):
        group = [r for r in allowed if r["category"] == category]
        for case in representatives(group, "group_id", 4):
            rows.append((case["uid"], case["group_id"], category))
    pairs = read("paired_behavior_icl_v1/FROZEN.json")["pairs"]
    pairs = [p for p in pairs if all(r["uid"] in roots for r in p["roots"])]
    pairs = [p for p in pairs if len({
        roots[r["uid"]][1]["public_task"]["query"] for r in p["roots"]
    }) == 1]
    if len(pairs) < 2:
        raise ValueError("Fewer than two exact-query RPEval pairs")
    for pair in sorted(pairs, key=lambda p: rank(p["group"]))[:2]:
        for case in pair["roots"]:
            rows.append((case["uid"], pair["group"], case["stratum"]))
    panel = []
    for uid, group, stratum in rows:
        name, root = roots[uid]
        panel.append({"benchmark": name, "uid": uid, "source_group": group, "stratum": stratum,
                      "public_wire_sha256": sha(public_wire(root)),
                      "source_evidence_sha256": sha(root["original_sources"]),
                      "archived_actor_sha256": root["archived_actor_sha256"]})
    if len({r["uid"] for r in panel}) != 16 or len({r["source_group"] for r in panel}) != 14:
        raise ValueError("Unexpected development panel")
    return {"panel": panel, "seed": SEED, "independent_confirmation": False,
            "max_generation_requests": 48, "max_grading_requests": 72,
            "implementation_sha256": {path.name: sha(path.read_text()) for path in (
                HERE / "authority.py", HERE / "freeze_panel.py")},
            "model_calls_to_freeze": 0}


if __name__ == "__main__":
    print(json.dumps(freeze(), ensure_ascii=False, indent=2))
