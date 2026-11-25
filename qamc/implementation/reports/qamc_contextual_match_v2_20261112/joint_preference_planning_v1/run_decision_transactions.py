"""Test independently executable variants on exposed RPEval histories."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import canonical, sha, token_estimate

import decision_transactions as method
import run_effect_scope as previous
from settle_joint_planning import score_matrix, usage


BASE_OUT = previous.OUT.with_name("transaction_scope_rpeval_v1")
BASE_RUN = previous.RUN.with_name(BASE_OUT.name)
STAGE, JUDGE = "DecisionTransactions", previous.JUDGE
probe, read, replay = previous.probe, previous.read, previous.replay
ARCHIVED = previous.ARCHIVED
ARMS = (*method.MODES, *ARCHIVED)
REGRESSION = ("explicit/029", "explicit/049", "explicit/052", "explicit/090", "explicit/116")


def prepare(panel):
    spec_old, _, old_data, roots, archive, linked_compose = previous.prepare()
    linked_cases = previous.prior.prepare()[2]
    older = previous.prior.old.prior.parent.prior
    parent, _, _, rows, _, _ = older.prepare("pilot")
    used_groups = {m["group"] for m in spec_old["roster"].values()} | {m["group"] for m in linked_cases.values()}
    drafts = previous.task_only.saved_drafts(archive)
    task_scores = {r["uid"]: r["task_only"] for r in read(previous.task_only.OUT / "RESULTS.json")["roots"]}
    data, roster, jobs = {}, {}, []
    for row in rows:
        uid, group = row["uid"], row["group"]
        root = roots[uid]
        if panel == "smoke":
            if not uid.endswith(REGRESSION):
                continue
            task = old_data[uid]
            blocks, native = task["blocks"], task["native"]
            draft_origin = spec_old["roster"][uid]["draft_origin"]
        else:
            if group in used_groups:
                continue
            draft_origin = root["task_wire_sha256"]
            draft = drafts[draft_origin]["answer"]
            if not draft:
                raise ValueError("Uncovered frozen draft")
            blocks = {"D1": {"kind": "CONTENT", "lines": [draft], "anchor": root["public_task"]["query"]}}
            native = {**{m: row["native"][m] for m in ARCHIVED[1:]}, ARCHIVED[0]: task_scores[uid]}
        roster[uid] = {"group": group, "draft_origin": draft_origin, "blocks_sha256": sha(blocks)}
        data[uid] = {"blocks": blocks, "labels": row["labels"], "positions": row["positions"], "native": native}
        jobs.extend([(uid, method.ATOMIC, method.request(root, blocks)),
                     (uid, method.ORDINARY, method.linked.request(root, blocks, method.ORDINARY))])
    if len(roster) != (len(REGRESSION) if panel == "smoke" else 55):
        raise ValueError("The committed exposed roster changed")
    compose = {**linked_compose, **read(previous.OUT / f"{previous.STAGE}_EXACT.json")}
    judge = previous.prior.old.prior.cache(archive)[JUDGE]
    stage_dirs = (previous.prior.old.prior.OUT, previous.prior.old.OUT, previous.prior.OUT, previous.OUT)
    for directory in stage_dirs:
        judge.update(read(directory / f"{JUDGE}_EXACT.json"))
    paths = [Path(__file__), Path(method.__file__), Path(method.scoped.__file__), Path(method.linked.__file__),
             Path(__file__).with_name("DECISION_TRANSACTION_PROTOCOL.md"),
             previous.OUT / "FROZEN.json", previous.prior.OUT / "FROZEN.json",
             older.BASE_OUT / "pilot/FROZEN.json", previous.task_only.OUT / "RESULTS.json",
             previous.OUT / f"{previous.STAGE}_EXACT.json", previous.prior.OUT / f"{previous.prior.COMPOSE}_EXACT.json",
             *(v / f"{JUDGE}_EXACT.json" for v in stage_dirs)]
    base = Path(__file__).resolve().parents[3]
    wires = {f"{uid}/{arm}": sha(wire) for uid, arm, wire in jobs}
    spec = {
        "panel": panel, "roster": roster, "generation_sha256": wires,
        "n_source_groups": len({v["group"] for v in roster.values()}),
        "caps": {STAGE: len(set(wires.values()) - compose.keys()), JUDGE: 3 * len(roster)},
        "input_sha256": {str(path.resolve().relative_to(base)): sha(path.read_bytes()) for path in paths},
        "inherited_sha256": {STAGE: sha(compose), JUDGE: sha(judge)},
        "service_reference_sha256": parent["service_reference_sha256"],
        "screen": {"coverage": .9, "match_margin": -.02, "opb_margin": .05, "other_margin": .1},
        "independent_confirmation": False,
    }
    return spec, jobs, roots, data, {STAGE: compose, JUDGE: judge}


def generate(inputs, stage):
    spec, jobs, roots, data, _ = inputs
    rows = {uid: {**meta, "uid": uid, "labels": data[uid]["labels"], "positions": data[uid]["positions"],
                  "native": dict(data[uid]["native"]), "outputs": {}, "attempts": {}}
            for uid, meta in spec["roster"].items()}
    for (uid, arm), (received, raw) in stage(STAGE, jobs).items():
        row = rows[uid]
        cell = row["attempts"][arm] = {"status": received["status"], "raw": raw,
                                     "request_sha256": received["request_sha256"]}
        if cell["status"] != "OK":
            continue
        try:
            if arm == method.ORDINARY:
                row["outputs"][arm] = method.linked.ordinary_answer(raw)
                continue
            root, blocks = roots[uid], data[uid]["blocks"]
            units, rejected = method.parse(root, blocks, raw)
            row.update(units=units, rejected=rejected, execution={})
            for variant in (method.ATOMIC, method.BUNDLED):
                answer, commits, rejections = method.render(root, blocks, units, atomic=variant == method.ATOMIC)
                row["outputs"][variant] = answer
                row["execution"][variant] = {"committed": commits, "rejected": rejections}
        except (KeyError, TypeError, ValueError) as error:
            cell.update(status="INVALID_COMPOSE", format_error=type(error).__name__)
    return rows


def grade(rows, stage):
    parent = previous.prior.old.prior.parent.prior.parent.joint
    reference = parent.prior
    official = read(reference.formal.OUT / "PLAN.json")
    cases = reference.author_cases(official)
    jobs = []
    for uid, row in rows.items():
        for arm in method.MODES:
            physical = method.ATOMIC if arm == method.BUNDLED else arm
            row["native"][arm] = {"fields": {}, "status": row["attempts"][physical]["status"]}
            if arm in row["outputs"]:
                jobs.append((uid, arm, parent.parent.grade_request(official, cases[uid], row["outputs"][arm])))
    for (uid, arm), (received, raw) in stage(JUDGE, jobs).items():
        row = rows[uid]
        row["native"][arm] = parent.parent.parse_grade(received, raw, row["positions"])


def summarize(spec, rows, ledger):
    values = list(rows.values())
    panels = {"all": values, "all_A": [r for r in values if set(r["labels"]) == {"A"}],
              "contains_BC": [r for r in values if set(r["labels"]) & {"B", "C"}]}
    compare = previous.prior.old.prior.parent.prior.parent.joint.parent.comparisons.grade_pair
    paired = {key: {arm: {"match": replay.paired(group, arm, method.ATOMIC),
                          **{f: compare(group, arm, method.ATOMIC, f) for f in ("OPB", "UPB", "FM", "VG")}}
                    for arm in ARMS if arm != method.ATOMIC} for key, group in panels.items()}
    changed = [r for r in values if r["outputs"].get(method.ATOMIC) != r["outputs"].get(method.BUNDLED)]
    distinct = len({v["group"] for v in changed})
    screen = spec["screen"]
    gates = {"two_source_groups_changed": distinct >= 2}
    for arm in (method.BUNDLED, method.ORDINARY):
        match = paired["all"][arm]["match"]
        interval = match.get("95pct_source_bootstrap")
        gates[f"{arm}/main_match"] = bool(interval and interval[0] > 0
                                         and match["valid_cases"] >= screen["coverage"] * len(values))
        bc = paired["contains_BC"][arm]["match"]
        gates[f"{arm}/retains_BC_match"] = bool(bc["valid_cases"] >= screen["coverage"] * len(panels["contains_BC"])
                                             and bc.get("match_delta") is not None
                                             and bc["match_delta"] >= screen["match_margin"])
        for layer, field in (("contains_BC", "UPB"), ("contains_BC", "FM"), ("all_A", "OPB"), ("all", "VG")):
            metric = paired[layer][arm][field]
            gates[f"{arm}/{field}"] = bool(metric["n"] and metric["n"] >= screen["coverage"] * len(panels[layer])
                                         and metric["delta"] <= screen["opb_margin" if field == "OPB" else "other_margin"])
    gate, rp = ARCHIVED[1:]
    for arm in (gate, rp):
        match = paired["all"][arm]["match"]
        gates[f"{arm}/positive_match"] = bool(match.get("match_delta") is not None and match["match_delta"] > 0
                                             and match["valid_cases"] >= screen["coverage"] * len(values))
    return {
        "panel": spec["panel"], "gates": gates, "pilot_passed": spec["panel"] == "pilot" and all(gates.values()),
        "paired": paired, "common": {key: score_matrix(group, ARMS) for key, group in panels.items()},
        "changed_cases": [row["uid"] for row in changed], "changed_groups": distinct,
        "attempt_statuses": Counter(f"{arm}/{attempt['status']}" for row in values for arm, attempt in row["attempts"].items()),
        "usage": {name: usage([row for row in ledger if row["unit"]["stage"] == name]) for name in spec["caps"]},
    }


def execute(inputs, out, run, *, live):
    spec, _, _, _, cache = inputs
    if spec != read(out / "FROZEN.json") or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen protocol or service reference changed")
    if any(key != record["request_sha256"] for values in cache.values() for key, (record, _) in values.items()):
        raise ValueError("Mismatched inherited receipt")
    probe.OUT, probe.RUN, replay.OUT = out, run, out

    def stage(name, jobs):
        digests = {sha(wire) for _, _, wire in jobs} - cache[name].keys()
        if len(digests) > spec["caps"][name] or any(token_estimate(canonical(w["messages"])) > 32768 for _, _, w in jobs):
            raise ValueError("Frozen stage cap exceeded")
        result = replay.execute_stage(spec, spec["panel"], name, jobs, cache[name], live)
        for uid, arm, wire in jobs:
            record, _ = result[uid, arm]
            if record["request_sha256"] != sha(wire) or record["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise ValueError("Unmatched or unresolved receipt")
        return result

    state = out / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": spec["caps"]})
    try:
        rows = generate(inputs, stage)
        grade(rows, stage)
        ledger = [record for name in spec["caps"] for record, _ in probe.stage_receipts(name).values()]
        if len(ledger) != len({(r["unit"]["stage"], r["request_sha256"]) for r in ledger}):
            raise ValueError("Duplicate physical request")
        probe.freeze(out / "SETTLED.json", {"rows": list(rows.values()), "ledger": ledger})
        probe.freeze(out / "RESULTS.json", summarize(spec, rows, ledger))
    except (ValueError, RuntimeError, OSError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


def check(inputs):
    spec, jobs, roots, data, _ = inputs
    payloads = {}
    for uid, _, wire in jobs:
        user_message = wire["messages"][1]
        body = json.loads(user_message["content"])
        assert set(body) == {"task", "draft", "source_evidence"}
        assert body["task"] == roots[uid]["public_task"] and body["source_evidence"] == roots[uid]["original_sources"]
        assert body["draft"].keys() == data[uid]["blocks"].keys()
        assert payloads.setdefault(uid, user_message) == user_message
        assert token_estimate(canonical(wire["messages"])) <= 32768
    replay.manifest(spec["panel"], STAGE, jobs)

    def simulated(name, requests):
        replay.manifest(spec["panel"], name, requests)
        receipts = {}
        for uid, arm, wire in requests:
            raw = ('{"answer":"offline"}' if arm == method.ORDINARY else '{"decisions":[]}') if name == STAGE else None
            receipts[uid, arm] = ({"request_sha256": sha(wire), "status": "OK" if raw else "OFFLINE"}, raw)
        return receipts

    rows = generate(inputs, simulated)
    for uid, row in rows.items():
        draft = method.rank.render(roots[uid], data[uid]["blocks"], {}, method.rank.DRAFT)["answer"]
        assert row["outputs"][method.ATOMIC] == row["outputs"][method.BUNDLED] == draft
    grade(rows, simulated)
    assert not summarize(spec, rows, [])["pilot_passed"]
    print(json.dumps({"cases": len(data), "groups": spec["n_source_groups"], "caps": spec["caps"], "new_requests": 0}))


def verify(inputs, out, run):
    state = read(out / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("Run has not settled")
    checked = []

    def compare(file, value):
        if read(file) != json.loads(json.dumps(value)):
            raise ValueError(f"Replay differs from {file.name}")
        checked.append(file.name)

    with patch.object(probe, "freeze", compare):
        execute(inputs, out, run, live=False)
    if len(read(out / "SETTLED.json")["ledger"]) != state["physical_requests"]:
        raise ValueError("Inconsistent physical request count")
    print(json.dumps({"files": checked, "requests": state["physical_requests"], "new_requests": 0}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("panel", choices=("smoke", "pilot"))
    parser.add_argument("action", choices=("check", "freeze", "run", "verify"))
    args = parser.parse_args()
    out, run = BASE_OUT / args.panel, BASE_RUN / args.panel
    inputs = prepare(args.panel)
    if args.action in ("check", "freeze"):
        check(inputs)
        if args.action == "freeze":
            probe.freeze(out / "FROZEN.json", inputs[0])
    else:
        with probe.runner_lock(run / "runner.lock"):
            if args.action == "verify":
                verify(inputs, out, run)
            else:
                execute(inputs, out, run, live=True)
