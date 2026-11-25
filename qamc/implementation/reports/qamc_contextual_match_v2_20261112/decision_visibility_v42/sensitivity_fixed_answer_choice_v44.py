"""Distinguish changed answer choices from scorer flags on replayed V44 output."""
from collections import Counter, defaultdict
import json

import analyze_fixed_answer_choice_v44 as audit
from qamc.common import parse_object, sha
from qamc_rpeval_terminal_judge_sensitivity import inspect, pair_bounds

RP, GENERIC, EVIDENCE = audit.RP, audit.GENERIC, audit.EVIDENCE
run, task = audit.run, audit.task


def guarded_ceiling(rows):
    """After-the-fact native-score ceiling over both existing drafts."""
    values = defaultdict(Counter)
    for row in rows:
        rp, zero = (row["native"][m]["fields"] for m in (RP, audit.ZERO))
        if not all(c.get("match") and all(f in c for f in ("UPB", "FM")) for c in (rp, zero)):
            continue
        all_a = set(row["labels"]) == {"A"}
        keep = all_a or (zero["UPB"] <= rp["UPB"] and zero["FM"] <= rp["FM"])
        old, alternate = (c["match"]["matched"] for c in (rp, zero))
        for key in ("all", "all_A" if all_a else "contains_BC"):
            values[key].update(roots=1, positions=len(row["labels"]), rp_matched=old,
                               best_existing=max(old, alternate),
                               guarded_best=max(old, alternate) if keep else old,
                               guarded_strict_wins=keep and alternate > old)
    return values


def compare(rows):
    archive = run.read(run.stage.prior.OUT / "FROZEN.json")
    roots = {r["uid"]: r for r in archive["roots"]}
    drafts = task.saved_drafts(archive)
    results, witnesses = defaultdict(Counter), []
    for row in rows:
        if not all("source" in row["choices"][m] for m in run.ARMS):
            continue
        uid, labels = row["uid"], row["labels"]
        packet = roots[uid]
        answers = {RP: packet["archived"][RP]["answer"],
                   audit.ZERO: drafts[packet["task_wire_sha256"]]["answer"]}
        modes = {m: row["choices"][m]["source"] for m in run.ARMS}
        observed = [row["native"][m]["fields"].get("match") for m in run.ARMS]
        stratum = "all_A" if set(labels) == {"A"} else "contains_BC"
        tags = ("all", stratum)
        for tag in tags:
            results[tag].update(paired_choices=1, different_source=modes[GENERIC] != modes[EVIDENCE],
                                same_source=modes[GENERIC] == modes[EVIDENCE])
            results[tag].update([GENERIC + "_selects_" + modes[GENERIC], EVIDENCE + "_selects_" + modes[EVIDENCE]])
        alternatives = {m: row["native"][m]["fields"].get("match") for m in (RP, audit.ZERO)}
        if all(alternatives.values()):
            values = {m: cell["matched"] for m, cell in alternatives.items()}
            oracle = max(values.values())
            for tag in tags:
                results[tag].update(oracle_cases=1, oracle_matched=oracle, oracle_positions=len(labels))
                for m in run.ARMS:
                    selected = modes[m]
                    results[tag].update({
                        m + "_regret_from_selecting_" + selected: oracle - values[selected],
                        m + "_oracle_equal": values[selected] == oracle,
                    })
        if not all(observed):
            continue
        already = {}
        for m in run.ARMS:
            cell = row["native"][m]
            text = answers[modes[m]]
            if sha(text) != row["choices"][m]["answer_sha256"]:
                raise ValueError("Source answer hash changed")
            already[m] = inspect({"uid": uid, "method": m, "native_fields": cell["fields"], "answer": text,
                                  "raw_scores": {run.stage.JUDGE: cell["raw"]}}, labels)
        low, high = pair_bounds(already[EVIDENCE], already[GENERIC])
        delta = observed[1]["matched"] - observed[0]["matched"]
        flags = bool(already[EVIDENCE]["flags"] or already[GENERIC]["flags"])
        for tag in tags:
            results[tag].update(scored_pairs=1, delta=delta, sensitivity_low=low, sensitivity_high=high,
                                flagged_roots=flags, win=delta > 0, loss=delta < 0, tie=delta == 0)
        if modes[GENERIC] != modes[EVIDENCE]:
            witnesses.append({
                "uid": uid, "group": row["group"], "stratum": stratum, "match_delta": delta,
                "sensitivity_range": [low, high], "source": modes,
                "score_flags": {m: already[m]["flags"] for m in run.ARMS},
                "archived_grade_reasons": {m: parse_object(row["native"][m]["raw"]).get("reason") for m in run.ARMS},
            })
    return {
        "source_choice_counts": results, "scored_choice_disagreements": witnesses, "new_model_calls": 0,
        "nondeployable_guarded_ceiling": guarded_ceiling(rows),
        "meaning": "The native score sensitivity is a diagnostic bound. No score changes or human or model adjudication.",
    }


if __name__ == "__main__":
    _, rows, _ = audit.reconstruct()
    print(json.dumps(compare(rows), ensure_ascii=False, indent=2))
