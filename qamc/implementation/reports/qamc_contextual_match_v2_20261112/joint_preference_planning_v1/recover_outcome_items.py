"""Re-render archived actors after neutralizing redundant status markers."""
from argparse import ArgumentParser
import json
from pathlib import Path
import re
from unittest.mock import patch

from qamc.common import sha

import run_outcome_contract as run


OUT, RUN = run.OUT / "item_header_recovery", run.RUN / "item_header_recovery"
method, probe, read = run.method, run.probe, run.read
STRICT = method.compile_answer
SOFT_STATUS = re.compile(r"S[1-9]\d*:[A-Z]\Z")


def normalize(raw, uses, choices):
    hard = {u["id"]: set(u["slots"]) for u in uses if u["force"] == "REQUIRE"}
    soft = {u["id"] for u in uses if u["force"] != "REQUIRE"}
    heads = list(method.HEADER.finditer(raw))
    if not heads:
        if hard or "@ITEM" in raw or not raw.strip() or not choices:
            raise ValueError("Response has no unambiguous item boundaries")
        return "@ITEM 1\n" + raw
    parts, previous = [], 0
    for header in heads:
        parts.append(raw[previous:header.start()])
        slots = set() if header[1] == "-" else {int(k) for k in header[1].split(",")}
        applicable = {key for key, targets in hard.items() if targets & slots}
        tokens = header[2].split()
        known = {token.split(":")[0] for token in tokens if method.STATE.fullmatch(token)}
        kept = []
        for token in tokens:
            if SOFT_STATUS.fullmatch(token) and token.split(":")[0] in soft:
                continue
            if token in {"D", "V", "X"} and not applicable - known:
                continue
            # No declared hard condition means no status can affect either
            # answer. Remove syntactically valid but redundant metadata.
            if not hard and method.STATE.fullmatch(token):
                continue
            kept.append(token)
        parts.append(" ".join(["@ITEM", header[1], *kept]) + "\n")
        previous = header.end()
    parts.append(raw[previous:])
    return "".join(parts)


def prepare():
    data = run.prepare()
    spec, _, roots, history, _, _ = data
    contract_cache = read(run.OUT / f"{run.CONTRACT}_EXACT.json")
    actor_cache = read(run.OUT / f"{run.ACTOR}_EXACT.json")
    repairs = {}
    for uid, digest in spec["wire_sha256"].items():
        record, raw = contract_cache[digest]
        if record["status"] != "OK":
            continue
        choices = history[uid]["contract"]
        try:
            uses, _ = method.compile_uses(roots[uid], choices, raw)
        except (KeyError, ValueError, TypeError):
            continue
        if not uses:
            continue
        wire = method.actor_request(roots[uid], choices, uses, history[uid]["draft"])
        record, raw = actor_cache[sha(wire)]
        if record["status"] != "OK" or record.get("finish_reason") != "stop" or not isinstance(raw, str):
            continue
        query = roots[uid]["public_task"]["query"]
        try:
            STRICT(raw, choices, uses, query)
        except ValueError:
            try:
                normalized = normalize(raw, uses, choices)
                answers, _ = STRICT(normalized, choices, uses, query)
            except ValueError:
                continue
            repairs[uid] = {"request_sha256": sha(wire), "raw_sha256": sha(raw), "contract_sha256": sha(uses),
                            "normalized_sha256": sha(normalized),
                            "answer_sha256": {arm: sha(answer) if answer is not None else None
                                              for arm, answer in answers.items()}}
    policy = {"parent_sha256": sha(spec), "recovery_sha256": sha(Path(__file__).read_bytes()),
              "caps": {run.CONTRACT: 0, run.ACTOR: 0, run.JUDGE: len(repairs) * 2}, "repairs": repairs,
              "contract_cache_sha256": sha(contract_cache), "actor_cache_sha256": sha(actor_cache),
              "author_labels_used": False}
    return data, policy


def execute(data, policy, action):
    if policy != read(OUT / "RECOVERY_PLAN.json") or read(run.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Prior experiment settlement and a frozen recovery are required")
    original, jobs, roots, history, scoring, cache = data
    cache = {stage: {**old, **read(run.OUT / f"{stage}_EXACT.json")} for stage, old in cache.items()}
    spec = {**original, "caps": policy["caps"], "recovery_sha256": sha(policy), "inherited_sha256": sha(cache)}
    allowed = {(r["raw_sha256"], r["contract_sha256"]): r["normalized_sha256"] for r in policy["repairs"].values()}

    def apply(raw, choices, uses, query):
        key = sha(raw), sha(uses)
        if key in allowed:
            raw = normalize(raw, uses, choices)
            if sha(raw) != allowed[key]:
                raise ValueError("Recovered wire no longer matches frozen normalization")
        return STRICT(raw, choices, uses, query)

    probe.OUT, probe.RUN, run.replay.OUT = OUT, RUN, OUT
    state = OUT / "RUN_STATE.json"
    previous = run.parent.previous
    with (probe.runner_lock(RUN / "runner.lock"), patch.object(method, "compile_answer", apply),
          patch.object(previous, "OUT", OUT), patch.object(previous, "evaluate", run.evaluate),
          patch.object(previous, "summarize", run.summarize)):
        done = state.exists() and read(state)["state"] == "COMPLETE"
        if action == "run" and not done:
            probe.freeze(OUT / "FROZEN.json", spec)
            previous.execute((spec, jobs, roots, history, scoring, cache), live=True)
        elif action == "verify":
            if not done:
                raise ValueError("The recovery is not settled")

            def same(path, data):
                if read(path) != json.loads(json.dumps(data)):
                    raise ValueError(f"Recovery replay differs at {path.name}")

            with patch.object(probe, "freeze", same):
                previous.execute((spec, jobs, roots, history, scoring, cache), live=False)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    action = parser.parse_args().action
    data, policy = prepare()
    if action == "freeze":
        probe.freeze(OUT / "RECOVERY_PLAN.json", policy)
    else:
        execute(data, policy, action)
    print(json.dumps({"action": action, "recoverable": len(policy["repairs"]), "caps": policy["caps"]}))
