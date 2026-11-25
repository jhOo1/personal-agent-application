"""Evaluate independent effect admission on exposed RPEval drafts."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import canonical, sha, token_estimate

import effect_scope_compiler as method
import run_linked_decision_render as prior
import score_task_only as task_only
from settle_joint_planning import score_matrix, usage


OUT = prior.OUT.with_name("effect_scope_rpeval_v1")
RUN = prior.RUN.with_name(OUT.name)
STAGE, JUDGE = "CompileEffects", prior.JUDGE
probe, read, replay = prior.probe, prior.read, prior.replay
ARCHIVED = (prior.INITIAL, *prior.old.BASELINES)
ARMS = (*method.MODES, *ARCHIVED)
KNOWN = (
    "explicit/058", "implicit/109", "implicit/004", "implicit/104", "explicit/127", "implicit/052",
    "explicit/056", "implicit/116", "explicit/052", "explicit/124", "implicit/075", "explicit/139",
)
DISCLOSED = (*KNOWN, "explicit/068", "explicit/086", "explicit/131", "implicit/133", "implicit/013", "implicit/123")


def prepare():
    _, _, linked_source, roots, archive = prior.prepare()
    previous = prior.old.prior.parent.prior
    roster, _, _, rows, _, _ = previous.prepare("pilot")
    excluded = set(roster["diagnostic_source_groups"])
    excluded.update(r["group"] for r in linked_source.values() if r["uid"].endswith(DISCLOSED))
    draft_receipts = task_only.saved_drafts(archive)
    task_scores = {r["uid"]: r["task_only"] for r in read(task_only.OUT / "RESULTS.json")["roots"]}
    linked_scores = {r["uid"]: r["native"] for r in read(prior.OUT / "SETTLED.json")["rows"]}
    old_compose = read(prior.OUT / f"{prior.COMPOSE}_EXACT.json")
    metadata, data, jobs = {}, {}, []
    for row in rows:
        uid = row["uid"]
        root = roots[uid]
        regression = uid in linked_source and uid.endswith(KNOWN)
        if regression:
            parent = linked_source[uid]
            blocks = parent["execution"]["blocks"]
            old_scores = {m: linked_scores[uid][m] for m in ARCHIVED}
            draft_origin = parent["execution"]["task_sha256"]
        elif uid not in linked_source and row["group"] not in excluded:
            draft_origin = root["task_wire_sha256"]
            text = draft_receipts[draft_origin]["answer"]
            if text is None:
                continue
            blocks = {"D1": {"kind": "CONTENT", "lines": [text], "anchor": root["public_task"]["query"]}}
            old_scores = {**{m: row["native"][m] for m in prior.old.BASELINES}, prior.INITIAL: task_scores[uid]}
        else:
            continue
        if not blocks:
            raise ValueError("A selected regression has no reusable draft")
        metadata[uid] = {"group": row["group"], "primary": not regression, "blocks_sha256": sha(blocks),
                         "draft_origin": draft_origin}
        data[uid] = {"blocks": blocks, "labels": row["labels"], "positions": row["positions"], "native": old_scores}
        jobs.extend(((uid, method.STRUCTURAL, method.request(root, blocks)),
                     (uid, method.ORDINARY, method.linked.request(root, blocks, method.ORDINARY))))
    base = Path(__file__).resolve().parents[3]
    paths = (Path(__file__), Path(method.__file__), Path(method.linked.__file__), Path(method.rank.__file__),
             Path(task_only.__file__), Path(__file__).with_name("EFFECT_SCOPE_PROTOCOL.md"),
             previous.BASE_OUT / "pilot/FROZEN.json", prior.OUT / "FROZEN.json", prior.OUT / "SETTLED.json",
             prior.OUT / f"{prior.COMPOSE}_EXACT.json", prior.OUT / f"{JUDGE}_EXACT.json",
             task_only.OUT / "FROZEN.json", task_only.OUT / "RESULTS.json")
    digests = {f"{uid}/{arm}": sha(wire) for uid, arm, wire in jobs}
    spec = {
        "roster": metadata, "generation_sha256": digests,
        "regression_compose_reuse": sum(digest in old_compose for digest in digests.values()),
        "inputs_sha256": {str(path.resolve().relative_to(base)): sha(path.read_bytes()) for path in paths},
        "caps": {STAGE: len(set(digests.values()) - old_compose.keys()), JUDGE: len(metadata) * len(method.MODES)},
        "service_reference_sha256": roster["service_reference_sha256"],
        "screen": {"coverage": .90, "match_loss": -.02, "severity_increase": .05},
        "independent_confirmation": False,
    }
    return spec, jobs, data, roots, archive, old_compose


def generate(inputs, stage):
    spec, jobs, data, roots, _, _ = inputs
    rows = {}
    for uid, meta in spec["roster"].items():
        task = data[uid]
        rows[uid] = {**meta, "uid": uid, "labels": task["labels"], "positions": task["positions"],
                     "native": dict(task["native"]), "outputs": {}, "attempts": {}}
    for (uid, arm), (received, raw) in stage(STAGE, jobs).items():
        row = rows[uid]
        attempt = row["attempts"][arm] = {"status": received["status"], "request_sha256": received["request_sha256"],
                                         "raw": raw}
        if attempt["status"] != "OK":
            continue
        blocks = data[uid]["blocks"]
        try:
            if arm == method.ORDINARY:
                row["outputs"][arm] = method.linked.ordinary_answer(raw)
                continue
            effects, edits, rejected = method.parse(roots[uid], blocks, raw)
            row.update(effects=effects, proposed_edits=edits, rejected=rejected, execution={})
            for mode in (method.SCOPED, method.STRUCTURAL):
                answer, applied, failed = method.render(roots[uid], blocks, effects, edits, scope=mode == method.SCOPED)
                row["outputs"][mode] = answer
                row["execution"][mode] = {"applied": applied, "rejected": failed}
        except (KeyError, TypeError, ValueError):
            attempt["status"] = "INVALID_COMPOSE"
    return rows


def grade(rows, stage):
    author = prior.old.prior.parent.prior.parent.joint.prior
    official = read(author.formal.OUT / "PLAN.json")
    cases = author.author_cases(official)
    scorer = prior.old.prior.parent.prior.parent.joint.parent
    jobs = []
    for uid, row in rows.items():
        for arm in method.MODES:
            physical = method.STRUCTURAL if arm == method.SCOPED else arm
            row["native"][arm] = {"fields": {}, "status": row["attempts"][physical]["status"]}
            if arm in row["outputs"]:
                jobs.append((uid, arm, scorer.grade_request(official, cases[uid], row["outputs"][arm])))
    for (uid, arm), (received, raw) in stage(JUDGE, jobs).items():
        row = rows[uid]
        row["native"][arm] = scorer.parse_grade(received, raw, row["positions"])


def summarize(spec, rows, ledger):
    primary = [r for r in rows.values() if r["primary"]]
    panels = {
        "primary": primary,
        "all_A": [r for r in primary if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in primary if set(r["labels"]) & {"B", "C"}],
        "regression": [r for r in rows.values() if not r["primary"]],
    }
    compare = prior.old.prior.parent.prior.parent.joint.parent.comparisons.grade_pair
    paired = {name: {arm: {"match": replay.paired(group, arm, method.SCOPED),
                           **{field: compare(group, arm, method.SCOPED, field)
                              for field in ("OPB", "UPB", "FM", "VG", "full_match")}}
                     for arm in ARMS if arm != method.SCOPED}
              for name, group in panels.items()}
    s = spec["screen"]
    sharpest = paired["primary"][method.ORDINARY]["match"]
    interval = sharpest.get("95pct_source_bootstrap")
    gate = {"beats_ordinary_match": bool(interval and interval[0] > 0
                                         and sharpest["valid_cases"] >= s["coverage"] * len(primary))}
    for arm in (method.ORDINARY, method.STRUCTURAL):
        match = paired["contains_BC"][arm]["match"]
        gate[f"{arm}/retains_BC_match"] = bool(match["valid_cases"] >= s["coverage"] * len(panels["contains_BC"])
                                             and match["match_delta"] is not None
                                             and match["match_delta"] >= s["match_loss"])
        for panel, field in (("contains_BC", "UPB"), ("contains_BC", "FM"), ("all_A", "OPB"), ("primary", "VG")):
            cell = paired[panel][arm][field]
            gate[f"{arm}/{field}"] = bool(cell["n"] and cell["n"] >= s["coverage"] * len(panels[panel])
                                         and cell["delta"] <= s["severity_increase"])
    changes = [r["uid"] for r in primary if method.SCOPED in r["outputs"]
               and r["outputs"][method.SCOPED] != r["outputs"][method.STRUCTURAL]]
    mechanism = paired["primary"][method.STRUCTURAL]["OPB"]
    protection = mechanism.get("95pct_source_bootstrap")
    gate["scope_off_to_on_reduces_OPB"] = bool(protection and protection[1] < 0)
    gate["scope_changes_two_source_groups"] = len({rows[uid]["group"] for uid in changes}) >= 2
    return {"gates": gate, "passed": all(gate.values()), "scope_changes_primary": changes,
            "paired": paired, "common": {name: score_matrix(group, ARMS) for name, group in panels.items()},
            "usage": {name: usage([r for r in ledger if r["unit"]["stage"] == name]) for name in spec["caps"]}}


def execute(inputs, *, live):
    spec, _, _, _, archive, old_compose = inputs
    if spec != read(OUT / "FROZEN.json") or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen inputs or service reference changed")
    cache = {STAGE: old_compose, JUDGE: prior.old.prior.cache(archive)[JUDGE]}
    for location in (prior.old.prior.OUT, prior.old.OUT, prior.OUT):
        cache[JUDGE].update(read(location / f"{JUDGE}_EXACT.json"))
    if any(k != v[0]["request_sha256"] for values in cache.values() for k, v in values.items()):
        raise ValueError("Cache does not match exact request digest")
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        digests = {sha(wire) for _, _, wire in jobs} - cache[name].keys()
        if len(digests) > spec["caps"][name] or any(token_estimate(canonical(w["messages"])) > 32768 for _, _, w in jobs):
            raise ValueError("Frozen stage caps exceeded")
        result = replay.execute_stage(spec, "effect_scope", name, jobs, cache[name], live)
        for uid, arm, wire in jobs:
            received, _ = result[uid, arm]
            if received["request_sha256"] != sha(wire) or received["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise ValueError("Unmatched or unresolved receipt")
        return result

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": spec["caps"]})
    try:
        rows = generate(inputs, stage)
        grade(rows, stage)
        ledger = [record for name in spec["caps"] for record, _ in probe.stage_receipts(name).values()]
        if len(ledger) != len({(r["unit"]["stage"], r["request_sha256"]) for r in ledger}):
            raise ValueError("Duplicate physical requests")
        probe.freeze(OUT / "SETTLED.json", {"rows": list(rows.values()), "ledger": ledger})
        probe.freeze(OUT / "RESULTS.json", summarize(spec, rows, ledger))
    except (ValueError, RuntimeError, OSError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


def check(inputs):
    spec, jobs, data, roots, _, _ = inputs
    payloads = {}
    for uid, _, wire in jobs:
        payload = json.loads(wire["messages"][1]["content"])
        assert set(payload) == {"task", "draft", "source_evidence"}
        assert payload["task"] == roots[uid]["public_task"] and payload["source_evidence"] == roots[uid]["original_sources"]
        assert set(payload["draft"]) == data[uid]["blocks"].keys()
        assert payloads.setdefault(uid, wire["messages"][1]) == wire["messages"][1]
        assert token_estimate(canonical(wire["messages"])) <= 32768
    replay.manifest("offline", STAGE, jobs)
    check_compiler(roots, data)
    check_native_route(inputs)
    print(json.dumps({"cases": Counter("primary" if v["primary"] else "regression" for v in spec["roster"].values()),
                      "primary_groups": len({v["group"] for v in spec["roster"].values() if v["primary"]}),
                      "exact_ordinary_reuse": spec["regression_compose_reuse"], "caps": spec["caps"],
                      "new_model_requests": 0}))


def check_compiler(roots, data):
    uid = next(uid for uid in data if uid.endswith("explicit/127"))
    root = roots[uid]
    source = root["original_sources"][4]
    quote = next(part for part in method.rank.draft.user_source(source["text"]) if part.strip()).strip()
    draft = "Purchase the expensive gift. Tell the recipient it is their favorite."
    blocks = {"D1": {"kind": "CONTENT", "lines": [draft], "anchor": root["public_task"]["query"]}}
    shared = {"source": {"id": source["memory_id"], "quote": quote}, "authority": "SELF",
              "task_quote": root["public_task"]["query"], "force": "REQUIRE", "delegation": None}
    payload = {
        "effects": [{**shared, "id": "E1", "site": "REQUESTER_ACTION"},
                    {**shared, "id": "E2", "site": "OTHER_OUTCOME"}],
        "edits": [
            {"block": "D1", "option": None, "before": "the expensive gift",
             "after": "an affordable gift", "effects": ["E1"]},
            {"block": "D1", "option": None, "before": "it is their favorite",
             "after": "it is their favorite because you prefer it", "effects": ["E2"]},
        ],
    }
    effects, edits, rejected = method.parse(root, blocks, json.dumps(payload))
    assert not rejected and len(edits) == 2
    strict, applied, failed = method.render(root, blocks, effects, edits, scope=True)
    lax, _, _ = method.render(root, blocks, effects, edits, scope=False)
    assert strict == draft.replace("the expensive gift", "an affordable gift")
    assert lax != strict and len(applied) == 1 and failed[0]["reason"] == "ROLE_FORCE_SCOPE"
    payload["edits"].append({**payload["edits"][0], "after": "a prepared gift"})
    effects, edits, rejected = method.parse(root, blocks, json.dumps(payload))
    strict, applied, failed = method.render(root, blocks, effects, edits, scope=True)
    assert not rejected and not applied and strict == draft
    assert sum(item["reason"] == "EDIT_OVERLAP" for item in failed) == 2


def check_native_route(inputs):
    spec, _, data, roots, _, _ = inputs

    def simulated(name, jobs):
        replay.manifest("offline", name, jobs)
        results = {}
        for uid, arm, wire in jobs:
            raw = ('{"answer":"offline"}' if arm == method.ORDINARY else
                   '{"effects":[],"edits":[]}') if name == STAGE else None
            results[uid, arm] = ({"request_sha256": sha(wire), "status": "OK" if raw else "OFFLINE"}, raw)
        return results

    rows = generate(inputs, simulated)
    for uid, row in rows.items():
        initial = method.rank.render(roots[uid], data[uid]["blocks"], {}, method.rank.DRAFT)["answer"]
        assert row["outputs"][method.SCOPED] == row["outputs"][method.STRUCTURAL] == initial
    grade(rows, simulated)
    assert not summarize(spec, rows, [])["passed"]


def verify(inputs):
    state = read(OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("Run has not settled")
    checked = []

    def confirm(path, rebuilt):
        if read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Replay differs from {path.name}")
        checked.append(path.name)

    with patch.object(probe, "freeze", confirm):
        execute(inputs, live=False)
    report = read(OUT / "SETTLED.json")
    if len(report["ledger"]) != state["physical_requests"]:
        raise ValueError("Inconsistent physical request count")
    print(json.dumps({"verified_files": checked, "requests": state["physical_requests"], "new_requests": 0}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "verify"))
    action = parser.parse_args().action
    inputs = prepare()
    if action in ("check", "freeze"):
        check(inputs)
        if action == "freeze":
            probe.freeze(OUT / "FROZEN.json", inputs[0])
    else:
        with probe.runner_lock(RUN / "runner.lock"):
            if action == "verify":
                verify(inputs)
            else:
                execute(inputs, live=True)
