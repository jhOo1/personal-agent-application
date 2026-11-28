"""Measure paired wins and admitted author labels after generation."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
exp = run_path(str(HERE / "trial.py"))
read = exp["read"]


def main():
    pin, items = exp["prepare"]()
    if pin != read(exp["PRIVATE"] / "FROZEN.json"):
        raise ValueError("Frozen request drift")
    labels = {e["uid"]: e["labels"] for pair in read(
        HERE.parent / "source_local_reentry_v1/ELIGIBILITY.json")["pairs"] for e in pair["endpoints"]}
    rows = read(exp["PRIVATE"] / "SETTLED.json")["rows"]
    by_uid = defaultdict(dict)
    for r in rows:
        if r["method"] in by_uid[r["uid"]]:
            raise ValueError("Duplicate logical answer")
        by_uid[r["uid"]][r["method"]] = r
    stats = defaultdict(Counter)
    changed = []
    for uid, item in items.items():
        track = item["track"]
        top, cover = (by_uid[uid][arm] for arm in exp["ARMS"])
        lookup = dict(zip((entry["memory_id"] for entry in item["sources"]), labels[uid], strict=True))
        for arm, row in by_uid[uid].items():
            stats[track + "/" + arm + "/selected_labels"].update(lookup[s] for s in row["selected"])
        base = item["base"]
        for ref, ref_score, ref_flags in (
            ("TOP", top["score"], top["score_flags"]),
            ("IPE-C", base["grade"], base["flags"]),
        ):
            counter = stats[track + "/COVER_vs_" + ref]
            score = cover["score"]
            if not all((grade or {}).get("match") for grade in (score, ref_score)):
                counter["unknown"] += 1
                continue
            if score["match"]["positions"] != ref_score["match"]["positions"]:
                raise ValueError("Match denominators differ")
            delta = score["match"]["matched"] - ref_score["match"]["matched"]
            direction = "win" if delta > 0 else "loss" if delta < 0 else "tie"
            counter[direction] += 1
            if not (cover["score_flags"] or ref_flags):
                counter["unflagged_" + direction] += 1
        if top["selected"] != cover["selected"]:
            record = {"case": uid.split("/")[-1], "track": track}
            for arm, row in by_uid[uid].items():
                grade = row["score"] or {}
                record[arm] = {"admitted": [lookup[s] for s in row["selected"]],
                               "match": grade.get("match"), "flags": row["score_flags"],
                               "bias": {key: grade.get(key) for key in ("OPB", "UPB", "FM")}}
            changed.append(record)
    print(json.dumps({"stats": stats, "changed_admission": changed}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
