"""Read only the formal multi development panel and match original saved endpoints."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

base = Path(__file__).resolve().parent.parent
def load(name):
    return json.loads((base / name).read_text())

rows = load("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
rp = {r["uid"]: r for r in load("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
      if r["method"] == "RPR_PAPER_FULL"}
counts = Counter()
groups = defaultdict(Counter)
cases = []
for row in rows:
    uid = row["uid"]
    wire = rp[uid].get("actor_request")
    if not wire:
        counts["missing_wire"] += 1
        continue
    body = json.loads(wire["messages"][-1]["content"])
    policy = body["preference_use_policy"]
    ids = [p["memory_id"] for p in policy]
    assert len(set(ids)) == len(ids) and ids == [s["memory_id"] for s in body["source_evidence"]]
    assert all(p["policy"] in ("A", "B", "C") for p in policy)
    counts["valid_wires"] += 1
    if sum(p["policy"] != "A" for p in policy) != 1:
        continue
    counts["eligible"] += 1
    retained = row["old_route"] == "REUSE_RP"
    counts["eligible_on" if retained else "eligible_other"] += 1
    endpoints = [row["scores"].get(k) or {} for k in ("RPR_PAPER_FULL", "TASK_ONLY")]
    grades = [(end.get("grade") or {}).get("match") for end in endpoints]
    if not all(grades):
        continue
    assert rp[uid]["native_fields"]["match"] == grades[0]
    assert hashlib.sha256(rp[uid]["answer"].encode()).hexdigest() == endpoints[0]["answer_sha256"]
    full, off = [g["matched"] for g in grades]
    n = grades[0]["positions"]
    assert grades[1]["positions"] == n == len(row["labels"])
    strata = ["paired", "history_on" if retained else "other_route",
              "all_A" if set(row["labels"]) == {"A"} else "contains_BC"]
    if all(end.get("flags") == [] for end in endpoints):
        strata.append("unflagged")
        if retained:
            strata.append("on_unflagged")
    for name in strata:
        g = groups[name]
        g.update(dict(tasks=1, positions=n, full=full, off=off))
        g["off_win" if off > full else "off_loss" if off < full else "tie"] += 1
        for key in ("OPB","UPB","FM"):
            for arm, end in zip(("full","off"), endpoints):
                v = end["grade"].get(key)
                if isinstance(v, int):
                    g[f"{arm}_{key}"] += v
                    g[f"{arm}_{key}_valid"] += 1
    if off != full:
        cases.append([uid.split("formal_multi_v1/")[-1], retained, full, off, n])
assert len(rows) == 300
print(json.dumps(dict(counts=counts, groups=groups, changed=cases), indent=2))
