"""Score only the new combinations from the archived RP-B-only release control."""
from argparse import ArgumentParser
from pathlib import Path

from qamc.common import sha

import audit_optional_release as release_audit
import run_realization_append_ablation as ablation
from settle_decision_realization import checked
from settle_joint_planning import subsets, usage


OUT = ablation.OUT.with_name("decision_optional_release_rpeval_v1")
RUN = ablation.RUN.with_name(OUT.name)
NATIVE = ablation.JUDGE
ARM = "RP_B_RELEASE"
probe, read, v42 = ablation.probe, ablation.read, ablation.v42


def inputs():
    _, rows, _ = checked()
    archive = read(ablation.parent.joint.prior.OUT / "FROZEN.json")
    roots = {r["uid"]: r for r in archive["roots"]}
    base = read(ablation.OUT / "SETTLED.json")["rows"]
    old = {r["uid"]: r for r in base}
    choices = dict.fromkeys(old, ablation.MAIN_ONLY)
    new = {}
    for row in rows:
        uid = row["uid"]
        if not old[uid]["appended"]:
            continue
        _, answer, _, equivalent = release_audit.release(row, roots[uid]["archived_policy"])
        choices[uid] = equivalent
        if equivalent is None:
            new[uid] = (answer,)
    jobs = [(uid, ARM, wire) for uid, _, wire in ablation.grading_jobs(new)]
    frozen = read(ablation.OUT / "FROZEN.json")
    spec = {
        "cap": len({sha(w) for _, _, w in jobs}),
        "grading_wires": {uid: sha(w) for uid, _, w in jobs},
        "service_reference_sha256": frozen["service_reference_sha256"],
        "diagnostic_source_groups": frozen["diagnostic_source_groups"],
        "parents": {path.name: sha(path.read_bytes()) for path in (
            Path(__file__), Path(release_audit.__file__),
            ablation.OUT / "SETTLED.json", ablation.OUT / "FROZEN.json",
            ablation.parent.joint.prior.OUT / "FROZEN.json",
        )},
        "new_generation_requests": 0, "independent_confirmation": False,
    }
    return spec, archive, jobs, choices, base


def run(action):
    spec, archive, jobs, choices, base = inputs()
    path = OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, spec)
        return
    live = action == "run"
    if read(path) != spec or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen optional release inputs or gateway fingerprint changed")
    inherited = v42.old_receipts(archive)[NATIVE]
    for directory in (ablation.parent.joint.parent.OUT, ablation.parent.OUT, ablation.OUT):
        for digest, pair in read(directory / f"{NATIVE}_EXACT.json").items():
            if digest != pair[0]["request_sha256"]:
                raise ValueError("Archived Judge receipt does not match the request")
            inherited.setdefault(digest, pair)
    probe.OUT, probe.RUN, v42.OUT = OUT, RUN, OUT
    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING"})
    try:
        grades = v42.execute_stage(spec, "main", NATIVE, jobs, inherited, live)
        rows = []
        for row in base:
            native = dict(row["native"])
            uid = row["uid"]
            anchor = choices[uid]
            if anchor:
                native[ARM] = {**native[anchor], "reuse": anchor}
            else:
                record, raw = grades[uid, ARM]
                if record["status"] == "PENDING_DELIVERY_UNKNOWN":
                    raise RuntimeError("Retained an indeterminate native scoring receipt")
                if record["request_sha256"] != spec["grading_wires"][uid]:
                    raise ValueError("Scoring receipt does not match the replay answer")
                native[ARM] = ablation.parent.joint.parent.parse_grade(record, raw, row["positions"])
            rows.append({**row, "native": native})
        physical = [r for r, _ in probe.stage_receipts(NATIVE).values()]
        if len(physical) > spec["cap"]:
            raise ValueError("Judging exceeded the pinned physical cap")
        panels = subsets(rows, spec)
        compared = {name: {anchor: {
            "match": v42.paired(panel, anchor, ARM),
            **{field: ablation.parent.joint.parent.comparisons.grade_pair(panel, anchor, ARM, field)
               for field in ("OPB", "UPB", "FM")},
        } for anchor in (ablation.MAIN_ONLY, ablation.method.SEGMENTED, ablation.parent.GATE, ablation.parent.RP)}
            for name, panel in panels.items()}
        probe.freeze(OUT / "RESULTS.json", {"comparisons": compared, "rows": rows, "usage": usage(physical),
                                            "ledger": physical, "new_generation_requests": 0})
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(physical)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    with probe.runner_lock(RUN / "runner.lock"):
        run(parser.parse_args().action)
