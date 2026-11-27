"""Write an aggregate account of the matched BenchPreS edits."""
from collections import Counter
import json

from expression import WORD
from run_expression import METHODS, RUN, panel, probe


def credit(score, feature):
    if feature is None:
        return None
    row = score["decisions"][feature["position"]]
    if row["preference"] != feature["preference"] or not row["appropriate"]:
        raise ValueError("The graded style attribute did not match the frozen audit")
    return int(row["label"] == "follow")


def sum_scores(cards, statuses):
    totals = Counter()
    features = Counter()
    for card, score in zip(cards, statuses, strict=True):
        if score is None:
            continue
        totals.update({k: score[k] for k in ("aar_numerator", "aar_denominator", "mr_numerator",
                                              "mr_denominator", "task_completeness")})
        totals["tasks"] += 1
        observed = credit(score, card["feature"])
        if observed is not None:
            features.update(follow=observed, positions=1)
    return {"all": totals, "target": features}


def report(result):
    cards = panel()
    rows = {(r["uid"], r["method"]): r for r in result["outputs"]}
    if len(rows) != len(cards) * len(METHODS):
        raise ValueError("Duplicate or missing final output")
    method_metrics = {}
    selections = {"all": cards, **{role: [c for c in cards if c["role"] == role]
                                   for role in sorted({c["role"] for c in cards})}}
    for role, allocated in selections.items():
        matched = [c for c in allocated if all(rows[c["uid"], arm]["score"] for arm in METHODS)]
        metric = {"allocated": len(allocated), "common": len(matched),
                  "profile_groups": len({c["group"] for c in matched})}
        metric["STRONG_GATE"] = sum_scores(matched, [c["score"] for c in matched])
        for arm in METHODS:
            metric[arm] = sum_scores(matched, [rows[c["uid"], arm]["score"] for c in matched])
        method_metrics[role] = metric

    edits = {arm: Counter() for arm in METHODS}
    for card in cards:
        for arm in METHODS:
            entry = rows[card["uid"], arm]
            e = edits[arm]
            e[entry["actor_status"]] += 1
            if entry["actor_status"] != "OK":
                continue
            changed = card["answer"] != entry["answer"]
            e.update({"changed_draft": changed, "accepted_edits": entry["accepted_count"],
                      "literal_pass": entry["literal_pass"], "valid_grade": entry["score"] is not None})
            if changed:
                e["words_removed"] += len(WORD.findall(card["answer"])) - len(WORD.findall(entry["answer"]))
                e["characters_removed"] += len(card["answer"]) - len(entry["answer"])
    return {"pairs": method_metrics, "edits": edits, "local_counts": result["local_counts"],
            "calls": dict(Counter(r["unit"]["stage"] for r in result["ledger"])),
            "statuses": result["statuses"], "reported_tokens": result["usage"],
            "unknown_usage": result["unknown_usage"]}


if __name__ == "__main__":
    print(json.dumps(report(probe.read(RUN / "RESULTS.json")), indent=2, sort_keys=True))
