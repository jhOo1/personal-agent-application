"""Quantify RPEval score sensitivity and compare unchanged archived strong controls."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from argparse import ArgumentParser

from qamc.common import sha
from qamc_rpeval_terminal_judge_sensitivity import inspect, pair_bounds

from audit_completed import audited_rows
from audit_visibility_v42 import replay_stage
from label_bounds import add_pair, cell_bounds
import run_policy_override_v43 as stage

REVIEW = "REVIEW"
FULL = "SCOPED_FULL"
EDIT_GROUPS = {frozenset("A"): "B_to_A_only", frozenset("C"): "B_to_C_only",
               frozenset("AC"): "both_edit_directions"}


def verify_receipts(plan, result, roots):
    cache = stage.inherited_receipts(plan)
    prior, probe = stage.prior, stage.probe
    original = stage.read(prior.formal.OUT / "PLAN.json")
    cases = prior.author_cases(original)
    archived = {r["archived_actor_sha256"]: r["archived"][prior.RP]["answer"]
                for r in roots.values() if r["archived"][prior.RP]["answer"]}
    actors, judges, hashes = [], [], {}
    for row in result["rows"]:
        uid, trace, answer = row["uid"], row["trace"], row["answer"]
        if trace["edits"]:
            wire = stage.policy_only_request(roots[uid], trace["edits"])
            if sha(wire) != trace["actor_sha256"]:
                raise ValueError("Compiled Actor request differs from the recorded intervention")
            if trace["actor_sha256"] in archived:
                if answer != archived[trace["actor_sha256"]]:
                    raise ValueError("Actor reused the wrong archived answer")
            else:
                actors.append((uid, stage.METHOD, wire))
        cell = row["native"][stage.METHOD]
        if not answer or cell.get("reuse"):
            continue
        proposed = {"uid": uid, "method": prior.GATE, "actor_status": "OK", "answer": answer}
        job, = prior.formal.grading_jobs(original, [cases[uid]], [proposed])
        wire = job["request"]
        hashes[uid] = sha(wire)
        if cell["judge_sha256"] != hashes[uid]:
            raise ValueError("Native Judge input differs from the recorded intervention")
        judges.append((uid, stage.METHOD, wire))

    counts, recovered = Counter(), []
    previous = stage.v42.OUT, probe.OUT, probe.RUN
    stage.v42.OUT, probe.OUT, probe.RUN = stage.OUT, stage.OUT, stage.RUN
    try:
        for name, jobs in ((stage.ACTOR, actors), (stage.JUDGE, judges)):
            physical = replay_stage("main", name, jobs, cache, counts)
            recovered.extend(receipt for receipt, _ in physical.values())
    finally:
        stage.v42.OUT, probe.OUT, probe.RUN = previous
    if recovered != result["ledger"]:
        raise ValueError("V43 completed ledger differs from the original receipt files")
    for row in result["rows"]:
        uid, trace = row["uid"], row["trace"]
        if trace["edits"] and trace["actor_sha256"] not in archived:
            receipt, raw = cache[stage.ACTOR][trace["actor_sha256"]]
            if (row["answer"], row["actor_status"]) != (raw, receipt["status"]):
                raise ValueError("V43 stored answer diverged from its actual Actor receipt")
        if uid in hashes:
            receipt, raw = cache[stage.JUDGE][hashes[uid]]
            cell = row["native"][stage.METHOD]
            if cell["raw"] != raw:
                raise ValueError("V43 stored raw grade diverged from its actual Judge receipt")
            if cell.get("fields"):
                fields, _ = probe.fields(stage.parse_object(raw), row["positions"], True)
                if fields != cell["fields"]:
                    raise ValueError("V43 stored parsed grade changed")
    return counts


def checked_rows(plan, result, roots):
    v41 = stage.read(stage.prior.OUT / "FROZEN.json")
    earlier = {row["uid"]: row for rows, _ in audited_rows(v41) for row in rows}
    current = {}
    for witness in plan["input_sources"]:
        file = stage.v42.OUT / f"wave_{witness['wave']:02d}" / "COMPLETED.json"
        if sha(file.read_bytes()) != witness["sha256"]:
            raise ValueError("V42 reference wave changed")
        current.update({row["uid"]: row for row in stage.read(file)["rows"]})
    if len(earlier) != 233 or len(current) != 233:
        raise ValueError("Wide archived review controls are incomplete")
    for frozen, row in zip(plan["roots"], result["rows"], strict=True):
        uid = frozen["uid"]
        if (row["trace"] != frozen or row["uid"] != uid or row["group"] != frozen["group"]
                or row["labels"] != earlier[uid]["labels"] or row["labels"] != current[uid]["labels"]):
            raise ValueError("Frozen alignment of roots, groups or author labels failed")
        candidate = row["native"][stage.METHOD]
        baseline = roots[uid]["archived"][stage.prior.RP]
        if not frozen["edits"] and (row["answer"], candidate["raw"], candidate["fields"], candidate["reuse"]) != (
            baseline["answer"], baseline["raw_judge"], baseline["fields"], stage.prior.RP
        ):
            raise ValueError("No-op changed the archived Actor answer or Judge")
        native = {**row["native"], REVIEW: earlier[uid]["native"][REVIEW],
                  FULL: current[uid]["native"][FULL]}
        answers = {name: cell["answer"] for name, cell in roots[uid]["archived"].items()}
        answers.update({REVIEW: earlier[uid]["answers"][REVIEW]["answer"],
                        FULL: current[uid]["answers"][FULL]["answer"], stage.METHOD: row["answer"]})
        yield {**row, "native": native}, answers


def analyze(rows):
    methods = (stage.prior.RP, stage.prior.GATE, REVIEW, FULL)
    parts, diagnostic = defaultdict(list), defaultdict(lambda: defaultdict(Counter))
    flags = defaultdict(Counter)
    for row, answers in rows:
        labels = row["labels"]
        tags = ["all", "all_A" if set(labels) == {"A"} else "contains_BC",
                "reviewed_prefix" if row["trace"]["parent_wave"] <= 4 else "later_prefix"]
        actions = frozenset(row["trace"]["edits"].values())
        if actions:
            tags.extend(("edited", EDIT_GROUPS[actions]))
        bounds, judged = {}, {}
        for method, cell in row["native"].items():
            bounds[method] = cell_bounds(labels, cell["fields"])
            judged[method] = inspect({"uid": row["uid"], "method": method,
                                      "native_fields": cell["fields"], "answer": answers[method],
                                      "raw_scores": {stage.JUDGE: cell["raw"]}}, labels)
            flags[method].update(judged[method]["flags"] if judged[method] else ["missing_match"])
        for tag in tags:
            parts[tag].append(row)
        for baseline in methods:
            old, new = judged[baseline], judged[stage.METHOD]
            if old is None or new is None:
                continue
            identity = (old["answer_sha256"], old["judge_sha256"]) == (new["answer_sha256"], new["judge_sha256"])
            low, high = pair_bounds(new, old)
            for tag in tags:
                scores = diagnostic[tag, baseline]
                scores["score_dispute"].update(roots=1, positions=len(labels), delta_min=low, delta_max=high,
                                                flagged_roots=bool(old["flags"] or new["flags"]))
                for lens in ("match_only", "bias_conditioned"):
                    before, after = bounds[baseline][lens], bounds[stage.METHOD][lens]
                    if before is not None and after is not None:
                        add_pair(scores[lens], before, after, labels, identity)
    common = [row for row in parts["all"]
              if all(row["native"][m]["fields"].get("match") is not None for m in (*methods, stage.METHOD))]
    common_comparisons = {
        method: stage.v42.paired(common, method, stage.METHOD) for method in methods
    }
    return {"methods": methods, "flag_counts": flags, "model_calls": 0,
            "all_method_common": common_comparisons,
            "scores": {tag: {name: {
                "native_match": stage.v42.paired(part, name, stage.METHOD),
                "native_severity": stage.v42.metric_pairs(part, name, stage.METHOD),
                "identified_ranges": diagnostic[tag, name],
            } for name in methods} for tag, part in parts.items()},
            "evidence": "Model-graded aggregate bounds. These do not certify behavior or actual memory treatment."}


def main():
    if stage.read(stage.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("V43 has no terminal outcomes to audit")
    plan, roots = stage.prepare()
    if stage.read(stage.OUT / "FROZEN.json") != plan:
        raise ValueError("V43 plan or code identity changed")
    result = stage.read(stage.OUT / "COMPLETED.json")
    if len(result["rows"]) != 233 or stage.finish(plan, result["rows"], result["ledger"]) != result["summary"]:
        raise ValueError("Native summary does not reconcile with completed rows and ledger")
    report = analyze(checked_rows(plan, result, roots))
    return {**report, "receipt_reconciliation": verify_receipts(plan, result, roots)}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    outcome = main()
    if args.output:
        with args.output.open("x", encoding="utf-8") as file:
            json.dump(outcome, file, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
