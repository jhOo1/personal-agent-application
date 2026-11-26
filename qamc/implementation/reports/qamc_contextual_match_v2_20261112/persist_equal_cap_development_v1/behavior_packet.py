"""Build a private score- and arm-masked utility audit packet from finished outputs."""
import json
from pathlib import Path
from runpy import run_path

from qamc.common import sha

HERE = Path(__file__).resolve().parent


def packet(pin, rows, public):
    shared, methods, missing = {}, {}, []
    for row in rows:
        uid = row["uid"]
        if uid not in pin["cohort"]:
            raise ValueError("Unallocated case")
        answer = row["answer"]
        if not answer:
            missing.append({"uid": uid, "arm": row["arm"], "status": row["status"]})
            continue
        tag = sha(["utility-behavior", uid, answer])
        shared[tag] = {"audit_id": tag, "query": public[uid]["query"],
                       "original_candidate_memory": public[uid]["memories"], "answer": answer}
        methods.setdefault(tag, []).append({"uid": uid, "arm": row["arm"], "group": row["group"]})
    return {"checklist": (HERE / "BEHAVIOR.md").read_text(), "items": [shared[k] for k in sorted(shared)]}, {
        "mapping": methods, "missing_answers": missing}


if __name__ == "__main__":
    runner = run_path(str(HERE / "run_bu.py"))
    run = runner["RUN"]
    load = runner["read"]
    result = load(run / "RESULTS.json")
    pin, _, _, public, *_ = runner["prepare"]()
    if pin != load(run / "FROZEN.json"):
        raise ValueError("Audit inputs differ from the generation freeze")
    blind, mapping = packet(pin, result["rows"], public)
    freeze = runner["probe"].freeze
    freeze(run / "BEHAVIOR_PACKET_PRIVATE.json", blind)
    freeze(run / "BEHAVIOR_MAPPING_PRIVATE.json", mapping)
    print(json.dumps({"unique_items": len(blind["items"]),
                      "missing_answers": len(mapping["missing_answers"])}))
