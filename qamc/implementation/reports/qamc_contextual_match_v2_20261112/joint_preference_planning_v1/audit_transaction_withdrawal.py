"""Replay source withdrawal on frozen proposals, with no new model inference."""
from argparse import ArgumentParser
from collections import Counter
import json
from unittest.mock import patch

from qamc.common import sha

from audit_decision_transactions import observed_generation
import run_decision_transactions as run


def committed_sources(units, committed):
    by_id = {unit["index"]: unit for unit in units}
    return {by_id[cell["decision"]]["effects"][key]["source"]["id"]
            for cell in committed for key in cell["effects"]}


def withdraw(root, blocks, units, excluded):
    method = run.method
    permitted = method.scoped.permitted

    def allowed(effect):
        return effect["source"]["id"] not in excluded and permitted(effect)

    with patch.object(method.scoped, "permitted", allowed):
        answer, committed, _ = method.render(root, blocks, units, atomic=True)
    retained = committed_sources(units, committed)
    if retained & excluded:
        raise ValueError("A withdrawn source still appears in the execution trace")
    return answer, retained


def audit(panel, rows, inputs):
    _, _, roots, data, _ = inputs
    counts, collateral, interventions = Counter(), Counter(), []
    changed_groups = set()
    for row in rows:
        method = run.method
        if method.ATOMIC not in row["outputs"]:
            counts["no_compiled_proposal"] += 1
            continue
        uid = row["uid"]
        root, blocks = roots[uid], data[uid]["blocks"]
        labels = dict(zip((source["memory_id"] for source in root["original_sources"]), row["labels"], strict=True))
        units = row["units"]
        answer = row["outputs"][method.ATOMIC]
        current = committed_sources(units, row["execution"][method.ATOMIC]["committed"])
        counts["with_compiled_proposal"] += 1
        if not current:
            continue
        counts["with_committed_sources"] += 1

        for source in sorted(current):
            changed_answer, retained = withdraw(root, blocks, units, {source})
            counts["single_source_withdrawals"] += 1
            counts["single_source_answer_changed"] += changed_answer != answer
            lost = current - retained - {source}
            collateral.update(f"{labels[source]}/{labels[affected]}" for affected in lost)

        # Author labels are used on already-generated receipts only. The mask
        # isolates how far hypothetical perfect A rejection could go with the
        # current proposals and compiler. It is never part of the tested method.
        unsuitable = {source for source, label in labels.items() if label == "A"}
        if not unsuitable & current:
            continue
        masked, retained = withdraw(root, blocks, units, unsuitable)
        draft = method.rank.render(root, blocks, {}, method.rank.DRAFT)["answer"]
        lost = (current - retained) - unsuitable
        gained = retained - current
        counts["author_A_masked_histories"] += 1
        counts["author_A_mask_changed_answer"] += masked != answer
        counts["author_A_mask_reverts_to_task_draft"] += masked != answer and masked == draft
        counts["author_A_mask_lost_legal"] += bool(lost)
        counts["author_A_mask_gained_legal"] += bool(gained)
        if masked != answer:
            changed_groups.add(row["group"])
        interventions.append({"uid": uid, "group": row["group"], "old": sorted(current), "new": sorted(retained),
                              "lost_B": sum(labels[source] == "B" for source in lost),
                              "lost_C": sum(labels[source] == "C" for source in lost),
                              "gained_B": sum(labels[source] == "B" for source in gained),
                              "gained_C": sum(labels[source] == "C" for source in gained),
                              "answer_sha256": sha(answer), "masked_answer_sha256": sha(masked),
                              "content_changed": masked != answer, "equals_task_only_draft": masked == draft})

    return {"panel": panel, "counts": counts, "single_source_collateral_by_removed_and_lost_label": collateral,
            "author_A_mask_groups_with_content_change": len(changed_groups), "author_A_mask_cases": interventions,
            "new_requests": 0, "new_scores": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("panel", choices=("smoke", "pilot"))
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    out = run.BASE_OUT / args.panel
    inputs = run.prepare(args.panel)
    if args.snapshot:
        settled = observed_generation(args.panel, inputs, out)
    else:
        if run.read(out / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Run has not settled")
        settled = run.read(out / "SETTLED.json")
    result = audit(args.panel, settled["rows"], inputs)
    print(json.dumps({**result, "snapshot": args.snapshot}, ensure_ascii=False, indent=2))
