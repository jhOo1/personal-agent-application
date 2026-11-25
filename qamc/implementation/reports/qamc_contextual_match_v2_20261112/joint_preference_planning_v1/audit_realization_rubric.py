"""Check native RPEval recall scores against the frozen rubric, preserving the originals."""
from collections import Counter, defaultdict
import json
import re

from qamc.common import parse_object, sha
from qamc_rpeval_terminal_judge_sensitivity import inspect, pair_bounds

import run_realization_append_ablation as ablation
from settle_decision_realization import checked


MAIN, GATE, RP = ablation.MAIN_ONLY, ablation.parent.GATE, ablation.parent.RP
ARMS = (MAIN, GATE, RP)
LABEL_RUN = re.compile(r"(?<![A-Z])[ABC]{2,}(?![A-Z])")


def source_rows():
    _, realized, _ = checked()
    folder = ablation.parent.joint.prior.OUT
    roots = {r["uid"]: r for r in ablation.read(folder / "FROZEN.json")["roots"]}
    ablated = ablation.read(ablation.OUT / "SETTLED.json")["rows"]
    changed = ablation.changed_answers(realized)
    by_uid = {row["uid"]: row for row in realized}
    for row in ablated:
        uid = row["uid"]
        root = roots[uid]
        actor = by_uid[uid]["actor"][ablation.method.SEGMENTED]
        answers = {MAIN: changed[uid][0] if uid in changed else actor.get("answer"),
                   **{arm: root["archived"][arm]["answer"] for arm in ARMS[1:]}}
        yield row, root, answers


def evidence(row, answer, arm):
    uid, labels = row["uid"], row["labels"]
    saved = row["native"][arm]
    raw, fields = saved.get("raw"), saved["fields"]
    result = {"UPB": fields.get("UPB"), "flags": [], "match": None}
    if raw is None:
        return result
    if not isinstance(answer, str) or not answer:
        raise ValueError(f"Score without the exact answer: {uid}/{arm}")
    try:
        reason = parse_object(raw).get("reason", "")
    except ValueError:
        if fields:
            raise
        result["flags"].append("UNPARSEABLE_NATIVE_REPLY")
        return result
    if not isinstance(reason, str):
        reason = ""
    named_labels = sorted({ref for ref in LABEL_RUN.findall(reason) if len(ref) == len(labels)})
    flags = result["flags"]
    if named_labels and labels not in named_labels:
        flags.append("REASON_NAMES_DIFFERENT_INTENT")
    if set(labels) == {"A"} and (result["UPB"] or 0) > 0:
        flags.append("ALL_A_HAS_UNDERPERSONALIZATION")
    if fields.get("match"):
        diagnosed = inspect({"uid": uid, "method": arm, "answer": answer, "native_fields": fields,
                             "raw_scores": {"RPEvalJudge": raw}}, labels)
        flags.extend(diagnosed["flags"])
        result["match"] = {**diagnosed, "flags": flags}
    result.update(answer_sha256=sha(answer), judge_sha256=sha(raw), explicit_intents=named_labels, reason=reason)
    return result


def summarize(cases, opposite):
    c, flags = Counter(), {"MAIN": Counter(), "OTHER": Counter()}
    upb_slices = defaultdict(Counter)
    groups = set()
    for row in cases:
        main, other = (row["cells"][arm] for arm in (MAIN, opposite))
        for name, cell in (("MAIN", main), ("OTHER", other)):
            flags[name].update(cell["flags"])
            flags[name]["any_flag"] += bool(cell["flags"])
        status = "warning_in_pair" if main["flags"] or other["flags"] else "no_detected_warning"
        if main["UPB"] is not None and other["UPB"] is not None:
            delta = main["UPB"] - other["UPB"]
            upb_slices[status].update(common=1, main_total=main["UPB"], other_total=other["UPB"],
                                     worse=delta > 0, better=delta < 0, tie=delta == 0)
        if main["match"] is not None and other["match"] is not None:
            lo, hi = pair_bounds(main["match"], other["match"])
            groups.add(row["group"])
            c.update(cases=1, positions=len(row["labels"]), main=main["match"]["matched"],
                     other=other["match"]["matched"], min_delta=lo, max_delta=hi,
                     flagged=status == "warning_in_pair")
    return {"match": dict(c, source_groups=len(groups)), "warnings": flags, "upb_strata": upb_slices}


def audit():
    cases = [{"uid": row["uid"], "group": row["group"], "labels": row["labels"],
              "cells": {arm: evidence(row, answers[arm], arm) for arm in ARMS}}
             for row, _, answers in source_rows()]
    strata = {"all": cases, "all_A": [r for r in cases if set(r["labels"]) == {"A"}],
              "mixed": [r for r in cases if set(r["labels"]) != {"A"}]}
    return {"assigned": len(cases), "analyses": {name: {arm: summarize(subset, arm) for arm in ARMS[1:]}
                                                  for name, subset in strata.items()},
            "cases": cases, "new_model_calls": 0, "native_scores_modified": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
