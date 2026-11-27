"""Replay two frozen, physically distinct predictions on each endpoint wave."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

here = Path(__file__).resolve().parent
runs = here.parents[2] / "runs" / here.parent.name / "rpe_ipe_fresh_repeat_v1"
def load(path):
    return json.loads(path.read_bytes())
def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

responses = set()
def wave(index):
    folder = runs / f"deployment{index}"
    rows = {r["uid"]:r for r in load(folder / "RESULTS.json")["rows"]}
    estimates = {}
    for p in (folder / "Estimate/visible").glob("*/record.json"):
        record = load(p)
        if record["unit"]["method"] != "RPR_IPE":
            continue
        uid = record["unit"]["root_id"]
        assert uid not in estimates and record["status"] == "OK"
        request = load(p.with_name("request.json"))
        fingerprint = digest(request)
        assert fingerprint == record["request_sha256"]
        ids = [m["memory_id"] for m in json.loads(request["messages"][-1]["content"])["memories"]]
        reply = load(p.with_name("response.json"))
        assert reply["id"] and reply["id"] not in responses
        responses.add(reply["id"])
        orders = {}
        for item in json.loads(reply["answer"])["rankings"]:
            key = item["memory_id"]
            assert key not in orders
            order = "".join(item["order"])
            assert sorted(order) == list("ABC")
            orders[key] = order
        assert set(orders) == set(ids) and len(orders) == len(ids)
        triggers = {k for k, v in orders.items() if v.startswith("C")}
        assert bool(triggers) == (rows[uid]["branch"] == "RP_FULL")
        estimates[uid] = fingerprint, triggers
    assert rows.keys() == estimates.keys()
    return rows, estimates

waves = [wave(i) for i in (1,2)]
assert waves[0][0].keys() == waves[1][0].keys() and len(responses) == 36
routes = defaultdict(Counter)
scores = defaultdict(lambda: defaultdict(Counter))
for uid, row in waves[0][0].items():
    assert row["group"] == waves[1][0][uid]["group"] and row["stratum"] == waves[1][0][uid]["stratum"]
    (h1, a),(h2, b) = [e[uid] for _, e in waves]
    assert h1 == h2
    decisions = dict(first=bool(a), second=bool(b), both_any=bool(a and b), both_same=bool(a & b))
    for group in ("all",row["stratum"]):
        routes[group].update(roots=1, same_set=int(a==b), differing_C_ids=len(a^b),
                             shared_C_ids=len(a&b), extra_veto=int(decisions["both_any"] and not decisions["both_same"]),
                             **{name:int(active) for name, active in decisions.items()})
    for i,(rows,_) in enumerate(waves,1):
        endpoints = rows[uid]["scores"]
        for name,active in decisions.items():
            c = scores[str(i)][name]
            c["assigned"] += 1
            selected = endpoints["RP_FULL" if active else "TASK_ONLY"]["grade"]
            if not selected.get("match"):
                c["assigned_missing"] += 1
            if not all(endpoints[k]["grade"].get("match") for k in ("RP_FULL","TASK_ONLY")):
                continue
            m = selected["match"]
            c.update(common=1, match=m["matched"], positions=m["positions"], exact=int(m["matched"]==m["positions"]),
                     OPB=selected["OPB"], UPB=selected["UPB"])
print(json.dumps(dict(routes=routes, common_scores=scores), indent=2,sort_keys=True))
