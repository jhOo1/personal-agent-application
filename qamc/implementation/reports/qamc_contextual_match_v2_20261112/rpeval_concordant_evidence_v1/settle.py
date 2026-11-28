"""Inspect the source and output trade-offs of the equal-count RPEval comparison."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

trial = run_path(str(Path(__file__).with_name("trial.py")))
OUT, RUN, archive, prepare, sha = (trial[k] for k in ("OUT", "RUN", "archive", "prepare", "sha"))
ARMS = ("IPE_C", *trial["ARMS"])


def summarize():
    pin, cards, jobs = prepare()
    if pin != archive.read(OUT / "FROZEN.json"):
        raise ValueError("Frozen experiment mismatch")
    output = archive.read(OUT / "RESULTS.json")
    index = {(r["uid"], r["method"]): r for r in output["rows"]}
    if set(index) != set(jobs) or len(output["rows"]) != len(index):
        raise ValueError("Missing or duplicate filled slot")
    receipts = []
    for file in RUN.glob("*/visible/*/record.json"):
        record = archive.read(file)
        if sha(archive.read(file.with_name("request.json"))) != record["request_sha256"]:
            raise ValueError("Saved request digest differs")
        receipts.append(record)

    def key(record):
        return record["unit"]["stage"], record["request_sha256"], record["status"]

    ledger = output["ledger"]
    if Counter(map(key, ledger)) != Counter(map(key, receipts)):
        raise ValueError("Unreconciled physical calls")
    totals = defaultdict(lambda: {m: Counter() for m in ARMS})
    retention = {m: Counter() for m in ARMS}
    paired = {m: Counter() for m in ARMS[:-1]}
    rows = []
    for uid, card in cards.items():
        entries = {m: index[uid, m] for m in ARMS[1:]}
        scores = {"IPE_C": card["archive"]["grade"]} | {m: r.get("score") for m, r in entries.items()}
        flags = {"IPE_C": card["archive"]["flags"]} | {m: r.get("score_flags", []) for m, r in entries.items()}
        common = all(s and s.get("match") for s in scores.values())
        lengths = {}
        for method in ARMS:
            kept = set(card["labels"] if method == "IPE_C" else card["retained"][method])
            retention[method].update(card["labels"][k] for k in kept)
            lengths[method] = sum(len(s["text"]) for s in card["records"] if s["memory_id"] in kept)
        if common:
            for method, score in scores.items():
                if score["match"]["positions"] != len(card["labels"]):
                    raise ValueError("Different preference denominator")
                for cohort in ("all", card["stratum"], *(("unflagged",) if not any(flags.values()) else ())):
                    totals[cohort][method].update(tasks=1, match=score["match"]["matched"],
                         positions=score["match"]["positions"], **{key: score[key] for key in ("OPB", "UPB", "FM")})
            for ref in paired:
                diff = scores["CONCORDANT"]["match"]["matched"] - scores[ref]["match"]["matched"]
                paired[ref]["win" if diff > 0 else "loss" if diff < 0 else "tie"] += 1
        rows.append({"case": "/".join(uid.split("/")[-2:]), "stratum": card["stratum"], "valid": common,
                     "scores": {m: s["match"] if s and s.get("match") else None for m, s in scores.items()},
                     "flags": flags, "retained_label_counts": {m: Counter(card["labels"][i] for i in ids)
                     for m, ids in card["retained"].items()}, "source_chars": lengths})
    return {"coverage": pin["coverage"], "assigned": len(cards), "totals": totals, "rows": rows,
            "retention": retention, "paired": paired, "calls": len(ledger), "reuse": output["reuse"],
            "transport": Counter(r["status"] for r in ledger), "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "retries": sum(r["automatic_retries"] for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(summarize(), sort_keys=True, indent=2))
