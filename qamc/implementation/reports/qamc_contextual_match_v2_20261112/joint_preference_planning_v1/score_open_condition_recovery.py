"""Score recoverable text-wire smoke answers without dispatching Selector or Actor requests."""
from argparse import ArgumentParser
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

from open_condition_codec_recovery import recover
import run_open_condition_text as pilot


OUT = pilot.BASE / "smoke" / "compatibility_score"
RUN = pilot.RUN / "smoke" / "compatibility_score"
previous = pilot.previous
probe, read, runtime, replay = pilot.probe, pilot.read, pilot.runtime, pilot.replay
method, scorer = pilot.method, previous.scorer
JUDGE = previous.JUDGE


def prepare(reference):
    root = pilot.BASE / "smoke"
    if read(root / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Wait for all original smoke receipts")
    old_config = read(root / "FROZEN.json")
    spec, _, roots, (archive, official, cases), _, cache = pilot.prepare(reference, "smoke")
    if spec != old_config:
        raise ValueError("Original smoke allocation changed")
    old_path = root / "SETTLED.json"
    saved = read(old_path)
    original = {row["uid"]: row for row in saved["rows"]}
    exact = read(root / (previous.ACTOR + "_EXACT.json"))
    old_grades = read(root / (JUDGE + "_EXACT.json"))
    for digest, item in old_grades.items():
        if item[0]["request_sha256"] != digest or (digest in cache[JUDGE] and cache[JUDGE][digest][1] != item[1]):
            raise ValueError("Conflicting original judge receipt")
    inherited = {**cache[JUDGE], **old_grades}
    rows, actor_manifest = {}, read(root / (previous.ACTOR + "_MANIFEST.json"))["units"]
    choices = saved["contracts"]
    for uid in roots:
        rows[uid] = {**archive[uid], "outputs": {}, "actor": {},
                     "strict_actor_status": {arm: value["status"] for arm, value in original[uid]["actor"].items()}}
    judges = []
    for entry in actor_manifest:
        uid, arm = (entry["unit"][key] for key in ("root_id", "method"))
        packet = roots[uid]
        conditions = choices[uid]["conditions"]
        expected = method.actor_request(packet["public_task"], packet["original_sources"], conditions, arm)
        digest = sha(expected)
        if sha(entry["request"]) != digest or original[uid]["actor"][arm]["request_sha256"] != digest:
            raise ValueError("Original Actor receipt has different inputs")
        receipt, raw = exact[digest]
        if receipt["request_sha256"] != digest:
            raise ValueError("Actor receipt and manifest differ")
        row = rows[uid]
        state = row["actor"][arm] = {"status": receipt["status"], "request_sha256": digest}
        if state["status"] != "OK":
            row["native"][arm] = {"fields": {}, "status": state["status"]}
            continue
        try:
            plan = recover(packet["public_task"], conditions, raw, receipt)
        except ValueError as error:
            state.update(status="INVALID_COMPATIBLE_CONTRACT", error=str(error))
            row["native"][arm] = {"fields": {}, "status": state["status"]}
            continue
        strict = original[uid]["actor"][arm].get("plan")
        if strict is not None and plan != strict:
            raise ValueError("A valid original plan changed during replay")
        state.update(plan=plan, recovery="IDENTICAL" if strict is not None else "COMPATIBLE")
        answer = row["outputs"][arm] = plan["answer"]
        judges.append((uid, arm, scorer.grade_request(official, cases[uid], answer)))
    if len(judges) > 2 * len(roots):
        raise ValueError("Scoring roster exceeds the original experiment")
    files = (Path(__file__), Path(recover.__code__.co_filename), Path(method.__file__), old_path)
    spec = {"panel": "text_wire_compatibility_on_saved_smoke", "caps": {JUDGE: len(judges)},
            "service_reference_sha256": reference, "thresholds": old_config["thresholds"],
            "sha256": {file.name: sha(file.read_bytes()) for file in files},
            "judge_sha256": {uid + "/" + arm: sha(wire) for uid, arm, wire in judges},
            "judge_cache_sha256": sha(inherited), "independent_confirmation": False}
    return spec, judges, roots, rows, choices, {JUDGE: inherited}


def evaluate(inputs, stage):
    _, jobs, _, rows, goals, _ = inputs
    for (uid, arm), (receipt, raw) in stage(JUDGE, jobs).items():
        rows[uid]["native"][arm] = scorer.parse_grade(receipt, raw, rows[uid]["positions"])
    return goals, list(rows.values())


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    action = parser.parse_args().action
    frozen = OUT / "FROZEN.json"
    reference = probe.read_reference()[1] if action == "freeze" else read(frozen)["service_reference_sha256"]
    inputs = prepare(reference)
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT
    with (
        probe.runner_lock(RUN / "runner.lock"),
        patch.object(runtime, "OUT", OUT),
        patch.object(runtime, "evaluate", evaluate),
        patch.object(runtime, "summarize", previous.summarize),
    ):
        if action == "freeze":
            probe.freeze(frozen, inputs[0])
            print(json.dumps(inputs[0]["caps"]))
            return
        terminal = OUT / "RUN_STATE.json"
        done = terminal.exists() and read(terminal)["state"] == "COMPLETE"
        if action == "run" and not done:
            runtime.execute(inputs, live=True)
        if action == "verify":
            if not done:
                raise ValueError("Wait for score receipts")

            def exact(path, value):
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError(f"Replay differs in {path.name}")

            with patch.object(probe, "freeze", exact):
                runtime.execute(inputs, live=False)
            print(json.dumps({"verified": True, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
