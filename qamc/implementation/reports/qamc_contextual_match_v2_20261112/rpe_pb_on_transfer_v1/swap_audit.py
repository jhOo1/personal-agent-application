"""Select every count-matched A-to-B exchange, then reconcile both saved draws."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
archive = here.parents[2] / "runs" / here.parent.name / here.name
def read(path):
    return json.loads(path.read_text())

labels = {r["uid"]: r["labels"] for r in read(here.parent / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
first = read(archive / "DRAW0.json")["selection"]
result = {}
for uid, s in first.items():
    if s["status"] != "CHANGED":
        continue
    pb, rp = set(s["pb"]), set(s["rp"])
    gained, lost = sorted(pb - rp), sorted(rp - pb)
    tags = labels[uid]
    if [tags[i] for i in gained] != ["B"] or [tags[i] for i in lost] != ["A"]:
        continue
    entry = {"tags":tags, "added_index_1based":gained[0]+1, "removed_index_1based":lost[0]+1, "draws":[]}
    for i in range(2):
        draw = read(archive / f"DRAW{i}.json")
        assert draw["selection"][uid] == s
        scores = {}
        for row in draw["rows"]:
            if row["uid"] != uid or row["arm"] not in ("PB","RP_K"):
                continue
            g = json.loads(row["judge"]["answer"])
            assert row["status"] == "OK" and row["actor"]["answer"].strip()
            m = row["grade"]["match"]
            assert g["match"] == f'{m["matched"]}/{m["positions"]}'
            scores[row["arm"]] = dict(match=g["match"], OPB=g["OPB"], UPB=g["UPB"], flags=row["flags"])
        assert len(scores) == 2
        entry["draws"].append(scores)
    result[uid] = entry
print(json.dumps(result, indent=2))
