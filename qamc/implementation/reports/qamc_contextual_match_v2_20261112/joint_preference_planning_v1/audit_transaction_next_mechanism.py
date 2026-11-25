"""Measure whether a better chooser could recover existing answers on RPEval."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_decision_transactions as run


METHODS = (run.ARCHIVED[0], run.method.ATOMIC, run.method.BUNDLED)
CONTROLS = (run.method.ORDINARY, run.ARCHIVED[2])
QUALITY = ("OPB", "UPB", "FM")
DIAGNOSED = ("explicit/014", "explicit/020", "implicit/021", "explicit/032", "explicit/037",
             "explicit/046", "explicit/064", "implicit/147", "4203f7b6afcbdade5e1d")


def profile(labels):
    return "contains_C" if "C" in labels else "B_without_C" if "B" in labels else "all_A"


def score(row, arm):
    fields = row["native"][arm]["fields"]
    match = fields.get("match")
    if not match or any(type(fields.get(key)) not in (int, float) for key in QUALITY):
        return None
    if not 0 <= match["matched"] <= match["positions"] == row["positions"]:
        raise ValueError("Match does not match the frozen position count")
    return match["matched"], *(fields[key] for key in QUALITY)


def bounds(settled, roots, data):
    aggregates, used, details = defaultdict(Counter), defaultdict(set), []
    for row in settled["rows"]:
        uid = row["uid"]
        root, blocks = roots[uid], data[uid]["blocks"]
        answers = {**row["outputs"], METHODS[0]: run.method.rank.render(root, blocks, {}, run.method.rank.DRAFT)["answer"]}
        answers[CONTROLS[1]] = root["archived"][CONTROLS[1]]["answer"]
        for control in CONTROLS:
            arms = (*METHODS, control)
            scores = {arm: score(row, arm) for arm in arms}
            if any(value is None for value in scores.values()):
                continue
            by_answer, disputes = {}, set()
            for arm in arms:
                answer_hash = sha(answers[arm])
                incumbent = by_answer.setdefault(answer_hash, arm)
                if scores[incumbent] != scores[arm]:
                    disputes.add(answer_hash)
            layer = profile(row["labels"])
            if disputes:
                for key in ((control, "all"), (control, layer)):
                    aggregates[key]["conflicting_identical_score_histories_excluded"] += 1
                continue

            base = scores[control]
            pooled = [scores[arm] for arm in METHODS]
            protected = [value for value in pooled if all(x <= y for x, y in zip(value[1:], base[1:], strict=True))]
            highest = max(value[0] for value in pooled)
            protected_highest = max([base[0], *(value[0] for value in protected)])
            metrics = {"histories": 1, "positions": row["positions"], "control_match": base[0],
                       "atomic_match": scores[run.method.ATOMIC][0], "pool_oracle_match": highest,
                       "has_pool_answer_protecting_all_metrics": bool(protected),
                       "protected_oracle_match_with_control_fallback": protected_highest,
                       "protected_gain_histories": protected_highest > base[0]}
            for key in ((control, "all"), (control, layer)):
                used[key].add(row["group"])
                aggregates[key].update(metrics)
            details.append({"uid": uid, "group": row["group"], "author_profile": layer, "control": control,
                            **metrics, "distinct_answers": len(by_answer)})
    return {"pool": METHODS, "severity_protection": QUALITY,
            "by_comparator": {control: {layer: {**v, "source_groups": len(used[arm, layer])}
                                         for (arm, layer), v in aggregates.items() if arm == control}
                              for control in CONTROLS},
            "histories": details, "oracle_diagnostic_only": True}


def available_matched_histories():
    effect = run.previous
    _, _, _, roots, _, _ = effect.prepare()
    original = effect.prior.old.prior.parent.prior
    frozen, _, _, rows, _, _ = original.prepare("pilot")
    named = (*DIAGNOSED, *run.REGRESSION, *effect.DISCLOSED, *effect.prior.DISCLOSED)
    excluded = set(frozen["diagnostic_source_groups"]) | {row["group"] for row in rows if row["uid"].endswith(named)}
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        root = roots[row["uid"]]
        key = row["group"], sha(root["public_task"]), root["task_wire_sha256"]
        grouped[key][profile(row["labels"])].append(row["uid"])
    combinations = {}
    for mix in ("B_without_C", "contains_C"):
        available = [(key, cells) for key, cells in grouped.items() if cells.get("all_A") and cells.get(mix)]
        outside = [(key, cells) for key, cells in available if key[0] not in excluded]
        combinations[mix] = {"all_matching_task_keys": len(available), "outside_named_diagnostics": len(outside),
                             "outside_distinct_source_groups": len({key[0] for key, _ in outside})}
    return {"exposed_histories": len(rows), "exact_task_keys": len(grouped),
            "named_diagnostic_source_groups": len(excluded), "pairs_with_all_A": combinations}


if __name__ == "__main__":
    plan, _, roots, data, _ = run.prepare("pilot")
    path = run.BASE_OUT / "pilot"
    status = run.read(path / "RUN_STATE.json")
    if status["state"] != "COMPLETE" or run.read(path / "FROZEN.json") != plan:
        raise ValueError("The 55-history frozen experiment is not settled")
    settled_path = path / "SETTLED.json"
    report = {"existing_answer_bounds": bounds(run.read(settled_path), roots, data),
              "exact_task_history_pair_availability": available_matched_histories(),
              "settled_sha256": sha(settled_path.read_bytes()), "new_requests": 0, "new_scores": 0}
    print(json.dumps(report, ensure_ascii=False, indent=2))
