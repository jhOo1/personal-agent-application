"""Bind repeat slots to physical journal entries before reading scores."""
from collections import defaultdict
from contextlib import closing
import json
import sqlite3

from check_exposure_fr3 import ROOT, RUN, actor_request, judge_wire, read, select, transfer
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import sha


class Receipts:
    def __init__(self, uids, signature):
        self.uids = uids
        self.signature = signature
        self.tables = {}

    def table(self, directory):
        if directory in self.tables:
            return self.tables[directory]
        db_path = directory / "samples.sqlite"
        with closing(sqlite3.connect(db_path.absolute().as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute(
                "SELECT unit_key,unit_json,request_sha,request_json,status,response_json FROM samples"
            ).fetchall()
        result = defaultdict(list)
        for key, raw_unit, digest, raw_wire, state, response in rows:
            unit = json.loads(raw_unit)
            uid = unit["root_id"]
            if uid not in self.uids:
                continue
            wire = json.loads(raw_wire)
            if sampling_key(unit) != key or sha(wire) != digest:
                raise ValueError("Archive sampling key or wire hash mismatch")
            meta = read(directory / "visible" / key / "record.json")
            if meta["request_sha256"] != digest or meta["unit"] != unit:
                raise ValueError("Archive receipt does not bind to its request")
            if meta["reference_config_sha256"] != self.signature or meta["automatic_retries"] != 0:
                continue
            if (state == "COMPLETE") != (meta["status"] == "OK"):
                raise ValueError("Archive journal does not agree with visible receipt")
            answer = json.loads(response)["answer"] if state == "COMPLETE" else None
            if state == "COMPLETE" and (not isinstance(answer, str) or not answer.strip()):
                raise ValueError("Malformed successful archive answer")
            result[uid, digest].append({
                "ref": str(directory.relative_to(ROOT)) + "/" + key,
                "request_sha256": digest, "status": meta["status"], "answer": answer,
                "origin": "EXACT_ARCHIVE", "started": meta["started_unix"],
                "unit": unit,
            })
        self.tables[directory] = result
        return result

    def exact(self, directory, uid, wire, *, optional=False, stages=None):
        digest = sha(wire)
        matches = [r for r in self.table(directory).get((uid, digest), ())
                   if stages is None or r["unit"]["stage"] in stages]
        if len(matches) > 1 or (not optional and not matches):
            raise ValueError(f"{directory.name}: ambiguous or missing exact receipt")
        return matches[0] if matches else None


def branch(task, reply):
    result = transfer.confirmation.route.decode(reply, task["query"])
    return "style" if result["check_history"] else "grounding"


def link_selection(bank, uid, item, case, protocol, dirs, stages=None):
    route_dir, select_dir, actor_dir, grade_dir = dirs
    route = bank.exact(route_dir, uid, item["selection_requests"]["query"],
                       stages={"Actor"} if stages else None)
    receipts = {("Route", route["request_sha256"]): route}
    if route["status"] != "OK":
        return receipts
    task = item["public"]
    wire = item["selection_requests"][branch(task, route["answer"])]
    selected = bank.exact(select_dir, uid, wire, stages={"Selector"} if stages else None)
    receipts["Select", sha(wire)] = selected
    if selected["status"] != "OK":
        return receipts
    evidence = select(case, task, route["answer"], selected["answer"])
    wire = actor_request(case, task["query"], evidence, protocol, protocol["prompts"]["gepa"])
    final = bank.exact(actor_dir, uid, wire,
                       stages={"Actor"} if stages else None)
    receipts["Actor", sha(wire)] = final
    if final["status"] == "OK":
        return receipts, grade_dir, final
    return receipts


def plan_receipts(cases, inputs, protocol, judge, bounds, signature):
    """Assign complete chains first, then unused exact fixed control attempts."""
    old = RUN.parent
    bank = Receipts(cases, signature)
    build_grade = judge_wire(cases, inputs, judge, bounds)
    safety = old / "persist_equal_cap_safety_v1"
    utility = old / "persist_equal_cap_development_v1"
    prior = old / "persist_repeated_deployment_v1"
    physical = {}
    covered = defaultdict(dict)
    risk_roster = read(safety / "FROZEN.json")["tracks"]
    utility_roster = read(utility / "FROZEN.json")["cohort"]
    supplements = [old / name for name in (
        "selected_gepa_expansion_v1", "persist_performance_v1",
        "persist_selected_gepa_completion_v1",
    )]
    selector_early = ROOT / "runs/qamc_persistbench_grounding_transfer/execution"
    actor_early = ROOT / "runs/qamc_persistbench_actor_factorial/execution"
    role_dirs = {
        directory: tuple(directory / stage for stage in (
            "QueryRoute", "EvidenceSelect", "FinalActor", "PersistNative",
        )) for directory in supplements
    }

    def bind(uid, wave, role, receipt):
        key = uid, wave
        if receipt is None:
            return
        ref = receipt["ref"]
        origin = physical.setdefault(ref, key)
        if origin != key:
            raise ValueError("One historical physical sample cannot count as two repetitions")
        cell = (role, receipt["request_sha256"])
        previous = covered[key].setdefault(cell, receipt)
        if previous != receipt:
            raise ValueError("Two distinct historical responses seek one slot")

    def assign_actor(uid, wave, actor, grade_dir, optional_grade=False, stages=None):
        bind(uid, wave, "Actor", actor)
        if actor and actor["status"] == "OK":
            grade = build_grade(uid, actor["answer"])
            saved = bank.exact(grade_dir, uid, grade, optional=optional_grade, stages=stages)
            bind(uid, wave, "Judge", saved)

    def linked(uid, wave, dirs, *, early=False):
        chain = link_selection(bank, uid, inputs[uid], cases[uid], protocol, dirs, early)
        receipts = chain[0] if isinstance(chain, tuple) else chain
        for (role, _), receipt in receipts.items():
            bind(uid, wave, role, receipt)
        if isinstance(chain, tuple):
            _, grade_dir, final = chain
            assign_actor(uid, wave, final, grade_dir, optional_grade=True,
                         stages={"Judge"} if early else None)

    # Reserved allocations take precedence even for unsuccessful attempts.
    for uid in sorted(risk_roster):
        for wave in (1, 2):
            dirs = tuple(safety / f"Wave{wave}_{name}" for name in ("Route", "Select", "Actor", "Judge"))
            linked(uid, wave, dirs)
            for arm in ("FULL", "EMPTY"):
                actor = bank.exact(dirs[2], uid, inputs[uid][arm])
                assign_actor(uid, wave, actor, dirs[3])
        linked(uid, 3, tuple(prior / f"Draw3_{name}" for name in (
            "Route", "Select", "SelectedActor", "Judge",
        )))

    for uid in sorted(utility_roster):
        dirs = tuple(utility / name for name in ("Route", "Select", "Actor", "Judge"))
        linked(uid, 1, dirs)
        for arm in ("FULL", "EMPTY"):
            actor = bank.exact(dirs[2], uid, inputs[uid][arm])
            assign_actor(uid, 1, actor, dirs[3])

    for uid in sorted(set(cases) - risk_roster.keys() - utility_roster.keys()):
        route_request = inputs[uid]["selection_requests"]["query"]
        sources = [dirs for dirs in role_dirs.values()
                   if bank.exact(dirs[0], uid, route_request, optional=True)]
        if len(sources) > 1:
            raise ValueError("Independent selected archive registration is ambiguous")
        if sources:
            linked(uid, 1, sources[0])
        elif bank.exact(selector_early, uid, route_request, optional=True, stages={"Actor"}):
            linked(uid, 1, (selector_early, selector_early, actor_early, actor_early), early=True)

    # Only systematic, exposed comparison archives. Bind by provenance and
    # original dispatch time, never by result, retaining any failed attempt.
    extras = [(old / "persist_historical_utility_completion_v1" / "FullActor",
               old / "persist_historical_utility_completion_v1" / "FullNative")]
    extras += [(prior / f"Draw{wave}_SelectedActor", prior / f"Draw{wave}_Judge")
               for wave in (1, 2)]
    extras += [(old / "persist_memgate_matched_actor_v1" / f"Wave{wave}_Actor",
                old / "persist_memgate_matched_actor_v1" / f"Wave{wave}_Judge")
               for wave in (0, 1, 2)]
    for uid, case in sorted(cases.items()):
        repeats = 1 if case["category"] == "beneficial_memory_usage" else 3
        for arm in ("FULL", "EMPTY", "RUBRIC"):
            wire = inputs[uid][arm]
            hits = [(r, grade_dir) for actor_dir, grade_dir in extras
                    if (r := bank.exact(actor_dir, uid, wire, optional=True)) is not None]
            pending = [(r, gd) for r, gd in sorted(hits, key=lambda pair: (
                pair[0]["started"], pair[0]["ref"],
            )) if r["ref"] not in physical]
            for wave in range(1, repeats + 1):
                if pending and ("Actor", sha(wire)) not in covered[uid, wave]:
                    receipt, grade_dir = pending.pop(0)
                    assign_actor(uid, wave, receipt, grade_dir, optional_grade=True)

    return covered
