"""Trace which V45 statements changed choices and which author positions they cite."""
from collections import Counter, defaultdict
import json

from qamc.common import canonical, parse_object
from qamc_rpeval_terminal_judge_sensitivity import inspect, pair_bounds

import analyze_decision_witness_v45 as scoring

run = scoring.run


def audit(rows):
    parent = run.read(run.stage.prior.OUT / "FROZEN.json")
    drafts = scoring.archived.task.saved_drafts(parent)
    roots = {item["uid"]: item for item in parent["roots"]}
    counters, witnesses = defaultdict(Counter), []
    for row in rows:
        witness = row["witness"]
        if witness["status"] != "COMPILED":
            continue
        uid, labels = row["uid"], row["labels"]
        root = roots[uid]
        source_ids = [src["memory_id"] for src in root["original_sources"]]
        if len(source_ids) != len(set(source_ids)) or len(source_ids) != len(labels):
            raise ValueError("Raw source to author position alignment changed")
        labels_by_id = dict(zip(source_ids, labels, strict=True))
        before, after = witness["fallback"], witness["anchored"]["source"]
        shape = witness["shape_only"]["source"]
        scope = "all_A" if set(labels) == {"A"} else "contains_BC"
        body = run.contract.packet(root, root["archived"][scoring.RP]["answer"], drafts[root["task_wire_sha256"]]["answer"])
        changed = before != after
        rejected = {e["index"] for e in witness["rejected"]}
        accepted = {canonical(effect): effect for i, effect in enumerate(run.contract.parse(witness["raw"]))
                    if i not in rejected}
        references = Counter(effect["kind"] + ":" + labels_by_id[effect["memory"]["id"]]
                             for effect in accepted.values() if effect["memory"])
        for tag in ("all", scope):
            counters[tag].update(compiled=1, changed_from_prior=changed, changed_from_shape=after != shape)
            counters[tag].update(references)
        for control in (scoring.C_PRIOR, scoring.GENERIC, scoring.SHAPE):
            native = [row["native"][method] for method in (control, scoring.ANCHORED)]
            matches = [r["fields"].get("match") for r in native]
            if not all(matches):
                continue
            raw_choice = {
                scoring.C_PRIOR: before, scoring.ANCHORED: after,
                scoring.SHAPE: shape, scoring.GENERIC:
                    "SOURCE_RP" if row["choices"][scoring.GENERIC].get("source") == scoring.RP else "CURRENT_TASK_ONLY",
            }
            options = {c["generation_context"]: c["answer"] for c in body["candidates"]}
            evidence = {}
            for method, cell in zip((control, scoring.ANCHORED), native, strict=True):
                evidence[method] = inspect({"uid": uid, "method": method, "native_fields": cell["fields"],
                                            "answer": options[raw_choice[method]],
                                            "raw_scores": {run.stage.JUDGE: cell["raw"]}}, labels)
            bounds = pair_bounds(evidence[scoring.ANCHORED], evidence[control])
            delta = matches[1]["matched"] - matches[0]["matched"]
            for tag in (f"{control}:all", f"{control}:{scope}"):
                counters[tag].update(paired=1, delta=delta, min_delta=bounds[0], max_delta=bounds[1],
                                     win=delta > 0, loss=delta < 0, tie=delta == 0,
                                     changed=raw_choice[control] != after)
            if control == scoring.C_PRIOR and changed:
                witnesses.append({
                    "uid": uid, "group": row["group"], "scope": scope, "before": before, "after": after,
                    "delta": delta, "bounds": bounds, "reason": witness["anchored"]["reason"],
                    "source_author_labels_for_evaluation_only": labels_by_id,
                    "evidence_flags": {m: e["flags"] for m, e in evidence.items()},
                    "native_grade_reasons": [parse_object(cell["raw"]).get("reason") for cell in native],
                    "witness": witness,
                })
    return {
        "counts": counters, "real_changes_from_C_prior": witnesses,
        "new_model_requests": 0, "human_reviews": 0,
        "note": "An exact anchor validates the cited text. Author-label comparisons indicate tension only, "
                "rather than certifying semantic errors. Native grades and their missingness are unmodified.",
    }


if __name__ == "__main__":
    _, rows, _ = scoring.collected()
    print(json.dumps(audit(rows), ensure_ascii=False, indent=2))
