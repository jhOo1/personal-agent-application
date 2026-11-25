"""Replay proposals with mechanically recoverable text framing in a separate run."""
from argparse import ArgumentParser
import json
from pathlib import Path
import re
from unittest.mock import patch

from qamc.common import sha

import decision_replacement as method
import run_decision_replacement as run
from transaction_text_wire import packet_marker


OUT, RUN = run.OUT / "framing_recovery", run.RUN / "framing_recovery"
probe, read = run.probe, run.read
STRICT = method.decode
ID = re.compile(r"T[1-9][0-9]*\Z")
PLAN_FILE = "RECOVERY_PLAN_V2.json"


def text_locations(value):
    for unit in value["units"]:
        for effect in unit["effects"]:
            yield effect["source"], "quote", "SOURCE"
            for key in ("delegation", "base_gap"):
                if effect[key] is not None:
                    yield effect, key, "EVIDENCE"
        for option in unit["options"]:
            yield option, "text", "CANDIDATE"
            for key in option["witnesses"]:
                yield option["witnesses"], key, "WITNESS"


def normalized(raw, marker):
    value, offset = json.JSONDecoder().raw_decode(raw.lstrip())
    if set(value) != {"units"} or not isinstance(value["units"], list) or len(value["units"]) > 8:
        raise ValueError("Cannot identify the proposal metadata")
    rest = raw.lstrip()[offset:]
    locations = list(text_locations(value))
    expected = {entry[key] for entry, key, _ in locations if ID.fullmatch(entry[key])}
    pattern = re.compile("^" + r"(?:" + re.escape(marker) + r" )?(T[1-9][0-9]*|END)( END)?(?:\n|\Z)",
                         re.MULTILINE)
    matches = list(pattern.finditer(rest))
    if rest[:matches[0].start() if matches else len(rest)].strip():
        raise ValueError("Undelimited text before first reference")
    fields, closed = {}, set()
    for i, opening in enumerate(matches):
        key = opening[1]
        end = matches[i + 1].start() if i + 1 < len(matches) else len(rest)
        body = rest[opening.end():end].removesuffix("\n")
        if key == "END" or opening[2]:
            if body.strip() or (key != "END" and (not fields or next(reversed(fields)) != key)):
                raise ValueError("Ambiguous field terminator")
            if fields:
                closed.add(next(reversed(fields)))
            continue
        if key in fields or key not in expected:
            raise ValueError("Unexpected or duplicate text reference")
        next_field = matches[i + 1] if i + 1 < len(matches) else None
        # Allow a single blank separator between bare references only.
        if not opening[0].startswith(marker) and body.endswith("\n"):
            body = body.removesuffix("\n")
        fields[key] = body
        if next_field is not None:
            closed.add(key)
    if fields.keys() != expected:
        raise ValueError("Missing a referenced text block")
    for entry, key, kind in locations:
        field = entry[key]
        if field in fields:
            if field not in closed and kind != "WITNESS":
                raise ValueError("An unclosed text block is not corroborated by a complete candidate")
            continue
        # Some messages put verbatim citations directly in the metadata.
        # Carry those exact decoded strings without editing them.
        ref = "T" + str(max((int(k[1:]) for k in fields), default=0) + 1)
        fields[ref] = field
        entry[key] = ref
    body = [json.dumps(value, ensure_ascii=False), *(f"{marker} {k}\n{v}" for k, v in fields.items()),
            marker + " END"]
    return "\n".join(body)


def decode(raw, marker):
    try:
        return STRICT(raw, marker)
    except (ValueError, TypeError):
        return STRICT(normalized(raw, marker), marker)


def prepare():
    inputs = run.prepare()
    spec, jobs, roots, history, _, _ = inputs
    actual = read(run.OUT / (run.PROPOSAL + "_EXACT.json"))
    recovery = {}
    for uid, _, wire in jobs:
        digest = sha(wire)
        record, raw = actual[digest]
        if record["request_sha256"] != digest or record["status"] != "OK":
            continue
        marker = packet_marker(wire["messages"][1]["content"])
        try:
            STRICT(raw, marker)
        except (TypeError, ValueError):
            if record.get("finish_reason") != "stop":
                continue
            try:
                candidate = normalized(raw, marker)
                outputs, picks, rejected = method.compile_answers(candidate, wire, roots[uid], **history[uid])
            except (ValueError, TypeError, AttributeError, KeyError):
                continue
            recovery[digest] = {"uid": uid, "marker": marker, "raw_sha256": sha(raw), "canonical_sha256": sha(candidate),
                                "output_hashes": {arm: sha(answer) for arm, answer in outputs.items()},
                                "picks": {arm: {str(slot): pick for slot, pick in values.items()}
                                          for arm, values in picks.items()}, "rejected": rejected}
    return inputs, {"original_sha256": sha(spec), "proposal_cache_sha256": sha(actual),
                    "recovery_sha256": sha(Path(__file__).read_bytes()), "repairs": recovery,
                    "caps": {run.PROPOSAL: 0, run.JUDGE: 2 * len(recovery)}, "author_labels_used": False}


def execute(inputs, plan, action):
    if plan != read(OUT / PLAN_FILE) or read(run.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The frozen recovery or original settlement is missing")
    spec, jobs, roots, history, data, cache = inputs
    sources = read(run.OUT / (run.PROPOSAL + "_EXACT.json"))
    cache = {run.PROPOSAL: sources, run.JUDGE: {
        **cache[run.JUDGE], **read(run.OUT / (run.JUDGE + "_EXACT.json"))}}
    spec = {**spec, "caps": plan["caps"], "recovery_sha256": sha(plan), "inherited_sha256": sha(cache)}
    approved = {(entry["raw_sha256"], entry["marker"]): entry["canonical_sha256"] for entry in plan["repairs"].values()}

    def approved_decode(raw, marker):
        key = sha(raw), marker
        if key not in approved:
            return STRICT(raw, marker)
        try:
            candidate = normalized(raw, marker)
        except (TypeError, ValueError) as error:
            raise ValueError("Frozen canonical response changed") from error
        if sha(candidate) != approved[key]:
            raise ValueError("Frozen canonical response changed")
        return STRICT(candidate, marker)

    run.probe.OUT, run.probe.RUN, run.replay.OUT = OUT, RUN, OUT
    with (probe.runner_lock(RUN / "runner.lock"), patch.object(method, "decode", approved_decode),
          patch.object(run.previous, "OUT", OUT), patch.object(run.previous, "evaluate", run.evaluate),
          patch.object(run.previous, "summarize", run.summarize)):
        state = OUT / "RUN_STATE.json"
        done = state.exists() and read(state)["state"] == "COMPLETE"
        if action == "run" and not done:
            probe.freeze(OUT / "FROZEN.json", spec)
            run.previous.execute((spec, jobs, roots, history, data, cache), live=True)
        elif action == "verify":
            if not done:
                raise ValueError("Recovery has not settled")

            def same(path, content):
                if read(path) != json.loads(json.dumps(content)):
                    raise ValueError(f"Recovery replay changed {path.name}")

            with patch.object(probe, "freeze", same):
                run.previous.execute((spec, jobs, roots, history, data, cache), live=False)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    action = parser.parse_args().action
    inputs, plan = prepare()
    if action == "freeze":
        probe.freeze(OUT / PLAN_FILE, plan)
    else:
        execute(inputs, plan, action)
    print(json.dumps({"mechanical_repairs": len(plan["repairs"]), "caps": plan["caps"], "action": action}))
