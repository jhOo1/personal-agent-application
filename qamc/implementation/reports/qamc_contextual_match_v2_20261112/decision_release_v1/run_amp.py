"""Frozen 21-task shared ARM comparison with CAR receipt infrastructure."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from amp_controller import ADAPTER, AUTHORIZE, FRAME, FREE, authorize, free_view, task_frame
from amp_release import compile_release
from pilot_panel import build
from qamc.common import sha
from run_car import archive, check_wire, engine, grading, packets, probe, schedule, wire

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
ARMS = ("RAW", "FREE", "AMP")
CAP = {"Frame": 21, "Authority": 42, "Actor": 63, engine.RPE: 27, "BenchAttrs": 180, "PersistNative": 18}


def roster():
    all_cards = build()
    rpe = [c for c in all_cards if c["benchmark"] == "RPEval"]
    counts = Counter(r["group"] for r in rpe)
    paired = list(dict.fromkeys(r["group"] for r in rpe if counts[r["group"]] == 2))[:3]
    chosen = [r for r in rpe if r["group"] in paired or r["stratum"] == "contains_C"]
    chosen.append(next(r for r in rpe if counts[r["group"]] == 1 and r["stratum"] == "all_A"))
    bench = [c for c in all_cards if c["benchmark"] == "BenchPreS"]
    chosen.extend(bench[:6])
    persist = [c for c in all_cards if c["benchmark"] == "PersistBench"]
    for s in ("cross_domain", "sycophancy", "beneficial_memory_usage"):
        chosen.extend([r for r in persist if r["stratum"] == s][:2])
    if len(chosen) != 21 or len({(r["benchmark"], r["group"]) for r in chosen}) != 18:
        raise ValueError("Unexpected AMP development allocation")
    return chosen


def actor_request(card, view):
    original = card["T"]
    result = deepcopy(original)
    user = result["messages"][1]
    expected = {"history": [], "grounded_facts": [], "decision_controls": [], "memory_view": ""}
    if not view.keys() <= expected.keys():
        raise ValueError("Unexpected Actor view fields")
    data = {**expected, **view}
    user["content"] += "\n\n" + ADAPTER + "\n" + json.dumps(data, ensure_ascii=False)
    return check_wire(result)


def prepare():
    rows = roster()
    for c in rows:
        frame = frame_wire(c)
        check_wire(frame)
        check_wire(actor_request(c, {}))
    for b, tag in (("BenchPreS", "BenchAttrs"), ("PersistBench", "PersistNative")):
        cases, protocol, _ = archive.transfer.context(b)
        tentative = [{"uid": r["root"]["uid"], "method": m, "answer": r["base_answer"],
                      "actor_status": "OK"} for r in rows if r["benchmark"] == b for m in ARMS]
        grading_jobs, _ = archive.transfer.grading_jobs(b, tentative, cases, protocol)
        if len(grading_jobs) > CAP[tag]:
            raise ValueError("Estimated score batch exceeds contract")
    code = {name: sha((HERE / name).read_bytes()) for name in (
        "PROTOCOL.md", "amp_release.py", "amp_controller.py", "run_amp.py")}
    by = Counter(r["benchmark"] for r in rows)
    return rows, {"development_only": True, "scope": "exposed tasks only", "panel_sha256": sha(rows),
                  "counts": dict(by), "caps": CAP, "code": code, "arms": list(ARMS),
                  "frame_wires_sha256": sha([frame_wire(r) for r in rows])}


def frame_wire(card):
    return wire(FRAME, {"task": card["root"]["public_task"]})


def run(frozen, cards, live):
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = CAP
    by_uid = {r["root"]["uid"]: r for r in cards}
    identity = {"experiment_sha256": sha(frozen), "service_reference_sha256": probe.read_reference()[1]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        path = RUN / "EXECUTION.json"
        if live:
            probe.freeze(path, identity)
        elif probe.read(path) != identity:
            raise ValueError("Frozen run identity changed")

        def stage(name, jobs, cache=None):
            return engine.stage(name, schedule(jobs), identity, live, ledger, cache) if jobs else {}

        frames = stage("Frame", {(uid, "SHARED"): frame_wire(c) for uid, c in by_uid.items()})
        slots_by_uid, issues, auth_jobs = {}, {}, {}
        for (uid, _), reply in frames.items():
            if reply["status"] != "OK":
                issues[uid, "SHARED"] = reply["status"]
                continue
            try:
                slots_by_uid[uid] = task_frame(reply["answer"])
                packet = {**packets(by_uid[uid]), "frame": [
                    {"id": s.id, "kind": s.kind, "description": s.description} for s in slots_by_uid[uid]]}
                pair = {(uid, "SHARED"): wire(AUTHORIZE, packet), (uid, "FREE"): wire(FREE, packet)}
            except (ValueError, TypeError):
                issues[uid, "SHARED"] = "INVALID_FRAME"
                slots_by_uid.pop(uid, None)
                continue
            auth_jobs.update(pair)
        replies = stage("Authority", auth_jobs)
        views, actor_jobs = {}, {}
        for (uid, method), reply in replies.items():
            if reply["status"] != "OK":
                issues[uid, method] = reply["status"]
                continue
            c = by_uid[uid]
            sources = {r["memory_id"]: r["text"] for r in c["root"]["original_sources"]}
            slots = slots_by_uid[uid]
            try:
                if method == "FREE":
                    generated = {"FREE": free_view(reply["answer"])}
                else:
                    plan = authorize(reply["answer"], slots, sources)
                    generated = {"RAW": compile_release(slots, sources, plan, exposure="raw"),
                                 "AMP": compile_release(slots, sources, plan, exposure="partitioned")}
                if "RAW" in generated and generated["RAW"]["decision_controls"] != generated["AMP"]["decision_controls"]:
                    raise ValueError("RAW and AMP use different authorization guidance")
                actual = {(uid, m): actor_request(c, v) for m, v in generated.items()}
            except (ValueError, TypeError):
                issues[uid, method] = "INVALID_PROJECTION"
                continue
            views[uid, method] = generated
            actor_jobs.update(actual)
        actors = stage("Actor", actor_jobs)
        rows = []
        for uid, card in by_uid.items():
            for arm in ARMS:
                reply = actors.get((uid, arm))
                status = (reply["status"] if reply else issues.get((uid, arm), issues.get((uid, "SHARED"), "UNISSUED")))
                row = {k: card[k] for k in ("benchmark", "group", "stratum", "base_score")}
                row.update(uid=uid, method=arm, actor_status=status, sources=card["root"]["original_sources"],
                           answer=reply["answer"] if reply and status == "OK" else None, score=None, score_flags=None)
                if row["answer"] and sha(row["answer"]) == card["baseline_answer_sha256"]:
                    row.update(score=card["base_score"], score_flags=card["base_flags"], score_origin="EXACT_BASE")
                rows.append(row)
        grading(rows, stage)
        deltas = {}
        for uid in by_uid:
            mode = views.get((uid, "SHARED"))
            if mode:
                deltas[uid] = {
                    "history_count": len(mode["RAW"]["history"]),
                    "released_facts_count": len(mode["AMP"]["grounded_facts"]),
                    "effects_count": len(mode["AMP"]["decision_controls"]),
                    "wire_differs": actor_jobs[uid, "RAW"] != actor_jobs[uid, "AMP"],
                }
        out = {"rows": rows, "view_counts": deltas, "ledger": ledger,
               "calls": dict(Counter(r["unit"]["stage"] for r in ledger)),
               "statuses": dict(Counter(r["status"] for r in ledger)),
               "tokens": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
               "unknown_usage": sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger)}
        if live:
            probe.freeze(RUN / "RESULTS.json", out)
        elif probe.read(RUN / "RESULTS.json") != out:
            raise ValueError("Terminal AMP replay drift")
        print(json.dumps({k: out[k] for k in ("calls", "statuses", "tokens", "unknown_usage")}, sort_keys=True))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("freeze", "check", "run", "replay"))
    args = p.parse_args()
    cards, plan = prepare()
    if args.command == "freeze":
        RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
        probe.freeze(RUN / "FROZEN.json", plan)
    elif probe.read(RUN / "FROZEN.json") != plan:
        raise ValueError("Private frozen panel or implementation drift")
    if args.command in ("run", "replay"):
        run(plan, cards, args.command == "run")
    else:
        print(json.dumps(plan, indent=2, sort_keys=True))
