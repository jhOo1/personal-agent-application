"""Join only common valid endpoints within each deployment and across deployments."""
import json
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
runs = here.parents[2] / "runs" / here.parent.name / here.name
def read(p):
    return json.loads(p.read_text())

pin = read(runs/"PANEL_V2.json")
cards = {uid:(g,s) for uid,g,s in pin["cards"]}
assert len(cards)==len(set(g for g,s in cards.values()))==24
history = {r["uid"]:r for r in read(here.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
panels = {"archive":{}}
status = Counter()
tokens = misses = 0
for uid in cards:
    panels["archive"][uid] = {arm:history[uid]["scores"][key]["grade"] for arm,key in
                              (("IPE_C","IPE_C"),("TASK_ONLY","TASK_ONLY"),("RP_FULL","RPR_PAPER_FULL"))}
for i in (1,2):
    path = runs/f"deployment{i}"/"RESULTS.json"
    if not path.exists():
        continue
    data = read(path)
    panels[str(i)] = {}
    assert {r["uid"] for r in data["rows"]} == cards.keys()
    for r in data["rows"]:
        assert (r["group"],r["stratum"]) == cards[r["uid"]]
        grades = {arm:cell["grade"] for arm,cell in r["scores"].items()}
        panels[str(i)][r["uid"]] = {**grades,"IPE_C":grades.get(r["branch"],{})}
    for r in data["ledger"]:
        status[r["status"]] += 1
        n = (r.get("usage") or {}).get("total_tokens")
        misses += n is None
        tokens += n or 0

eligible = {k:{u for u,x in p.items() if all(g.get("match") for g in x.values())} for k,p in panels.items()}
shared = set.intersection(*eligible.values())
tables = {}
for wave, p in panels.items():
    for scope in ("all","joint","B_only","all_A","contains_C"):
        subset = shared if scope=="joint" else {u for u in eligible[wave] if scope=="all" or cards[u][1]==scope}
        summary = {}
        for arm in ("IPE_C","TASK_ONLY","RP_FULL"):
            t = Counter()
            for uid in subset:
                g = p[uid][arm]
                m = g["match"]
                t.update(tasks=1, positions=m["positions"], matched=m["matched"], exact=int(m["matched"]==m["positions"]),
                         OPB=g["OPB"], UPB=g["UPB"], FM=g["FM"])
            summary[arm]=dict(t)
        tables[wave+"/"+scope]=summary
print(json.dumps({"settled_fresh_waves":len(panels)-1,"statuses":status,"reported_tokens":tokens,
                  "unknown_usage":misses,"tables":tables},indent=2))
