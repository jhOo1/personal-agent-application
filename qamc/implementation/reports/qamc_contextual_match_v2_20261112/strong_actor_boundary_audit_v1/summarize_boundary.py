"""Unblind model assessments without changing any saved native grades."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text())


def summarize():
    frozen, result = read("FROZEN.json"), read("RESULTS.json")
    cases = {row["uid"]:row for row in frozen["rows"]}
    if cases.keys() != {r["uid"] for r in result["rows"]}:
        raise ValueError("Unmatched frozen review roots")
    records, counts = [], Counter()
    for row in result["rows"]:
        case = cases[row["uid"]]
        benchmark = case["benchmark"]
        counts[f"{benchmark}/scheduled"] += 1
        if row["review"] is None:
            counts[f"{benchmark}/missing_valid_review"] += 1
            continue
        counts[f"{benchmark}/valid_review"] += 1
        target = {t["id"]:t for t in case["targets"]}
        for x in row["review"]:
            datum = target[x["id"]]
            states = {case["blind"][slot]: values for slot,values in x["answers"].items()}
            record = {"uid":row["uid"],"benchmark":benchmark,"group":case["group"],
                      "target":datum,"scope":x["applicability"],"decision":x["decision"],
                      "states":states}
            records.append(record)
            counts["/".join((benchmark,datum["role"],x["applicability"],states["BASE"]["status"]))] += 1
    candidates = [r for r in records if r["target"]["role"] == "FOCAL"
                  and r["scope"] == "APPLIES" and r["states"]["BASE"]["status"] == "OMITTED"]
    witnessed = [r for r in candidates if r["states"].get("OTHER",{}).get("status") == "REALIZED"]
    return {"counts":counts,"records":records,"candidate_omissions":candidates,
            "alternate_answer_witnesses":witnessed,
            **{k:result[k] for k in ("requests","statuses","tokens","unknown_usage")}}


if __name__ == "__main__":
    print(json.dumps(summarize(),ensure_ascii=False,indent=2))
