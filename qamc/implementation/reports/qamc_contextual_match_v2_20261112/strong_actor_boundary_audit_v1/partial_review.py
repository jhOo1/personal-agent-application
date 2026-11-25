"""Inspect individually supported judgments in rows rejected for nonliteral quotes."""
from collections import Counter
import json

from audit_boundary import HERE, parse, parse_object, read


def partial_review():
    rows = read(HERE/"RESULTS.json")["rows"]
    frozen = {r["uid"]:r for r in read(HERE/"FROZEN.json")["rows"]}
    recovered, overall = [], Counter()
    for row in rows:
        if row.get("error") != "Nonverbatim evidence":
            continue
        case = frozen[row["uid"]]
        parsed = parse_object(row["receipt"]["answer"])
        discarded = []
        try:
            for target in parsed["targets"]:
                for slot, state in target["answers"].items():
                    q = state["quote"]
                    if q and q not in case["answers"][case["blind"][slot]]:
                        discarded.append({"id":target["id"],"slot":slot,"raw":dict(state)})
                        state.update(status="UNCERTAIN",quote="")
            safe = parse(json.dumps(parsed,ensure_ascii=False),case)
        except (ValueError,TypeError,KeyError) as error:
            recovered.append({"uid":row["uid"],"error":str(error)})
            continue
        targets = []
        for item in safe:
            meta = next(t for t in case["targets"] if t["id"] == item["id"])
            if meta["role"] != "FOCAL":
                continue
            state = {method:item["answers"][slot]["status"] for slot,method in case["blind"].items()}
            overall[f'{row["benchmark"]}/{item["applicability"]}/{state["BASE"]}'] += 1
            targets.append({"id":item["id"],"applicability":item["applicability"],"states":state,
                            "decision":item["decision"]})
        recovered.append({"uid":row["uid"],"discarded_nonliteral_slots":discarded,"targets":targets})
    return {"strict_rows_modified":0,"sensitivity_counts":overall,"partial_rows":recovered}


if __name__ == "__main__":
    print(json.dumps(partial_review(),ensure_ascii=False,indent=2))
