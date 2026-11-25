"""Continue the open-condition comparison with an identical text wire in both arms."""
from argparse import ArgumentParser
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import open_condition_text_wire as method
import run_open_condition_planning as previous


BASE = previous.BASE.with_name("open_condition_text_rpeval_v2")
RUN = previous.RUN.with_name(BASE.name)
probe, read, runtime, replay = previous.probe, previous.read, previous.runtime, previous.replay


def prepare(reference, phase):
    old_state = previous.BASE / "smoke" / "RUN_STATE.json"
    old_settlement = previous.BASE / "smoke" / "SETTLED.json"
    if read(old_state)["state"] != "COMPLETE":
        raise ValueError("The previous smoke must have a terminal receipt set")
    spec, jobs, roots, (rows, official, cases), _, cache = previous.prepare(reference, "main")
    old = {row["uid"] for row in read(old_settlement)["rows"]}
    if old & roots.keys() or len(old) != 14:
        raise ValueError("The text-wire panel overlaps previously generated items")
    selected, groups = set(), set()
    for uid in sorted(roots, key=lambda key: sha(["open_condition_text_wire_v2", key])):
        group = roots[uid]["group"]
        if group in groups:
            continue
        selected.add(uid)
        groups.add(group)
        if len(selected) == 14:
            break
    if len(selected) != 14:
        raise ValueError("Insufficient source diversity for the text-wire smoke")
    roots = {uid: root for uid, root in roots.items() if (uid in selected) == (phase == "smoke")}
    rows = {uid: rows[uid] for uid in roots}
    jobs = [job for job in jobs if job[0] in roots]
    caps = {previous.GOALS: len(jobs), previous.ACTOR: 2 * len(jobs), previous.JUDGE: 2 * len(jobs)}
    names = (Path(__file__), Path(method.__file__), Path(runtime.__file__), BASE / "RECOVERY_PROTOCOL.md")
    spec.update(panel=f"open_condition_text_{phase}", caps=caps, text_wire_smoke=sorted(selected),
                prior_strict_receipt_sha256=sha(old_settlement.read_bytes()),
                wire_shas={uid: sha(wire) for uid, _, wire in jobs}, comparison_rows_sha256=sha(rows))
    spec["code_sha256"].update({path.name: sha(path.read_bytes()) for path in names})
    return spec, jobs, roots, (rows, official, cases), None, cache


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    parser.add_argument("phase", choices=("smoke", "main"))
    args = parser.parse_args()
    action, phase = args.action, args.phase
    out, run = BASE / phase, RUN / phase
    frozen = out / "FROZEN.json"
    reference = probe.read_reference()[1] if action == "freeze" else read(frozen)["service_reference_sha256"]
    inputs = prepare(reference, phase)
    probe.OUT, probe.RUN, replay.OUT = out, run, out
    with (
        probe.runner_lock(run / "runner.lock"),
        patch.object(previous, "method", method),
        patch.object(runtime, "OUT", out),
        patch.object(runtime, "evaluate", previous.evaluate),
        patch.object(runtime, "summarize", previous.summarize),
    ):
        if action == "freeze":
            runtime.manifest(inputs[0]["panel"], previous.GOALS, inputs[1])
            probe.freeze(frozen, inputs[0])
            print(json.dumps(inputs[0]["caps"]))
            return
        state = out / "RUN_STATE.json"
        done = state.exists() and read(state)["state"] == "COMPLETE"
        if action == "run" and not done:
            runtime.execute(inputs, live=True)
        if action == "verify":
            if not done:
                raise ValueError("Comparison has not settled")

            def exact(path, value):
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError(f"Replay differs in {path.name}")

            with patch.object(probe, "freeze", exact):
                runtime.execute(inputs, live=False)
            print(json.dumps({"verified": True, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
