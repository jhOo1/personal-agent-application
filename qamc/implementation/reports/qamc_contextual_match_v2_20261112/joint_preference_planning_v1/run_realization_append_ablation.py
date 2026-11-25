"""Native same-draft comparison of the main answer with and without compiled additions."""
from argparse import ArgumentParser
import json
from pathlib import Path

from qamc.common import parse_object, sha

import decision_realization as method
import run_decision_realization as parent
from settle_decision_realization import checked
from settle_joint_planning import subsets, usage


OUT = parent.OUT.with_name("decision_realization_append_ablation_v1")
RUN = parent.RUN.with_name(OUT.name)
JUDGE = parent.JUDGE
MAIN_ONLY = "SAME_DRAFT_MAIN_ONLY"
probe, read, v42 = parent.probe, parent.read, parent.v42


def changed_answers(rows):
    """Return distinct main answers using the frozen compiler and the single saved draft."""
    changed = {}
    for row in rows:
        actor = row["actor"][method.SEGMENTED]
        selection = row["selection"]
        if selection.get("route") != "SEGMENTED" or actor["status"] != "OK":
            continue
        compiled, added, rejected = method.compile_answer(actor["raw"], selection["uses"], method.SEGMENTED)
        if (compiled, added, rejected) != (actor["answer"], actor["appended_sources"], actor["rejected_adjustments"]):
            raise ValueError("The saved structured answer differs from deterministic compilation")
        main = parse_object(actor["raw"])["main_answer"]
        if main != compiled:
            if not added or not compiled.startswith(main + "\n\n"):
                raise ValueError("The intervention changed the main answer or lacked an approved addition")
            changed[row["uid"]] = (main, compiled, added, actor["request_sha256"])
    return changed


def prepare():
    frozen, rows, _ = checked()
    selected = changed_answers(rows)
    if len(selected) > 80:
        raise ValueError("Adjunct grading exceeded the observed frozen treatment count")
    cohort = OUT / "ACTOR_COHORT.json"
    actor_only = read(cohort)
    differences = {uid: {"main_sha256": sha(main), "compiled_sha256": sha(compiled),
                         "actor_request_sha256": digest, "appended_sources": added}
                   for uid, (main, compiled, added, digest) in selected.items()}
    if (actor_only["changed_answers"] != differences
            or actor_only["actor_exact_sha256"] != sha((parent.OUT / "Actor_EXACT.json").read_bytes())
            or actor_only["selector_exact_sha256"] != sha((parent.OUT / "Selector_EXACT.json").read_bytes())):
        raise ValueError("Settled treatment differs from the Actor-only checkpoint")
    spec = {
        "assigned": frozen["assigned"], "source_groups": frozen["source_groups"],
        "service_reference_sha256": frozen["service_reference_sha256"],
        "diagnostic_source_groups": frozen["diagnostic_source_groups"],
        "caps": {JUDGE: len(selected)}, "independent_confirmation": False,
        "changed_answers": differences,
        "input_hashes": {
            path.name: sha(path.read_bytes()) for path in (
                Path(__file__), Path(__file__).with_name("REALIZATION_APPEND_PROTOCOL.md"),
                Path(method.__file__), Path(parent.__file__), cohort, parent.OUT / "FROZEN.json",
                parent.OUT / "SETTLED.json", parent.OUT / "RESULTS.json",
                parent.joint.prior.formal.OUT / "PLAN.json",
            )
        },
    }
    return spec, rows, selected


def grading_jobs(selected):
    formal = read(parent.joint.prior.formal.OUT / "PLAN.json")
    cases = parent.joint.prior.author_cases(formal)
    return [(uid, MAIN_ONLY, parent.joint.parent.grade_request(formal, cases[uid], values[0]))
            for uid, values in selected.items()]


def merge(rows, jobs, returned):
    job_hash = {uid: sha(wire) for uid, _, wire in jobs}
    merged = []
    for row in rows:
        uid = row["uid"]
        native = dict(row["native"])
        if uid not in job_hash:
            native[MAIN_ONLY] = {**native[method.SEGMENTED], "reuse": method.SEGMENTED}
        else:
            record, raw = returned[uid, MAIN_ONLY]
            if record["request_sha256"] != job_hash[uid]:
                raise ValueError("Main-only grade returned for a different answer")
            native[MAIN_ONLY] = parent.joint.parent.parse_grade(record, raw, row["positions"])
        merged.append({**{key: row[key] for key in ("uid", "group", "labels", "positions", "less_exposed")},
                       "appended": uid in job_hash, "native": native})
    return merged


def report(spec, rows, physical):
    panels = subsets(rows, spec)
    panels["changed_answers"] = [row for row in rows if row["appended"]]
    arms = (MAIN_ONLY, method.DIRECT)
    comparisons = {name: {control: {
        "match": v42.paired(panel, control, method.SEGMENTED),
        **{field: parent.joint.parent.comparisons.grade_pair(panel, control, method.SEGMENTED, field)
           for field in (*parent.joint.SUPPORT, "VG")},
    } for control in arms} for name, panel in panels.items()}
    actual = usage(physical)
    if actual["requests"] > spec["caps"][JUDGE]:
        raise ValueError("Exceeded the frozen grading cap")
    return {"assigned": spec["assigned"], "appended_roots": sum(row["appended"] for row in rows),
            "independent_confirmation": False, "new_generation_requests": 0,
            "actual_native_grading_requests": actual, "comparisons": comparisons}


def main(action):
    design, rows, selected = prepare()
    path = OUT / "FROZEN.json"
    if action == "preview":
        print(json.dumps({"assigned": design["assigned"], "caps": design["caps"]}, indent=2))
        return
    if action == "freeze":
        probe.freeze(path, design)
        return
    live = action == "run"
    if read(path) != design or (live and probe.read_reference()[1] != design["service_reference_sha256"]):
        raise ValueError("The ablation or gateway no longer matches the freeze")
    prior_archive = read(parent.joint.prior.OUT / "FROZEN.json")
    inherited = v42.old_receipts(prior_archive)[JUDGE]
    experiments = (parent.joint.parent.OUT, parent.joint.OUT,
                   parent.OUT.with_name("rp_seed_minimal_revision_rpeval_v1"),
                   parent.OUT.with_name("focal_memory_rpeval_v1"), parent.OUT)
    for experiment in experiments:
        for digest, pair in read(experiment / f"{JUDGE}_EXACT.json").items():
            if digest != pair[0]["request_sha256"]:
                raise ValueError("An inherited Judge receipt is attributed to the wrong request")
            inherited.setdefault(digest, pair)
    probe.OUT, probe.RUN, v42.OUT = OUT, RUN, OUT
    jobs = grading_jobs(selected)
    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": design["caps"]})
    try:
        judged = v42.execute_stage(design, "main", JUDGE, jobs, inherited, live)
        if any(record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in judged.values()):
            raise RuntimeError("Ablation grading returned an unsettled delivery")
        final = merge(rows, jobs, judged)
        records = [record for record, _ in probe.stage_receipts(JUDGE).values()]
        probe.freeze(OUT / "SETTLED.json", {"rows": final, "ledger": records})
        probe.freeze(OUT / "RESULTS.json", report(design, final, records))
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(records)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "freeze", "run", "report"))
    arg = parser.parse_args().action
    if arg in ("freeze", "run"):
        with probe.runner_lock(RUN / "runner.lock"):
            main(arg)
    else:
        main(arg)
