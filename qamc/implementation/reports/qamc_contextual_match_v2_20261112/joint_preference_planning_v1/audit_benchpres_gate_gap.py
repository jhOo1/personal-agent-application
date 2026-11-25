"""Locate format and task quality gaps to the archived BenchPreS strong Gate."""
from collections import Counter
import json
import re

from markdown_it import MarkdownIt
from qamc.common import sha

from audit_qamc_benchpres_bold_sensitivity import visible_strong
import run_communication_binding as run


GATE = "GEPA_SELECTED_BOUNDS"
BOLD = re.compile(r"\bbold\s+text\b", re.IGNORECASE)


def audit():
    cases, _, controls = run.archive.context(run.BENCH)
    verified = {row["uid"]: row["score"] for row in controls if row["method"] == GATE}
    baselines = {row["uid"]: row for row in run.archived_answers(run.BENCH, cases) if row["method"] == GATE}
    roots = {row["uid"]: row for row in run.archive.development_roots(run.BENCH)}
    source = run.OUT / run.BENCH
    saved = run.read(source / "SETTLED.json")
    if run.read(source / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The current comparator is not settled")
    candidates = {row["uid"]: row for row in saved["rows"] if row["method"] == run.BOUND}
    totals, completeness, transitions, bold_losses = Counter(), Counter(), [], []
    parser = MarkdownIt("commonmark")
    pairs = []
    for uid, case in cases.items():
        baseline = baselines.get(uid)
        current = candidates[uid]
        if baseline is None or not baseline["score"] or not current["score"]:
            continue
        a, b = baseline["score"], current["score"]
        if a != verified[uid]:
            raise ValueError(f"Archived answer or score differs from receipt-verified anchor: {uid}")
        pairs.append((case, a, b))
        trace = saved["selector"][uid]
        active = any(trace["gate"].values())
        offset = b["task_completeness"] - a["task_completeness"]
        group = case["analysis_group_id"]
        cohort = "active" if active else "same_actor_wire_as_ungated"
        completeness[f"{cohort}/{offset:+d}"] += 1
        case_record = {"uid": uid, "profile_group": group, "gate_activated": active,
                       "completeness": [a["task_completeness"], b["task_completeness"]],
                       "answer_sha256": [sha(baseline["answer"]), sha(current["answer"])]}
        differences = []
        for left, right in zip(a["decisions"], b["decisions"], strict=True):
            pref = left["preference"]
            if (pref, left["appropriate"]) != (right["preference"], right["appropriate"]):
                raise ValueError(f"Attribute roster differs on {uid}")
            appropriate, bold = left["appropriate"], bool(BOLD.search(pref))
            transition = left["label"] + "->" + right["label"]
            family = ("appropriate_bold" if bold else "appropriate_other") if appropriate else "inappropriate"
            totals[f"{family}/{transition}"] += 1
            if left["label"] == right["label"]:
                continue
            exact = {m["memory_id"] for m in roots[uid]["original_sources"] if m["text"] == pref}
            proposed = {use["memory_id"] for use in trace["plain"]} & exact
            passed = {use["memory_id"] for use in trace["bound"]} & exact
            disposition = ("visible" if passed else "removed_by_gate" if proposed else "not_proposed"
                           if exact else "no_exact_original_match")
            entry = {"profile_group": group, "preference": pref, "family": family, "transition": transition,
                     "exact_source_ids": sorted(exact), "new_source_disposition": disposition}
            if transition == "do_not_follow->follow" and not appropriate:
                entry["new_visible_uses"] = [
                    {"decision": use["decision"], "affected_role": use["affected_role"],
                     "typed": trace["typed"][use["memory_id"]]} for use in trace["bound"]
                    if use["memory_id"] in passed]
            if bold:
                entry["visible_markdown_strong"] = [visible_strong(row["answer"], parser)
                                                   for row in (baseline, current)]
            differences.append(entry)
            if appropriate and bold and left["label"] == "follow":
                bold_losses.append({"uid": uid, **entry})
        if offset or differences:
            transitions.append({**case_record, "attribute_differences": differences})
    if run.bench_comparison(pairs) != saved["comparisons"][GATE]:
        raise ValueError("Recomputed pairs differ from the frozen main readout")
    return {"common_native_roots": len(pairs), "comparisons": saved["comparisons"][GATE],
            "attribute_transitions": totals, "completeness_changes": completeness,
            "bold_losses": bold_losses, "changing_cases": transitions,
            "new_requests": 0, "native_scores_modified": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, ensure_ascii=False, sort_keys=True))
