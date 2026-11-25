"""Prepare a small blinded answer audit for V43 after the native endpoint."""
from argparse import ArgumentParser
import json
from pathlib import Path
import sys

from qamc.common import sha
from qamc_rpeval_terminal_judge_sensitivity import inspect

import run_policy_override_v43 as stage

sys.path.insert(0, str(stage.OUT.parent / "decision_scoped_policy_v40"))
import behavior_audit as blind

ARCHIVED, CANDIDATE = stage.prior.RP, stage.METHOD
HOME = stage.OUT / "behavior_diagnostic"


def observations(rows, roots):
    for row in rows:
        uid = row["uid"]
        root = roots[uid]
        previous, current = root["archived"][ARCHIVED]["answer"], row["answer"]
        if not row["trace"]["edits"] or not current or previous == current:
            continue
        outcomes = {}
        for method, answer in ((ARCHIVED, previous), (CANDIDATE, current)):
            cell = row["native"][method]
            outcomes[method] = inspect({"uid": uid, "method": method, "answer": answer,
                                        "native_fields": cell["fields"], "raw_scores": {stage.JUDGE: cell["raw"]}},
                                       row["labels"])
        if not all(outcomes.values()):
            continue
        fields = {m: row["native"][m]["fields"] for m in (ARCHIVED, CANDIDATE)}
        changes = {metric: fields[CANDIDATE][metric] - fields[ARCHIVED][metric]
                   if all(metric in value for value in fields.values()) else None
                   for metric in ("UPB", "FM")}
        yield {"root": root, "uid": uid, "group": row["group"], "answers": (previous, current),
               "labels": row["labels"], "edits": row["trace"]["edits"],
               "delta": outcomes[CANDIDATE]["matched"] - outcomes[ARCHIVED]["matched"],
               "upb_increase": changes["UPB"], "quality_decrease": changes["FM"],
               "flags": sum(bool(c["flags"]) for c in outcomes.values())}


def witnesses(items):
    tags = (
        ("all_A_native_gain", lambda x: set(x["labels"]) == {"A"} and x["delta"] > 0,
         lambda x: -x["delta"]),
        ("all_A_native_loss", lambda x: set(x["labels"]) == {"A"} and x["delta"] < 0,
         lambda x: x["delta"]),
        ("removed_author_B", lambda x: any(
            label == "B" and x["edits"].get(src["memory_id"]) == "A"
            for label, src in zip(x["labels"], x["root"]["original_sources"], strict=True)),
         lambda x: (x["upb_increase"] is None, -(x["upb_increase"] or 0), x["delta"])),
        ("restored_candidate_C", lambda x: "C" in x["edits"].values(),
         lambda x: (-x["delta"], -x["flags"])),
        ("task_quality", lambda x: (x["quality_decrease"] or 0) > 0, lambda x: -x["quality_decrease"]),
        ("judge_field_dispute", lambda x: x["flags"] > 0, lambda x: (-x["flags"], -abs(x["delta"]))),
    )
    picked, groups = {}, set()
    for tag, keep, metric in tags:
        current = [entry for entry in items if entry["group"] not in groups and keep(entry)]
        if current:
            best = min(current, key=lambda x: (metric(x), sha(["v43-audit-20261119", tag, x["uid"]])))
            picked[tag] = best
            groups.add(best["group"])
    return picked


def prepare(rows, roots):
    available = list(observations(rows, roots))
    picked = witnesses(available)
    paired = [{"uid": entry["uid"], "answers": {
        m: {"answer": text} for m, text in zip((blind.GLOBAL, blind.SCOPED), entry["answers"], strict=True)
    }} for entry in picked.values()]
    form = blind.prepare({"roots": [entry["root"] for entry in picked.values()]}, paired)
    form.pop("max_physical_requests")
    return {**form, "eligible_edited_roots": len(available), "maximum_requests": len(form["packets"]),
            "picked": {tag: entry["uid"] for tag, entry in picked.items()},
            "method_by_role": {blind.GLOBAL: ARCHIVED, blind.SCOPED: CANDIDATE},
            "labels_for_postprocessing_only": {
                entry["uid"]: dict(zip((src["memory_id"] for src in entry["root"]["original_sources"]),
                                       entry["labels"], strict=True))
                for entry in picked.values()
            }}


def collect(plan, votes):
    result = blind.settled_votes(plan, votes, plan["labels_for_postprocessing_only"])
    return {**result, "requested_packets": len(plan["packets"]), "valid_votes": len(votes),
            "method_by_role": plan["method_by_role"],
            "interpretation": "Targeted two-order automated audit. Do not infer population rates.",
            "human_adjudications": 0, "native_scores_changed": 0}


def freeze():
    if stage.read(stage.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The behavior audit needs terminal V43 evidence")
    pinned, roots = stage.prepare()
    if stage.read(stage.OUT / "FROZEN.json") != pinned:
        raise ValueError("V43 plan changed")
    result = stage.read(stage.OUT / "COMPLETED.json")
    if [row["uid"] for row in result["rows"]] != [root["uid"] for root in pinned["roots"]]:
        raise ValueError("V43 terminal case identities changed")
    report = prepare(result["rows"], roots)
    stage.probe.freeze(HOME / "FROZEN.json", {
        **report, "v43_results_sha256": sha((stage.OUT / "COMPLETED.json").read_bytes())})
    return {key: report[key] for key in ("eligible_edited_roots", "maximum_requests", "picked")}


def execute(plan):
    """Use the existing Judge transport, stopping this optional audit on transport failure."""
    result = stage.OUT / "COMPLETED.json"
    if sha(result.read_bytes()) != plan["v43_results_sha256"]:
        raise ValueError("The frozen behavior sample refers to a different V43 result")
    live_home = stage.RUN / "behavior_diagnostic"
    selected = [
        plan["picked"][reason] for reason in ("removed_author_B", "all_A_native_gain", "all_A_native_loss",
                                              "restored_candidate_C") if reason in plan["picked"]
    ]
    schedule = [name for uid in selected for name, packet in plan["packets"].items()
                if any(row["uid"] == uid for row in packet["identities"].values())]
    probe = stage.probe
    frozen = stage.read(stage.OUT / "FROZEN.json")
    with probe.runner_lock(live_home / "runner.lock"):
        probe.freeze(HOME / "DISPATCH_SCOPE.json", schedule)
        observed, votes = {}, {}
        for name in schedule:
            packet = plan["packets"][name]
            if sha(packet["wire"]) != packet["request_sha256"]:
                raise ValueError("Blind request digest changed")
            probe.OUT, probe.RUN = HOME / "dispatch" / sha(name), live_home
            probe.CAP = {"Blind": 1}
            probe.answer_grid = lambda *_: {name: {"ready": True}}
            probe.blind_wire = lambda *_: packet["wire"]
            probe.validate_blind = blind.validate
            probe.blind({"roots": [{"uid": name}], "service_reference_sha256": frozen["service_reference_sha256"]})
            folder = live_home / "Blind" / sha(name)
            receipt = stage.read(folder / "record.json")
            if receipt["request_sha256"] != packet["request_sha256"]:
                raise ValueError("Blind receipt request digest changed")
            observed[name] = receipt
            if receipt["status"] == "OK":
                votes[name] = stage.read(folder / "vote.json")
            elif receipt["status"] != "INVALID_JUDGE_OUTPUT":
                break
        return {**collect(plan, votes), "dispatch_cap": len(schedule), "receipts": observed,
                "votes": votes, "observed_physical_requests": len(observed)}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    parser.add_argument("--votes", type=Path)
    args = parser.parse_args()
    if args.action == "freeze":
        value = freeze()
    elif args.action == "run":
        value = execute(stage.read(HOME / "FROZEN.json"))
        stage.probe.freeze(HOME / "RESULTS.json", value)
    else:
        votes = stage.read(args.votes) if args.votes else {}
        value = collect(stage.read(HOME / "FROZEN.json"), votes)
    print(json.dumps(value, ensure_ascii=False, indent=2))
