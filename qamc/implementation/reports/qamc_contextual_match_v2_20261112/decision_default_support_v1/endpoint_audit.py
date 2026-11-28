"""Check whether existing endpoints cover the failure cases from the default-support test."""
from collections import Counter
import json

from run_trial import BASE, HERE, archive, prepare, sha

GRADE_FIELDS = ("OPB", "UPB", "FM")
METHODS = ("IPE_C", "TASK_ONLY", "GEPA_SELECTED_BOUNDS")


def audit():
    _, cards, _ = prepare()
    endpoints = {r["uid"]: r for r in archive.read(BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    pair_bank = {r["uid"]: r for r in archive.read(BASE / "selective_path_frontier_v1" / "RESULTS.json")["rows"]}
    test = archive.read(HERE / "AGGREGATE.json")
    tested = {r["case"]: r for r in test["rows"]}
    if len(tested) != len(cards):
        raise ValueError("Incomplete new comparison")
    result = []
    for uid, card in sorted(cards.items()):
        case = "/".join(uid.split("/")[-2:])
        ep, bank = endpoints[uid], pair_bank[uid]
        old, task = (ep["scores"][key] for key in ("IPE_C", "TASK_ONLY"))
        if old["answer_sha256"] != card["baseline_answer_sha256"] or old["grade"] != card["base_score"]:
            raise ValueError(f"Archived IPE-C answer or score mismatch for {case}")
        if task["answer_sha256"] != sha(ep["no_history_state"]["answer"]):
            raise ValueError(f"Archived task-only answer mismatch for {case}")
        if ep["source_group"] != bank["source_group"] or bank["positions"] != len(ep["labels"]):
            raise ValueError(f"Endpoint population mismatch for {case}")
        gate = bank["cells"]["GEPA_SELECTED_BOUNDS"]
        if not gate:
            raise ValueError(f"Missing Gate result for {case}")
        positions = len(ep["labels"])
        def grade(cell):
            if cell["grade"]["match"]["positions"] != positions:
                raise ValueError(f"Endpoint has wrong positions for {case}")
            return {"primary": cell["grade"]["match"]["matched"], "positions": positions,
                    **{k: cell["grade"][k] for k in GRADE_FIELDS}}
        scores = {"IPE_C": grade(old), "TASK_ONLY": grade(task),
                  "GEPA_SELECTED_BOUNDS": {"primary": gate["matched"], "positions": positions,
                                           **{k: gate["fields"][k] for k in GRADE_FIELDS}}}
        if tested[case]["metrics"]["ARCHIVE"] != scores["IPE_C"]:
            raise ValueError(f"Latest comparison mismatch for {case}")
        flags = {"IPE_C": old["flags"], "TASK_ONLY": task["flags"], "GEPA_SELECTED_BOUNDS": gate["flags"]}
        gains = {}
        for method in METHODS[1:]:
            old_score, other = scores["IPE_C"], scores[method]
            if (not (flags["IPE_C"] or flags[method]) and other["primary"] > old_score["primary"]
                    and all(other[key] <= old_score[key] for key in GRADE_FIELDS)):
                gains[method] = other["primary"] - old_score["primary"]
        result.append({"case": case, "stratum": card["stratum"], "scores": scores,
                       "flagged": flags, "protected_gains": gains})
    totals = {method: Counter() for method in METHODS}
    for row in result:
        for method in METHODS:
            totals[method].update(row["scores"][method])
    recoverable = sum(max(row["protected_gains"].values(), default=0) for row in result)
    return {"rows": result, "totals": totals, "protected_archival_oracle_gain": recoverable,
            "new_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
