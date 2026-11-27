"""Inventory native regrading of exposed FR3 answers without invoking a scorer."""
import json
from collections import Counter, defaultdict
from pathlib import Path
from hashlib import sha256

here = Path(__file__).resolve().parent
repo = here.parents[2]
runs = repo / "runs" / here.parent.name
release = repo / "literature/qamc_pa_v1/PersistBench/experiments/multi_turn/paper_traces/baseline_all_models.json"
raw = release.read_bytes()
pin = json.loads((runs / "persist_released_grade_agreement_v1/private/FROZEN.json").read_text())
assert sha256(raw).hexdigest() == pin["release"]
rows = json.loads((runs / "persist_exposure_fr3_v1/RESULTS.json").read_text())["rows"]
eligible = {r["uid"] for r in rows}
published = defaultdict(set)
for entry in json.loads(raw)["entries"].values():
    task = {k: entry[k] for k in ("query", "memories")}
    encoded = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    uid = "persistbench/" + sha256(encoded).hexdigest()[:20]
    if uid in eligible:
        for method in entry["results"].values():
            for g in method["generations"]:
                if not g["error"] and g.get("judge", {}).get("score") is not None:
                    published[uid].add(g["memory_response"])

def inventory(panel):
    by_track = defaultdict(Counter)
    answer_slots = set()
    seen = set()
    for r in rows:
        uid, draw, track = r["uid"], r["repeat"], r["track"]
        if uid not in panel:
            continue
        assert (uid, draw) not in seen
        seen.add((uid, draw))
        counts = by_track[track]
        for method in r["methods"].values():
            counts["allocated"] += 1
            a = method["actor"]
            if not a or a["status"] != "OK" or not a["answer"]:
                counts["unavailable"] += 1
                continue
            key = (uid, draw, a["answer"])
            if key in answer_slots:
                counts["duplicate_answer_slots"] += 1
                continue
            answer_slots.add(key)
            counts["distinct_answer_slots"] += 1
            if a["answer"] in published.get(uid, ()):
                counts["verbatim_native_candidates"] += 1
    for c in by_track.values():
        assert c["allocated"] == c["distinct_answer_slots"] + c["duplicate_answer_slots"] + c["unavailable"]
        c.setdefault("verbatim_native_candidates", 0)
    return by_track

assert len(eligible) == 49 and len(published) == 13
print(json.dumps({"exposed_49": inventory(eligible), "overlap_13": inventory(published)}, indent=2, sort_keys=True))
