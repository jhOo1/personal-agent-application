"""Read only the frozen direct-feature trial and verify actual Actor inputs."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())

cards = {r["uid"]: r for r in read(HERE / "PANEL.json")["cases"]}
out = HERE / "receipts"
seen = set()
for unit in read(out / "FixedRouteActor_MANIFEST.json")["units"]:
    uid, arm = unit["unit"]["root_id"], unit["unit"]["method"]
    wire = unit["request"]
    system, sep, example = wire["messages"][0]["content"].rpartition("\n\nIllustration from a different task, for the writing approach only. ")
    assert sep and example and (uid, arm) not in seen
    seen.add((uid, arm))
    wire["messages"][0]["content"] = system
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert sha256(encoded).hexdigest() == cards[uid]["qwen_request_sha256"]
arms = ("TASK_FEATURE", "MEMORY_FEATURE")
assert seen == {(uid, arm) for uid in cards for arm in arms}
result = read(out / "RESULTS.json")
rows = {(r["uid"], r["method"]): r for r in result["rows"]}
print("| Stratum | UID suffix | positions | IPE-C / generic / memory Match | OPB | UPB | FM |")
print("|---|---|---:|---|---|---|---|")
totals = defaultdict(Counter)
for uid, card in cards.items():
    scores = [card["base_grade"], *(rows[uid, arm]["score"] for arm in arms)]
    denom = scores[0]["match"]["positions"]
    if not all(s and (s.get("match") or {}).get("positions")==denom for s in scores):
        print(f"| {card['stratum']} | {uid.split('v1/')[-1]} | {denom} | missing paired Match | | | |")
        continue
    values = [[s["match"]["matched"] for s in scores]] + [[s.get(k) for s in scores] for k in ("OPB","UPB","FM")]
    print("|", " | ".join([card["stratum"],uid.split("v1/")[-1],str(denom),
                          *[" / ".join(map(str,v)) for v in values]]), "|")
    for key, vs in zip(("Match","OPB","UPB","FM"),values):
        if None not in vs:
            totals[key].update(dict(zip(("IPE-C",*arms),vs)))
            totals[key].update({"tasks":1,"positions":denom})
print()
for key,c in totals.items(): print(key,dict(c))
ledger = result["ledger"]
print("Receipts",dict(Counter(e["status"] for e in ledger)),"reported tokens",
      sum((e["usage"] or {}).get("total_tokens",0) for e in ledger),"unknown usage",
      sum((e["usage"] or {}).get("total_tokens") is None for e in ledger))
