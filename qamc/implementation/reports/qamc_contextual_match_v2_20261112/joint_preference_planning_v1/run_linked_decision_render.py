"""Evaluate decision-linked realization on fixed task-only drafts and original memories."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import canonical, sha, token_estimate

import linked_decision_render as method
import run_grounded_feasibility as old
from settle_joint_planning import score_matrix, usage


OUT = old.OUT.with_name("linked_decision_rpeval_v1")
RUN = old.RUN.with_name(OUT.name)
COMPOSE, JUDGE = "LinkedCompose", old.JUDGE
probe, read, replay = old.probe, old.read, old.replay
INITIAL = old.method.DRAFT
OLD_PLACEMENT = old.method.DIRECT
CONTROLS = (INITIAL, OLD_PLACEMENT, *old.BASELINES)
ARMS = (*method.MODES, *CONTROLS)
DISCLOSED = ("explicit/052", "explicit/056", "explicit/068", "explicit/086", "explicit/131")


def prepare():
    frozen, _, _, roots, archive = old.prepare()
    if frozen != read(old.OUT / "FROZEN.json") or read(old.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Predecessor run is not verified complete")
    source = {row["uid"]: row for row in read(old.OUT / "SETTLED.json")["rows"]}
    roles, jobs = {}, []
    for pair in frozen["pairs"]:
        primary = pair["primary"] and not any(pair[k].endswith(DISCLOSED) for k in old.CONDITIONS)
        for key in old.CONDITIONS:
            uid = pair[key]
            parent = source[uid]
            blocks = parent["execution"]["blocks"]
            roles[uid] = {"primary": primary, "eligible": bool(blocks), "condition": key,
                          "group": pair["group"], "blocks_sha256": sha(blocks)}
            if blocks:
                for arm in (method.OFF, method.ORDINARY):
                    jobs.append((uid, arm, method.request(roots[uid], blocks, arm)))
    files = (Path(__file__), Path(method.__file__), Path(method.rank.__file__), Path(old.__file__),
             Path(__file__).with_name("LINKED_DECISION_PROTOCOL.md"), old.OUT / "FROZEN.json",
             old.OUT / "SETTLED.json", old.OUT / f"{old.JUDGE}_EXACT.json")
    base = Path(__file__).resolve().parents[3]
    spec = {"roster": roles, "service_reference_sha256": frozen["service_reference_sha256"],
            "caps": {COMPOSE: len(jobs), JUDGE: sum(v["eligible"] for v in roles.values()) * len(method.MODES)},
            "generation_sha256": {f"{uid}/{arm}": sha(wire) for uid, arm, wire in jobs},
            "inputs_sha256": {str(p.resolve().relative_to(base)): sha(p.read_bytes()) for p in files},
            "screen": {"coverage": .90, "min_fm_reduction": .10, "protected_match": -.02,
                       "protected_bias": .05},
            "independent_confirmation": False}
    return spec, jobs, source, roots, archive


def generate(inputs, stage):
    spec, jobs, source, roots, _ = inputs
    rows = {}
    for uid, metadata in spec["roster"].items():
        parent = source[uid]
        rows[uid] = {**metadata, "uid": uid, "labels": parent["labels"], "positions": parent["positions"],
                     "native": {m: parent["native"][m] for m in CONTROLS}, "outputs": {}, "attempts": {}}
    for (uid, arm), (receipt, raw) in stage(COMPOSE, jobs).items():
        row = rows[uid]
        state = row["attempts"][arm] = {"status": receipt["status"], "request_sha256": receipt["request_sha256"],
                                       "raw": raw}
        if receipt["status"] != "OK":
            continue
        try:
            if arm == method.ORDINARY:
                row["outputs"][arm] = method.ordinary_answer(raw)
            else:
                blocks = source[uid]["execution"]["blocks"]
                policy, links, rejected = method.compile_links(roots[uid], blocks, raw)
                row.update(policy=policy, links=links, rejected=rejected)
                row["outputs"][method.OFF] = method.render(roots[uid], blocks, policy, {})["answer"]
                row["outputs"][method.ON] = method.render(roots[uid], blocks, policy, links)["answer"]
        except (KeyError, TypeError, ValueError):
            state["status"] = "INVALID_COMPOSE"
    return rows


def grade(rows, stage):
    training_archive = old.prior.parent.prior.parent.joint.prior
    official = read(training_archive.formal.OUT / "PLAN.json")
    cases = training_archive.author_cases(official)
    scorer = old.prior.parent.prior.parent.joint.parent
    jobs = []
    for uid, row in rows.items():
        for arm in method.MODES:
            if arm in row["outputs"]:
                jobs.append((uid, arm, scorer.grade_request(official, cases[uid], row["outputs"][arm])))
            status = row["attempts"].get(method.OFF if arm == method.ON else arm, {}).get("status", "INVALID_DRAFT")
            row["native"][arm] = {"fields": {}, "status": status}
    for (uid, arm), (record, raw) in stage(JUDGE, jobs).items():
        row = rows[uid]
        row["native"][arm] = scorer.parse_grade(record, raw, row["positions"])


def summarize(spec, rows, ledger):
    primary = [r for r in rows.values() if r["primary"] and r["eligible"]]
    panels = {
        "primary": primary,
        "guard": [r for r in primary if r["condition"] == "guard"],
        "all_A": [r for r in primary if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in primary if set(r["labels"]) & {"B", "C"}],
        "regression": [r for r in rows.values() if not r["primary"] and r["eligible"]],
    }
    compare = old.prior.parent.prior.parent.joint.parent.comparisons.grade_pair
    paired = {name: {arm: {"match": replay.paired(group, arm, method.ON),
                           **{field: compare(group, arm, method.ON, field)
                              for field in ("OPB", "UPB", "FM", "VG", "full_match")}}
                     for arm in ARMS if arm != method.ON}
              for name, group in panels.items()}
    s = spec["screen"]
    gates = {}
    for arm in (method.OFF, method.ORDINARY):
        pair = paired["primary"][arm]
        fm, match = pair["FM"], pair["match"]
        bounds = fm.get("95pct_source_bootstrap")
        gates[f"{arm}/FM"] = bool(bounds and fm["n"] >= s["coverage"] * len(primary)
                                 and fm["delta"] <= -s["min_fm_reduction"] and bounds[1] < 0)
        gates[f"{arm}/Match"] = bool(match["valid_cases"] >= s["coverage"] * len(primary)
                                    and match["match_delta"] is not None
                                    and match["match_delta"] >= s["protected_match"])
        for panel, field in (("all_A", "OPB"), ("contains_BC", "UPB"), ("primary", "VG")):
            relevant = paired[panel][arm][field]
            gates[f"{arm}/{field}"] = bool(panels[panel] and relevant.get("n", 0) >= s["coverage"] * len(panels[panel])
                                          and relevant["delta"] <= s["protected_bias"])
    changes = [r for r in primary if method.ON in r["outputs"] and r["outputs"][method.ON] != r["outputs"][method.OFF]]
    gates["two_source_groups_changed"] = len({r["group"] for r in changes}) >= 2
    return {"gates": gates, "passed": all(gates.values()),
            "coverage": Counter(("primary" if r["primary"] else "regression", r["eligible"])
                                for r in rows.values()).most_common(),
            "changed_primary": [r["uid"] for r in changes],
            "common": {k: score_matrix(v, ARMS) for k, v in panels.items()}, "paired": paired,
            "usage": {name: usage([r for r in ledger if r["unit"]["stage"] == name]) for name in spec["caps"]}}


def execute(inputs, *, live):
    spec, _, _, _, archive = inputs
    if spec != read(OUT / "FROZEN.json") or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen protocol or service reference changed")
    exact = {COMPOSE: {}, JUDGE: old.prior.cache(archive)[old.JUDGE]}
    for location in (old.prior.OUT, old.OUT):
        exact[JUDGE].update(read(location / f"{old.JUDGE}_EXACT.json"))
    if any(digest != item[0]["request_sha256"] for digest, item in exact[JUDGE].items()):
        raise ValueError("Judge cache receipt differs from request hash")
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        digests = {sha(wire) for _, _, wire in jobs} - exact[name].keys()
        if len(digests) > spec["caps"][name] or any(token_estimate(canonical(w["messages"])) > 32768 for _, _, w in jobs):
            raise ValueError("Frozen stage caps exceeded")
        result = replay.execute_stage(spec, "linked_decision", name, jobs, exact[name], live)
        for uid, arm, wire in jobs:
            receipt, _ = result[uid, arm]
            if receipt["request_sha256"] != sha(wire) or receipt["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise ValueError("Unexpected or unresolved receipt")
        return result

    path = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(path, {"state": "RUNNING", "caps": spec["caps"]})
    try:
        rows = generate(inputs, stage)
        grade(rows, stage)
        ledger = [r for name in spec["caps"] for r, _ in probe.stage_receipts(name).values()]
        if len(ledger) != len({(r["unit"]["stage"], r["request_sha256"]) for r in ledger}):
            raise ValueError("Duplicate physical request")
        probe.freeze(OUT / "SETTLED.json", {"rows": list(rows.values()), "ledger": ledger})
        probe.freeze(OUT / "RESULTS.json", summarize(spec, rows, ledger))
    except (ValueError, RuntimeError, OSError) as error:
        if live:
            probe.atomic_json(path, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(path, {"state": "COMPLETE", "physical_requests": len(ledger)})


def check(inputs):
    spec, jobs, source, roots, _ = inputs
    for uid, arm, wire in jobs:
        payload = json.loads(wire["messages"][1]["content"])
        assert set(payload) == {"task", "draft", "source_evidence"}
        assert payload["task"] == roots[uid]["public_task"]
        assert payload["source_evidence"] == roots[uid]["original_sources"]
        assert set(payload["draft"]) == source[uid]["execution"]["blocks"].keys()
        assert spec["generation_sha256"][f"{uid}/{arm}"] == sha(wire)
    by_uid = {uid: {} for uid, _, _ in jobs}
    for uid, arm, wire in jobs:
        by_uid[uid][arm] = wire["messages"][1]
    assert all(pair[method.OFF] == pair[method.ORDINARY] for pair in by_uid.values())
    replay.manifest("offline", COMPOSE, jobs)

    uid = next(uid for uid in source if uid.endswith("explicit/052"))
    execution = source[uid]["execution"]
    blocks, root = execution["blocks"], roots[uid]
    choice, saved = next((key, value) for key, value in execution["policy"].items() if value["guard"])
    prose = next(key for key, block in blocks.items() if block["kind"] == "CONTENT")
    original = blocks[prose]["lines"][0]
    link = {"prose": prose, "choice": choice, "old": original[:28], "new": "LOCAL_REPAIR"}
    example = {"decisions": [{"block": choice, **saved}], "linked_prose": [link]}
    policy, links, invalid = method.compile_links(root, blocks, json.dumps(example))
    assert not invalid and list(links) == [prose]
    off = method.render(root, blocks, policy, {})
    on = method.render(root, blocks, policy, links)
    assert on["answer"] == off["answer"].replace(link["old"], link["new"], 1)
    assert on["decisions"] == off["decisions"]
    example["linked_prose"].append({**link, "new": "OVERLAP"})
    assert method.compile_links(root, blocks, json.dumps(example))[1:] == ({}, ["LINK_OVERLAP"])
    example["decisions"] = [{"block": choice, **saved, "guard": None}]
    _, links, invalid = method.compile_links(root, blocks, json.dumps(example))
    assert not links and invalid == ["LINK_SCOPE", "LINK_SCOPE"]
    print(json.dumps({"roster": Counter(r["eligible"] for r in spec["roster"].values()),
                      "primary": sum(v["primary"] and v["eligible"] for v in spec["roster"].values()),
                      "caps": spec["caps"], "model_requests": 0}))


def verify(inputs):
    state = read(OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("Run has not settled")
    checked = []

    def confirm(path, rebuilt):
        if read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Offline replay differs from {path.name}")
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
