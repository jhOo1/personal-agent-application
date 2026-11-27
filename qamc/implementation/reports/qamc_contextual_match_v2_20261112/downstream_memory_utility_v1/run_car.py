"""Freeze, run, or replay the three-benchmark CAR development pilot."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from assembler import anchors, segment
from controller import FINAL, OPPORTUNITY, finalize, opportunity
from exposure_wires import rp_projection
from pilot_panel import ARMS, CAP, archive, build, inventory, project_bench_or_persist, source
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from trial_reassembly import grading

HERE = Path(__file__).resolve().parent
engine, probe = archive.engine, archive.probe
RUN = engine.RUN.with_name("car_shared_pilot_v1")
MAX_INPUT = 32768


def check_wire(wire):
    validate_public_request(wire)
    if token_estimate(canonical(wire["messages"])) > MAX_INPUT:
        raise ValueError("Frozen input capacity exceeded")
    return wire


def wire(prompt, packet):
    return check_wire(archive.body(prompt, packet, 8192))


def packets(card):
    root = card["root"]
    return {"task": root["public_task"], "source_evidence": root["original_sources"]}


def donor_wire(card, proposal, bridge):
    sources = card["root"]["original_sources"]
    wanted = {r["id"] for r in proposal["evidence"]}
    chosen = [i for i, r in enumerate(sources) if r["memory_id"] in wanted]
    if card["benchmark"] == "RPEval":
        old = json.loads(card["origin_wire"]["messages"][1]["content"])
        use = {r["memory_id"]: "B" for r in old["preference_use_policy"]
               if r["memory_id"] in wanted and r["policy"] == "A"}
        return rp_projection(card["origin_wire"], chosen, use)
    notes = None
    if card["benchmark"] == "BenchPreS":
        guidance = ("For " + proposal["affected_party"] + ", make this change only as supported by the "
                    "current task and this source: " + proposal["change"]
                    + " Preserve this condition: " + proposal["protect"])
        notes = dict.fromkeys(chosen, guidance)
    return project_bench_or_persist(card, chosen, bridge, notes)


def preflight():
    cards = build()
    for c in cards:
        check_wire(c["T"])
        check_wire(c["H"])
    revision = dict(FINAL)
    files = ("run_car.py", "pilot_panel.py", "controller.py", "action_commit.py", "exposure_wires.py",
             "PILOT_PROTOCOL.md")
    code = {p: sha((HERE / p).read_bytes()) for p in files}
    for benchmark, key in (("BenchPreS", "BenchAttrs"), ("PersistBench", "PersistNative")):
        selected = [r for r in cards if r["benchmark"] == benchmark]
        cases, protocol, _ = archive.transfer.context(benchmark)
        provisional_rows = [{"uid": r["root"]["uid"], "method": arm, "answer": r["base_answer"],
                             "actor_status": "OK"} for r in selected for arm in ARMS]
        score_wires, _ = archive.transfer.grading_jobs(benchmark, provisional_rows, cases, protocol)
        if len(score_wires) > CAP[key]:
            raise ValueError("Frozen scorer cap cannot cover all arms")
        for w in score_wires.values():
            check_wire(w)
    return {"inventory": inventory(cards), "code": code, "panel_sha256": sha(cards),
            "scope": "previously exposed development only", "caps": CAP, "final_arms": list(revision)}, cards


def schedule(jobs):
    return dict(sorted(jobs.items(), key=lambda kv: sha(["car-order-v1", *kv[0]])))


def make_cache(cards):
    found = {}
    for card in cards:
        for name, answer in card["reused"].items():
            key = sha(card[name])
            if found.setdefault(key, answer) != answer:
                raise ValueError("Archived exact wire has incompatible answers")
    return found


def run(plan, cards, live):
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = CAP
    ledger = []
    bridge = source.PersistAuthorBridge(source.previous.parent.AUTHOR)
    with probe.runner_lock(RUN / "runner.lock"):
        path = RUN / "EXECUTION.json"
        identity = {"experiment_sha256": sha(plan), "service_reference_sha256": probe.read_reference()[1]}
        if live:
            probe.freeze(path, identity)
        elif probe.read(path) != identity:
            raise ValueError("Frozen run identity changed")

        def stage(name, jobs, cache=None):
            return engine.stage(name, schedule(jobs), identity, live, ledger, cache) if jobs else {}

        cache = make_cache(cards)
        endpoints = stage("Endpoints", {(c["root"]["uid"], k): c[k] for c in cards for k in ("T", "H")}, cache)
        by_uid = {c["root"]["uid"]: c for c in cards}
        for reply in endpoints.values():
            if reply["status"] == "OK":
                cache[reply["request_sha256"]] = reply["answer"]
        candidates, issues, proposal_wires = {}, {}, {}
        for uid, c in by_uid.items():
            available = {k: endpoints[uid, k]["answer"] for k in ("T", "H")
                         if endpoints[uid, k]["status"] == "OK"}
            if len(available) != 2:
                issues[uid] = "ENDPOINT_TRANSPORT"
                continue
            candidates[uid] = available
            try:
                proposal_wires[uid, "SHARED"] = wire(OPPORTUNITY, {**packets(c), "candidates": available})
            except ValueError:
                issues[uid] = "OPPORTUNITY_CAPACITY"
        replies = stage("Opportunity", proposal_wires)
        proposals, donor_jobs = {}, {}
        for (uid, _), response in replies.items():
            c = by_uid[uid]
            if response["status"] != "OK":
                issues[uid] = response["status"]
                continue
            known = {s["memory_id"]: s["text"] for s in c["root"]["original_sources"]}
            try:
                proposed = opportunity(response["answer"], known)
                if proposed:
                    donor_jobs[uid, "D"] = check_wire(donor_wire(c, proposed, bridge))
                proposals[uid] = proposed
            except (TypeError, ValueError):
                issues[uid] = "INVALID_OPPORTUNITY_OR_DONOR_WIRE"

        donors = stage("Donor", donor_jobs, cache)
        final_jobs, final_inputs = {}, {}
        for uid, proposed in proposals.items():
            c = by_uid[uid]
            candidate_map = candidates[uid]
            candidate_map["F"] = c["base_answer"]
            donor = donors.get((uid, "D"))
            if donor:
                if donor["status"] != "OK":
                    issues[uid] = donor["status"]
                    continue
                candidate_map["D"] = donor["answer"]
            blocks = {k: [r["text"] for r in segment(text)] for k, text in candidate_map.items()}
            protected = [r["literal"] for r in anchors(c["root"]["public_task"], c["base_answer"])]
            packet = {**packets(c), "candidates": blocks, "opportunity": proposed,
                      "fallback": "F", "protected_literals": protected}
            try:
                request_set = {(uid, arm): wire(FINAL[arm], packet) for arm in ARMS}
            except ValueError:
                issues[uid] = "FINAL_CAPACITY"
                continue
            final_jobs.update(request_set)
            final_inputs[uid] = (blocks, protected)
        final = stage("Final", final_jobs)
        rows = []
        for uid, card in by_uid.items():
            for arm in ARMS:
                response = final.get((uid, arm))
                row = {"uid": uid, "method": arm, "benchmark": card["benchmark"],
                       "group": card["group"], "stratum": card["stratum"],
                       "actor_status": response["status"] if response else issues.get(uid, "NOT_EVALUABLE"),
                       "answer": None, "score": None, "score_flags": None,
                       "base_score": card["base_score"], "sources": card["root"]["original_sources"]}
                rows.append(row)
                if row["actor_status"] != "OK":
                    continue
                blocks, protected = final_inputs[uid]
                result = finalize(arm, response["answer"], blocks, "F", protected)
                row.update(asdict(result))
                row["answer_sha256"] = sha(result.answer)
                if row["answer_sha256"] == card["baseline_answer_sha256"]:
                    row.update(score=card["base_score"], score_flags=card["base_flags"], score_origin="EXACT_BASE")
        grading(rows, stage)
        results = {"rows": rows, "ledger": ledger, "endpoint_records": list(endpoints.values()),
                   "proposals": proposals, "donors": list(donors.values()),
                   "calls": dict(Counter(r["unit"]["stage"] for r in ledger)),
                   "statuses": dict(Counter(r["status"] for r in ledger)),
                   "tokens": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
                   "unknown_usage": sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger)}
        if live:
            probe.freeze(RUN / "RESULTS.json", results)
        elif probe.read(RUN / "RESULTS.json") != results:
            raise ValueError("CAR settlement replay drift")
        print(json.dumps({k: results[k] for k in ("calls", "statuses", "tokens", "unknown_usage")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "check", "run", "replay"))
    args = parser.parse_args()
    current, cards = preflight()
    if args.command == "freeze":
        RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
        probe.freeze(RUN / "FROZEN.json", current)
    elif probe.read(RUN / "FROZEN.json") != current:
        raise ValueError("Private frozen roster or implementation drift")
    if args.command in ("run", "replay"):
        run(current, cards, args.command == "run")
    else:
        print(json.dumps(current, indent=2, sort_keys=True))
