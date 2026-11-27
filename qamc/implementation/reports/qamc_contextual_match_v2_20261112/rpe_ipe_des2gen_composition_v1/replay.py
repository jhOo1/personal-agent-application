"""Replace only the deployed IPE history-on endpoint with archived full Des2Gen."""
from collections import Counter, defaultdict
from pathlib import Path
import json

base = Path(__file__).resolve().parent.parent
def read(name):
    return json.loads((base / name).read_text())

rows = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
formal = read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
des = {r["uid"]: r for r in formal if r["method"] == "DES2GEN_FULL"}
stats = defaultdict(Counter)
groups = Counter()
for row in rows:
    route = row["old_route"]
    if route == "ARCHIVED_ESTIMATE_OR_ACTOR_UNAVAILABLE":
        continue
    on = route == "REUSE_RP"
    assert on or route in {"REUSE_DRAFT", "NEW_DRAFT", "REUSE_ORIGINAL_TASK_ONLY_STATE"}
    original = row["scores"]["IPE_C"]
    endpoint = row["scores"]["RPR_PAPER_FULL" if on else "TASK_ONLY"]
    if original.get("answer_sha256") and endpoint.get("answer_sha256"):
        assert original["answer_sha256"] == endpoint["answer_sha256"]
    alternative = des[row["uid"]]["native_fields"] or {}
    grades = {"IPE": original["grade"], "DES": alternative,
              "COMPOSED": alternative if on else original["grade"]}
    if any(not g.get("match") or any(g.get(k) is None for k in ("OPB","UPB","FM")) for g in grades.values()):
        continue
    n = len(row["labels"])
    assert all(g["match"]["positions"] == n for g in grades.values())
    for name in ("overall", "on" if on else "off", "C" if "C" in row["labels"] else "B_only_or_A_B" if "B" in row["labels"] else "all_A"):
        c = stats[name]
        c["tasks"] += 1
        c["positions"] += n
        for method, g in grades.items():
            hits = g["match"]["matched"]
            c[method + "_Match"] += hits
            c[method + "_Exact"] += hits == n
            for k in ("OPB","UPB","FM"):
                c[method + "_" + k] += g[k]
    groups[row["source_group"]] += grades["COMPOSED"]["match"]["matched"] - original["grade"]["match"]["matched"]
print(json.dumps(dict(allocated=len(rows), common=stats, source_group_net_vs_IPE=Counter(
    "win" if v > 0 else "loss" if v < 0 else "tie" for v in groups.values())),indent=2))
