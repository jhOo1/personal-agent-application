"""Recover mechanically verifiable task contracts from the archived stream."""
from argparse import ArgumentParser
import json
from pathlib import Path
import re
from unittest.mock import patch

from qamc.common import sha

import run_task_conditioned_value as original


OUT = original.OUT / "contract_recovery"
RUN = original.RUN / "contract_recovery"
PILOT = original.OUT / "pilot"
probe, read = original.probe, original.read
validate = original.method.contract
NAME = re.compile(r'("choice"\s*:\s*")([^\r\n]*?)("\s*,\s*"task_quote"\s*:)')
ELLIPSIS = re.compile(r"…+|\.{3,}")


def unique_expanded_quote(task, quote):
    parts = ELLIPSIS.split(quote)
    if len(parts) != 2 or not all(parts):
        return quote
    pattern = re.compile(rf"(?=({re.escape(parts[0])}.{{0,80}}?{re.escape(parts[1])}))")
    matches = {m[1] for field in original.method.task_text(task) for m in pattern.finditer(field)}
    return matches.pop() if len(matches) == 1 else quote


def decode(task, raw):
    try:
        return validate(task, raw), []
    except ValueError:
        pass
    source = raw.strip().removeprefix("```json").removesuffix("```").strip()
    repairs = []
    try:
        decoded = json.loads(source)
    except json.JSONDecodeError:
        def quote_name(match):
            name = match[2]
            if "\\" in name or '"' not in name:
                return match[0]
            repairs.append("ESCAPE_INTERIOR_CHOICE_QUOTES")
            return match[1] + name.replace('"', r'\"') + match[3]

        source = NAME.sub(quote_name, source)
        try:
            decoded = json.loads(source)
        except json.JSONDecodeError as error:
            if error.pos != len(source) or not source.endswith("]"):
                raise
            decoded = json.loads(source + "}]}")
            if len(decoded.get("decisions", [])) != 8:
                raise ValueError("A response below the decision limit may be incomplete")
            repairs.append("CLOSE_LAST_RECORD_AND_ENVELOPE_AT_LIMIT")

    for row in decoded["decisions"]:
        before = row["task_quote"]
        if not any(before in field for field in original.method.task_text(task)):
            after = unique_expanded_quote(task, before)
            if after != before:
                row["task_quote"] = after
                repairs.append({"kind": "EXPAND_UNIQUE_TASK_QUOTE", "original": before, "resolved": after})
    return validate(task, json.dumps(decoded, ensure_ascii=False)), repairs


def prepare():
    inputs = original.prepare("pilot")
    spec, jobs, _, _, _, _ = inputs
    received = read(PILOT / (original.CONTRACT + "_EXACT.json"))
    repairs = {}
    for key, _, wire in jobs:
        digest = sha(wire)
        receipt, raw = received[digest]
        if receipt["request_sha256"] != digest or receipt["status"] != "OK":
            raise ValueError("Unexpected contract receipt")
        task = json.loads(wire["messages"][1]["content"])["task"]
        choices, changes = decode(task, raw)
        if changes:
            repairs[key] = {"received_sha256": sha(raw), "decoded_sha256": sha(choices),
                            "changes": changes, "affected_histories": sum(k["task"] == key for k in spec["roster"].values())}
    missing = sum(row["affected_histories"] for row in repairs.values())
    policy = {"previous_freeze_sha256": sha(spec), "contract_receipt_sha256": sha(received), "repairs": repairs,
              "code_sha256": sha(Path(__file__).read_bytes()), "scope": "engineering_completion",
              "caps": {original.CONTRACT: 0, original.ANSWER: 2 * missing, original.JUDGE: 2 * missing},
              "independent_confirmation": False}
    return inputs, policy


def execute(inputs, policy, action):
    if policy != read(OUT / "RECOVERY_PLAN.json"):
        raise ValueError("The planned repairs changed")
    if read(PILOT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The original experiment has not settled")
    spec, jobs, roots, data, settled, caches = inputs
    cache = {name: {**old, **read(PILOT / (name + "_EXACT.json"))} for name, old in caches.items()}
    spec = {**spec, "caps": policy["caps"], "contract_recovery_sha256": sha(policy),
            "inherited_sha256": {name: sha(records) for name, records in cache.items()}}
    probe.OUT, probe.RUN = OUT, RUN
    state = OUT / "RUN_STATE.json"
    with probe.runner_lock(original.RUN / "pilot" / "runner.lock"), probe.runner_lock(RUN / "runner.lock"):
        with patch.object(original.method, "contract", lambda task, raw: decode(task, raw)[0]):
            if action == "run" and not (state.exists() and read(state)["state"] == "COMPLETE"):
                probe.freeze(OUT / "FROZEN.json", spec)
                original.execute((spec, jobs, roots, data, settled, cache), live=True)
            else:
                if read(state)["state"] != "COMPLETE":
                    raise ValueError("Recovery is not settled")

                def compare(path, value):
                    if read(path) != json.loads(json.dumps(value)):
                        raise ValueError(f"Stored recovery differs at {path.name}")

                with patch.object(probe, "freeze", compare):
                    original.execute((spec, jobs, roots, data, settled, cache), live=False)
                print(json.dumps({"state": "VERIFIED", "physical_requests": 0}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    action = parser.parse_args().action
    inputs, policy = prepare()
    if action == "freeze":
        probe.freeze(OUT / "RECOVERY_PLAN.json", policy)
        print(json.dumps({"repairs": len(policy["repairs"]), "caps": policy["caps"], "physical_requests": 0}))
    else:
        execute(inputs, policy, action)
