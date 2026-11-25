"""Measure exact IPE-C routing lift at the same memory exposure rate."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from random import Random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FULL, ZERO = "RPR_PAPER_FULL", "TASK_ONLY"
METRICS = ("Match", "OPB", "UPB", "FM")
DRAWS = 10000
SALT = "qamc-fixed-rate-controls-v1"


def read(path):
    return json.loads(path.read_text())


def load():
    files = {
        "scores": ROOT / "selective_path_frontier_v1/RESULTS.json",
        "choice": ROOT / "rp_estimator_routing_replay_v1/RESULTS.json",
        "task": ROOT / "counterfactual_rpeval_v41/FROZEN.json",
        "cohort": ROOT / "rpeval_formal_multi_coverage_v1/PLAN.json",
    }
    docs = {k: read(v) for k, v in files.items()}
    if docs["task"]["independent_confirmation"]:
        raise ValueError("Expected exposed prior cohort")
    routes = {r["uid"]: r["keep_rp"]["IPE_C"] for r in docs["choice"]["rows"]}
    task = {r["uid"]: r for r in docs["task"]["roots"]}
    cohort = {r["uid"]: r for r in docs["cohort"]["cases"] if r["independent_confirmation"] is False}
    rows = sorted(docs["scores"]["rows"], key=lambda r: r["uid"])
    if len(rows) != 216 or len({r["uid"] for r in rows}) != len(rows):
        raise ValueError("Common panel changed")
    for r in rows:
        uid = r["uid"]
        labels = {m: r["cells"][m] for m in (FULL, ZERO)}
        if r["base"] != (FULL if routes[uid] else ZERO) or task[uid]["group"] != r["source_group"]:
            raise ValueError("Route or source group mismatch")
        source_count = len(task[uid]["original_sources"])
        if source_count != r["positions"] or not all(c and c["matched"] <= source_count for c in labels.values()):
            raise ValueError("Endpoints do not share the assigned source count")
        r.update(track=cohort[uid]["track"], count=source_count, wire=task[uid]["task_wire_sha256"],
                 clean=not any(c["flags"] for c in labels.values()))
    return rows, {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in files.items()}


def score(row, endpoint, metric):
    if metric == "Match":
        return row["cells"][endpoint]["matched"]
    return row["cells"][endpoint]["fields"].get(metric)


def sum_scores(rows, selection):
    card = {}
    for q in METRICS:
        usable = [r for r in rows if all(score(r, m, q) is not None for m in (ZERO, FULL))]
        card[q] = {"total": sum(score(r, selection(r), q) for r in usable), "tasks": len(usable)}
    return card


def blocks(rows, key):
    buckets = defaultdict(list)
    for i, row in enumerate(rows):
        buckets[key(row)].append(i)
    return list(buckets.values())


def stat(draws, observed, larger):
    values = sorted(draws)
    n = len(values)
    return {"mean": sum(values) / n, "p025": values[int(n*.025)], "p975": values[int(n*.975)-1],
            "at_least_as_good_fraction": sum((x >= observed if larger else x <= observed) for x in values) / n}


def audit_control(rows, groups, subsets, salt):
    rng = Random(SALT + salt)
    settings = []
    references = {scope: sum_scores([rows[i] for i in indices], lambda r: r["base"])
                  for scope, indices in subsets.items()}
    for scope, indices in subsets.items():
        for metric in METRICS:
            values = [(i, score(rows[i], ZERO, metric), score(rows[i], FULL, metric)) for i in indices]
            common = [(i, z, f) for i,z,f in values if z is not None and f is not None]
            settings.append((scope, metric, sum(z for i,z,f in common), [(i,f-z) for i,z,f in common], []))
    each = [(group, sum(rows[i]["base"] == FULL for i in group)) for group in groups]
    chosen_count = sum(n for _, n in each)
    mixed = {i for g,n in each if 0<n<len(g) for i in g}
    if salt == "exact_public_task":
        for metric in METRICS:
            values = [(i,score(rows[i],ZERO,metric),score(rows[i],FULL,metric)) for i in sorted(mixed)]
            common = [(i,z,f) for i,z,f in values if z is not None and f is not None]
            settings.append(("mixed_only", metric, sum(z for i,z,f in common), [(i,f-z) for i,z,f in common], []))
        references["mixed_only"] = sum_scores([rows[i] for i in sorted(mixed)],lambda r:r["base"])
    fixed_full = [i for g,n in each if n==len(g) for i in g]
    variable = [(g,n) for g,n in each if 0<n<len(g)]
    for _ in range(DRAWS):
        choice = set(fixed_full)
        for group,n in variable:
            choice.update(rng.sample(group,n))
        if len(choice)!=chosen_count:
            raise ValueError("History inclusion rate drift")
        for _, _, z, deltas, sample in settings:
            sample.append(z + sum(d for i,d in deltas if i in choice))
    result = {}
    for scope, metric, _, _, sample in settings:
        obs = references[scope][metric]
        result.setdefault(scope,{})[metric] = {**stat(sample, obs["total"], metric=="Match"),
                                               "ipe_c": obs["total"], "tasks": obs["tasks"]}
    return {"blocks": len(groups), "mixed_blocks": len(variable), "mixed_tasks": len(mixed),
            "mixed_positions": sum(rows[i]["positions"] for i in mixed), "full_choices": chosen_count,
            "by_scope": result}


def build():
    rows, hashes = load()
    scopes = {"all": list(range(len(rows)))}
    for k in ("all_A","B_only","contains_C"):
        scopes[k] = [i for i,r in enumerate(rows) if r["stratum"] == k]
    scopes["flag_excluded"] = [i for i,r in enumerate(rows) if r["clean"]]
    existing = {}
    for key,ids in scopes.items():
        cells = [rows[i] for i in ids]
        existing[key] = {"positions": sum(r["positions"] for r in cells),
                         "groups": len({r["source_group"] for r in cells}),
                         "policies": {"IPE_C": sum_scores(cells, lambda r:r["base"]),
                                      FULL: sum_scores(cells, lambda r:FULL),
                                      ZERO: sum_scores(cells, lambda r:ZERO)}}
    if existing["all"]["policies"]["IPE_C"]["Match"] != {"total":765,"tasks":216}:
        raise ValueError("Observed route reference does not match prior calculation")
    controls = {"global": lambda r: None, "track_source_count": lambda r:(r["track"],r["count"]),
                "exact_public_task": lambda r:r["wire"]}
    return {"inputs": hashes, "draws_per_control": DRAWS, "salt": SALT, "actual": existing,
            "controls": {name: audit_control(rows, blocks(rows,key),scopes,name) for name,key in controls.items()},
            "new_model_requests": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    output = HERE / "RESULTS.json"
    data = build()
    if parser.parse_args().check:
        if read(output) != data:
            raise SystemExit("Sensitivity result drifted")
    else:
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print({name: r["by_scope"]["all"]["Match"] for name,r in data["controls"].items()})
