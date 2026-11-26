"""Summarize frozen contingency arms on shared strict Match denominators."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "rpe_contingency_v1"
METHODS = ("BASE", "ORDINARY", "TWO_STATE")
SEVERITIES = ("OPB", "UPB", "FM")


def read(path):
    return json.loads(path.read_text())


def summarize(panel, result):
    runs = {(r["uid"], r["method"]): r for r in result["rows"]}
    if len(runs) != len(result["rows"]):
        raise ValueError("Duplicate Actor result")
    scores = {}
    for card in panel:
        uid = card["uid"]
        left, right = (runs[uid, m] for m in METHODS[1:])
        if left["base_score"] != right["base_score"]:
            raise ValueError("Base grade drift between arms")
        scores[uid] = (left["base_score"], left["score"], right["score"])
    slices = ["all", *dict.fromkeys(card["stratum"] for card in panel)]
    summary, invalid = {}, []
    for subset in slices:
        cards = [c for c in panel if subset in ("all", c["stratum"])]
        counts = Counter(assigned=len(cards))
        totals = {method: Counter() for method in METHODS}
        for card in cards:
            uid = card["uid"]
            cells = scores[uid]
            if not all(cell and cell.get("match") for cell in cells):
                if subset == "all":
                    invalid.append(uid)
                continue
            sizes = {s["match"]["positions"] for s in cells}
            if len(sizes) != 1:
                raise ValueError(f"Strict denominator drift: {uid}")
            counts["paired"] += 1
            counts["positions"] += sizes.pop()
            matched = [s["match"]["matched"] for s in cells]
            for key, a in zip(("base", "ordinary"), matched):
                diff = matched[2] - a
                counts[f"vs_{key}_{'win' if diff > 0 else 'loss' if diff < 0 else 'tie'}"] += 1
            common_fields = [f for f in SEVERITIES if all(type(cell.get(f)) is int for cell in cells)]
            for field in common_fields:
                counts[f"{field}_paired"] += 1
            for method, cell in zip(METHODS, cells):
                totals[method].update({"Match": cell["match"]["matched"],
                                       **{f: cell[f] for f in common_fields}})
        summary[subset] = {"counts": counts, "severity_and_match": totals}
    receipts = result["ledger"]
    usage = [((x.get("usage") or {}).get("total_tokens")) for x in receipts]
    return {
        "slices": summary,
        "absent_strict_pairs": invalid,
        "receipt_statuses": Counter(x["status"] for x in receipts),
        "reported_tokens": sum(x for x in usage if x is not None),
        "unknown_usage": usage.count(None),
    }


if __name__ == "__main__":
    out = summarize(read(HERE / "RPE_CONTINGENCY_PANEL.json"), read(ROOT / "RESULTS.json"))
    print(json.dumps(out, indent=2))
