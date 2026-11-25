"""Distinguish no-history score overlap, routing opportunity and policy alignment."""
from collections import Counter, defaultdict
import json

from qamc.common import sha
from qamc_rpeval_terminal_judge_sensitivity import inspect, pair_bounds

from intervention import archived_packet
from score_task_only import METHOD, OUT, READ, saved_drafts, v41


def add_match(table, native):
    matched = native["fields"]["match"]
    table.update(rows=1, match=matched["matched"], positions=matched["positions"],
                 full=matched["matched"] == matched["positions"])


def analyze():
    plan = READ(OUT / "FROZEN.json")
    report = READ(OUT / "RESULTS.json")
    if report["state"]["state"] != "COMPLETE":
        raise ValueError("Diagnostics require a settled scoring-only run")
    original = READ(v41.OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in original["roots"]}
    drafts = saved_drafts(original)
    lookup = {root["uid"]: root for root in report["roots"]}
    summaries, transport, answers = defaultdict(Counter), Counter(), defaultdict(set)
    oracle, sensitivity = defaultdict(Counter), defaultdict(Counter)
    per_roots = []
    for uid, root in roots.items():
        item = lookup[uid]
        labels = item["labels"]
        _, packet = archived_packet(root)
        policy = "".join(item["policy"] for item in packet["preference_use_policy"])
        all_a, policy_all_a = set(labels) == {"A"}, set(policy) == {"A"}
        kind = "all_A" if all_a else "contains_BC"
        subset = "less_exposed" if root["in_sensitivity"] else "additional_groups"
        keys = ("all", kind, subset, f"{subset}/{kind}")
        for key in keys:
            oracle[key].update(planned=1, proposed_task_only=policy_all_a,
                               author_all_A=all_a, author_all_A_detected=all_a and policy_all_a,
                               author_BC_that_would_skip_memory=not all_a and policy_all_a)
        native = item["task_only"]
        wire = plan["ready"].get(uid)
        if wire:
            answers[wire["task_wire_sha256"]].add(wire["answer_sha256"])
        if "match" not in native["fields"]:
            transport.update({kind + "/" + native["status"]: 1})
            continue
        answer = drafts[wire["task_wire_sha256"]]["answer"]
        if sha(answer) != wire["answer_sha256"]:
            raise ValueError("Scored task-only answer changed")
        diagnostic = inspect(
            {"uid": uid, "method": METHOD, "native_fields": native["fields"],
             "answer": answer, "raw_scores": {"RPEvalJudge": native["raw"]}}, labels
        )
        baseline = root["archived"][v41.RP]
        current, previous = native["fields"]["match"], baseline["fields"].get("match")
        drift = (current["matched"] - previous["matched"]) if previous else None
        rp_diagnostic = (inspect(
            {"uid": uid, "method": v41.RP, "native_fields": baseline["fields"],
             "answer": baseline["answer"], "raw_scores": {"RPEvalJudge": baseline["raw_judge"]}}, labels
        ) if previous else None)
        for key in keys:
            score = summaries[key]
            add_match(score, native)
            known = native["fields"]
            for metric in ("OPB", "UPB", "RII", "FM", "VG"):
                if metric in known:
                    score[metric + "_present"] += 1
                    score[metric + "_positive"] += known[metric] > 0
            score["flagged_roots"] += bool(diagnostic["flags"])
            score.update(diagnostic["flags"])
            if drift is not None:
                oracle[key].update(
                    measurable=1, paired_positions=len(labels), archived_match=previous["matched"],
                    rootwise_maximum_gain=max(0, drift),
                    gold_all_A_switch_delta=drift if all_a else 0,
                    predicted_all_A_switch_delta=drift if policy_all_a else 0,
                )
                lo, hi = pair_bounds(diagnostic, rp_diagnostic)
                warning = bool(diagnostic["flags"] or rp_diagnostic["flags"])
                sensitivity[key].update(
                    paired_roots=1, positions=len(labels), flagged_pair_roots=warning,
                    task_only_minus_RP_worst=lo, task_only_minus_RP_best=hi,
                    unflagged_roots=not warning, unflagged_positions=0 if warning else len(labels),
                    unflagged_task_only_minus_RP=0 if warning else drift,
                )
        per_roots.append({"uid": uid, "author_all_A": all_a, "RP_all_A": policy_all_a,
                          "group": root["group"], "task_only_minus_RP_match_count": drift,
                          "native_score_flags": diagnostic["flags"]})
    if any(len(values) != 1 for values in answers.values()):
        raise ValueError("A shared task wire has more than one draft")
    return {
        "task_only_native_summary": summaries, "missing_controls": transport,
        "routing_comparison": oracle, "rp_judge_dispute_sensitivity": sensitivity, "rows": per_roots,
        "generation_requests": 0, "evaluation_only": True,
        "interpretation": ("Switch estimates choose between already saved answers. The gold condition "
                           "and rootwise maximum are descriptive upper references, not deployable scores. "
                           "Each switch leaves all other archived answers fixed. Native errors on task-only "
                           "answers may be rubric failures, incidental overlap, or answer quality defects."),
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
