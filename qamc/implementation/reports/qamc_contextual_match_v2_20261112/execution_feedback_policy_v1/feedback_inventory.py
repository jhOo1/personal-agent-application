"""Make an exposed, score-grounded pair inventory without overwriting any benchmark results."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
FRONTIER = BASE/"native_decision_frontier_v1/FRONTIER.json"
ENDPOINTS = BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json"
SALT = "qamc-execution-feedback-group-split-v1"
BOTH = ("TASK_ONLY","RPR_PAPER_FULL")
ANCHOR = {"rpeval":"IPE_C", "benchpres":"GEPA_SELECTED_BOUNDS", "persistbench":"PB_RUBRIC"}


def frozen_hash(*items):
    return sha256(json.dumps(items,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def pareto(x,y):
    return all(a>=b for a,b in zip(x,y,strict=True)) and any(a>b for a,b in zip(x,y,strict=True))


def compare(row):
    pair_list, counts = [], Counter()
    for (a, x), (b,y) in combinations(sorted(row["scores"].items()),2):
        if x["answer_sha256"]==y["answer_sha256"]:
            counts["same_answer"]+=1
            continue
        vx,vy = ((z["primary"],*z["protections"]) for z in (x,y))
        if not (pareto(vx,vy) or pareto(vy,vx)):
            counts["equal" if vx==vy else "tradeoff"]+=1
            continue
        if pareto(vy,vx):
            a,b,x,y,vx,vy = b,a,y,x,vy,vx
        counts["dominated"]+=1
        pair_list.append({"preferred":a,"other":b,
                          "preferred_sha256":x["answer_sha256"],"other_sha256":y["answer_sha256"],
                          "preferred_native":list(vx),"other_native":list(vy),
                          "primary_gain":vx[0]-vy[0]})
    return pair_list,counts


def same_source_endpoint_pairs():
    saved = load(ENDPOINTS)
    result = {}
    for row in saved["rows"]:
        cells = [row["scores"][m] for m in BOTH]
        if any(c["flags"]!=[] or not c["grade"].get("match") or not c["answer_sha256"] for c in cells):
            continue
        uid = row["uid"]
        stripped = {}
        for method, cell in zip(BOTH,cells,strict=True):
            g = cell["grade"]
            if any(m not in g for m in ("OPB","UPB","FM")):
                break
            stripped[method] = {"primary":g["match"]["matched"],
                                "protections":[-g[k] for k in ("OPB","UPB","FM")],"answer_sha256":cell["answer_sha256"]}
        if len(stripped)!=2:
            continue
        if any(c["grade"]["match"]["positions"]!=len(row["labels"]) for c in cells):
            raise ValueError("Two endpoints do not score the same original positions")
        result[uid] = compare({"scores":stripped})[0]
    return result


def build():
    data = load(FRONTIER)
    endpoints = same_source_endpoint_pairs()
    result = {}
    for bench,table in data["benchmarks"].items():
        rows = [r for r in table["rows"] if r["variant"] == ("exclude_known_flags" if bench=="rpeval" else "core")]
        roster = defaultdict(list)
        for row in rows:
            roster[row["group"]].append(row)
        training = {g for g in roster if int(frozen_hash(SALT,bench,g)[:8],16)%5<3}
        held = set(roster)-training
        evaluations = []
        for group in sorted(held):
            slot = min(roster[group],key=lambda r:frozen_hash(SALT,"per_group",r["uid"]))
            evaluations.append({"uid":slot["uid"],"group":group,"stratum":slot["stratum"]})
        train_count, strata, novel = Counter(), defaultdict(Counter), []
        anchors = set()
        for group in sorted(training):
            for row in roster[group]:
                pairs, count = compare(row)
                train_count.update(count)
                if not pairs:
                    continue
                chosen = min(pairs,key=lambda p:(ANCHOR[bench] not in (p["preferred"],p["other"]),
                                               p["primary_gain"]==0, frozen_hash(SALT,row["uid"],p["preferred"],p["other"])))
                if ANCHOR[bench] in (chosen["preferred"],chosen["other"]):
                    anchors.add(group)
                clean_endpoints = endpoints.get(row["uid"],[]) if bench=="rpeval" else []
                novel.append({"uid":row["uid"],"group":group,"stratum":row["stratum"],"pair":chosen,
                              "same_source_endpoint_pairs":clean_endpoints,
                              "native_positive_pairs":sum(p["primary_gain"]>0 for p in pairs)})
                strata[row["stratum"]].update(contrasts=1,primary=bool(chosen["primary_gain"]),
                                                same_endpoint_pair=bool(clean_endpoints))
        result[bench] = {"population":{"tasks":len(rows),"groups":len(roster)},
                         "training_tasks":sum(len(roster[g]) for g in training),
                         "training_groups":len(training),"evaluation_groups":len(held),
                         "training_task_pairs":len(novel),"training_pair_groups":len({r["group"] for r in novel}),
                         "groups_with_incumbent_comparison":len(anchors),
                         "groups_with_clean_fixed_endpoint_pair":len({r["group"] for r in novel if r["same_source_endpoint_pairs"]}),
                         "score_pair_counts":dict(train_count),"feedback_by_stratum":dict(strata),
                         "training_group_ids": sorted(training),"policy_evaluation_roster":evaluations,
                         "training_pairs":novel}
    return {"source_sha256":{p.name:sha256(p.read_bytes()).hexdigest() for p in (FRONTIER,ENDPOINTS)},
            "benchmarks":result,"new_requests":0,"scored_eval_feedback_read_by_induction":0}


if __name__=="__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--check",action="store_true")
    args = cli.parse_args()
    dest = HERE/"INVENTORY.json"
    result = build()
    if args.check:
        if load(dest)!=result:
            raise SystemExit("Execution-feedback corpus drift")
    else:
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print({b:{k:v for k,v in data.items() if k in ("population","training_groups","evaluation_groups",
        "training_task_pairs","training_pair_groups","groups_with_incumbent_comparison",
        "groups_with_clean_fixed_endpoint_pair")} for b,data in result["benchmarks"].items()})
