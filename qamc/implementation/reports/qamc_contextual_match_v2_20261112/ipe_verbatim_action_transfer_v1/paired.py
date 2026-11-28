"""Compare both interventions and original endpoints on exact common tasks."""
from collections import Counter, defaultdict
import json

import trial


def scalar(score):
    grade = (score or {}).get("grade", {})
    return grade.get("match", {}).get("matched")


def main():
    _, cards, _ = trial.build()
    data = trial.read(trial.PRIVATE / "RESULTS.json")
    records = {(r["uid"], r["method"]): r for r in data["rows"]}
    totals = defaultdict(Counter)
    for uid, card in cards.items():
        two = {m: records[uid, m] for m in ("FREE", "DONOR")}
        compared = {"BASE": card["base_score"], "ALTERNATE": card["alternate_score"],
                    **{m: r["score"] for m, r in two.items()}}
        for reference in ("BASE", "FREE", "ALTERNATE"):
            for tag in ("ALL", card["stratum"]):
                c = totals[tag + "/" + reference]
                c["assigned"] += 1
                a, b = (scalar(compared[m]) for m in ("DONOR", reference))
                if a is None or b is None:
                    c["unknown"] += 1
                    continue
                c["positions"] += len(card["labels"])
                c["donor_match"] += a
                c["reference_match"] += b
                c["win" if a > b else "loss" if a < b else "tie"] += 1
                if reference == "FREE":
                    c["same_output"] += int(two["FREE"]["answer"] == two["DONOR"]["answer"])
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
