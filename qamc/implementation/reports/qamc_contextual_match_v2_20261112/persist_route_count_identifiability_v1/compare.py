"""Compare observed exposure preferences inside identical router/count cells."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from inspect_answers import records
from trial import prepare, branch, sha

base = Path(__file__).resolve().parents[3] / "runs" / "qamc_contextual_match_v2_20261112"


def rows(name):
    return json.loads((base/name).read_text())["rows"]


def votes(track, narrow, group):
    if narrow is None or group is None:
        return "missing"
    def passed(score):
        return score == 3 if track == "beneficial_memory_usage" else score < 3
    delta = int(passed(group)) - int(passed(narrow))
    return {1:"group", -1:"narrow", 0:"tie"}[delta]


def panel():
    data = []
    grades = {}
    for folder in ("persist_same_actor_protection_crossjudge_v1", "persist_same_actor_syc_crossjudge_v1"):
        for r in rows(folder+"/private/RESULTS.json"):
            key = r["uid"], r["rep"]
            assert key not in grades
            grades[key] = r
    for r in rows("persist_exposure_fr3_v1/RESULTS.json"):
        if r["track"] == "beneficial_memory_usage":
            continue
        e = r["exposure"] or {}
        g = grades[r["uid"], r["repeat"]]
        data.append((r["uid"], r["repeat"], e.get("branch"), e.get("count"),
                     votes(r["track"], g["selected_g"], g["group_g"]),
                     votes(r["track"], g["selected_q"], g["group_q"])))
    _, items, _, _, _ = prepare()
    route = records("Route")
    utility = defaultdict(dict)
    for r in rows("persist_utility_fresh_deployment_v1/private/SETTLED.json"):
        utility[r["uid"]][r["arm"]] = r
    for uid, cells in utility.items():
        sel, group = cells["SELECTED"], cells["FULL"]
        item = items[uid]
        mode = branch(item["public"], route[sha(item["selection_requests"]["query"])])
        count = sel["selection_count"]
        assert count > 0
        data.append((uid, 1, mode, count, *(votes("beneficial_memory_usage", sel[j], group[j]) for j in ("GPT","Qwen"))))
    assert len(data) == 111 and len({r[0] for r in data}) == 49
    return data


def report(data, title):
    print("\n## "+title+"\n")
    print("|Branch|Count|N|GPT group/narrow/tie/missing|Qwen group/narrow/tie/missing|")
    print("|---|---:|---:|---|---|")
    buckets = defaultdict(list)
    for r in data:
        buckets[r[2:4]].append(r)
    for key, subset in sorted(buckets.items(), key=lambda item:str(item[0])):
        counts = [Counter(r[i] for r in subset) for i in (4,5)]
        cells = ["/".join(str(c[k]) for k in ("group","narrow","tie","missing")) for c in counts]
        print("|"+"|".join([str(key[0]),str(key[1]),str(len(subset)),*cells])+"|")


if __name__ == "__main__":
    data=panel()
    print("# Do identical router/count decisions require different exposures?")
    report([r for r in data if r[1]==1], "First deployment per source (49)")
    report(data, "All available deployments (111; repeated risk sources)")
    print("\n## Scored differences\n\n|Source prefix|Draw|Branch|Count|GPT|Qwen|\n|---|---:|---|---:|---|---|")
    for uid, rep, mode, count, gpt, qwen in sorted(data):
        if {gpt,qwen} & {"group","narrow"}:
            print(f"|{uid.split('/')[-1][:8]}|{rep}|{mode}|{count}|{gpt}|{qwen}|")
