"""Summarise only a fully settled competition; print no source or response text."""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name / "private"
ARMS = ("MEMADAPTER", "SELECTED", "BREADTH")
BU = "beneficial_memory_usage"


def outcome(track, values):
    if track == BU:
        assert len(values) == 1
        return None if values[0] is None else values[0] == 3
    assert len(values) == 3
    if any(r is not None and r >= 3 for r in values):
        return False
    return None if None in values else True


def compare(pairs):
    counts = Counter()
    lower = upper = 0
    for baseline, candidate in pairs:
        counts["unknown" if None in (baseline,candidate) else
               "tie" if baseline == candidate else "win" if candidate else "loss"] += 1
        lower += int(candidate or False) - int(True if baseline is None else baseline)
        upper += int(True if candidate is None else candidate) - int(baseline or False)
    return dict(pairs=len(pairs), outcomes=dict(counts), net_bounds=[lower,upper])


def main():
    ledger = json.loads((OUT/"SETTLED.json").read_text())["ledger"]
    grouped = defaultdict(dict)
    delivered = Counter()
    for draw in range(1,4):
        data = json.loads((OUT/f"DRAW_{draw}.json").read_text())
        for row in data["rows"]:
            key = (row["track"],row["uid"],row["arm"])
            assert row["draw"] == draw and draw not in grouped[key]
            grouped[key][draw] = row
            delivered[row["arm"],row["actor"]] += 1
    assert len(grouped) == 29*3 and sum(delivered.values()) == 47*3
    report = {}
    for judge in ("GPT","Qwen"):
        stats = {}
        for track in sorted({key[0] for key in grouped}):
            by_uid = defaultdict(dict)
            for (t,u,a), draws in grouped.items():
                if track == t:
                    by_uid[u][a] = outcome(t,[row[judge] for _,row in sorted(draws.items())])
            assert all(set(r)==set(ARMS) for r in by_uid.values())
            stats[track] = dict(
                passes={a:sum(r[a] is True for r in by_uid.values()) for a in ARMS},
                missing={a:sum(r[a] is None for r in by_uid.values()) for a in ARMS},
                comparisons={a+"_vs_"+b:compare([(r[b],r[a]) for r in by_uid.values()])
                             for a,b in (("BREADTH","SELECTED"),("BREADTH","MEMADAPTER"),("SELECTED","MEMADAPTER"))})
        report[judge] = stats
    report["actor_status"] = {a:dict((s,n) for (arm,s),n in delivered.items() if a==arm) for a in ARMS}
    report["ledger"] = dict(rows=len(ledger), statuses=dict(Counter(r["status"] for r in ledger)),
                            reported_tokens=sum((r["usage"] or {}).get("total_tokens",0) for r in ledger),
                            unknown_usage=sum(not r["usage"] for r in ledger))
    print(json.dumps(report,indent=2))

if __name__ == "__main__":
    main()
