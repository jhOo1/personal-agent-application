"""Matched benchmark metrics from frozen DCR receipts."""
import json
from collections import Counter
from pathlib import Path

from summarize_reassembly import aligned, measure

HERE = Path(__file__).resolve().parent
ARMS = ("BASE", "SHARED", "LOCAL")


def evidence_keys(group):
    return {(item["source"], item["quote"]) for item in group["evidence"]}


def main():
    plan = json.loads((HERE / "FROZEN.json").read_text())
    result = json.loads((HERE / "RESULTS.json").read_text())
    outputs = {(row["uid"], row["method"]): row for row in result["rows"]}
    groups = Counter()
    totals = Counter()
    cases = {}
    for row in plan["rows"]:
        uid, benchmark, stratum = (row[k] for k in ("uid", "benchmark", "stratum"))
        context = result["compiled"].get(uid)
        distinct = bool(context and len(context["groups"]) == 2 and
            evidence_keys(context["groups"][0]) != evidence_keys(context["groups"][1]))
        cells = {"BASE": measure(benchmark, stratum, row["base_score"])}
        for arm in ARMS[1:]:
            cells[arm] = measure(benchmark, stratum, outputs[uid, arm]["score"])
        cases[uid] = {"stratum":stratum,"exposure_diff":distinct,"scores":cells,
            "same_answer":outputs[uid,"LOCAL"]["answer"] == outputs[uid,"SHARED"]["answer"]}
        for arms in (ARMS,ARMS[1:]):
            tag = "/".join(arms)
            if not aligned(cells,arms):
                continue
            slices = ["all",stratum] + (["different_exposure"] if distinct else [])
            for subset in slices:
                groups[benchmark,tag,subset] += 1
                for arm in arms:
                    for key,value in cells[arm].items():
                        totals[benchmark,tag,subset,arm,key] += value
    print(json.dumps({
        "counts":{" / ".join(k):v for k,v in sorted(groups.items())},
        "metrics":{" / ".join(k):v for k,v in sorted(totals.items())},
        "cases":cases,"calls":result["calls"],"statuses":result["statuses"],
        "tokens":result["tokens"],
        "usage_unknown":sum("total_tokens" not in (r["usage"] or {}) for r in result["ledger"]),
        "issues":result["issues"],
    },ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
