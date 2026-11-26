"""Dispatch only unfilled MemGate slots under the matched GEPA contract."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

from audit_memgate import BASE, BU, HERE, ROOT, prepare
from complete import engine, normalized, probe, read
from extend import archived, merge_stage, receipt
from qamc.common import sha

RUN = engine.RUN.with_name(HERE.name)
ARM = "MEMGATE"


def prior_wave(wave):
    name = "persist_equal_cap_safety_v1" if wave else "persist_equal_cap_development_v1"
    root = RUN.with_name(name)
    prefix = f"Wave{wave}_" if wave else ""
    return root, f"{prefix}Actor", f"{prefix}Judge"


def allocate(actors, cases, previous):
    old, _ = archived(actors, ROOT)
    allocations, used_history = {}, set()
    for wave in (0, 1, 2):
        root, actor_stage, _ = prior_wave(wave)
        jobs = {}
        candidates = {}
        for row in previous[wave]:
            if row["actor_sha256"] == sha(actors[row["uid"]]):
                candidates.setdefault(row["uid"], row)
        for uid in sorted(cases):
            if (cases[uid]["category"] == BU) != (wave == 0):
                continue
            row = candidates.get(uid)
            if row:
                answer = row["answer"]
                if answer:
                    if receipt(root, actor_stage, uid, actors[uid]) != answer:
                        raise ValueError("Matched-wave Actor response did not verify")
                    jobs[uid] = {"origin": "MATCHED_WAVE", "status": "OK", "answer": answer,
                                 "request_sha256": row["actor_sha256"], "prior_grade": row["judge"]}
                else:
                    jobs[uid] = {"origin": "MATCHED_WAVE", "status": row["status"], "answer": None,
                                 "request_sha256": row["actor_sha256"]}
                continue
            row = old.get(uid)
            if row and uid not in used_history:
                if RUN.name in Path(row["archive"]).parts:
                    continue
                if root.name in Path(row["archive"]).parts or "persist_equal_cap_safety_v1" in Path(row["archive"]).parts:
                    continue  # Samples assigned to the old waves are never moved between them.
                jobs[uid] = row
                used_history.add(uid)
        allocations[str(wave)] = jobs
    return allocations


def score_wire(api, configuration, bounds, task, case, uid, answer):
    scorer = api["persist"].author.ext.parent.persist
    _, rubrics, fmt = scorer.upstream()
    wire = api["persist"].author.ext.text_request(
        rubrics[case["category"]], fmt["build_judge_prompt"](task["memories"], task["query"], answer),
        configuration["model"], configuration["stages"][api["persist"].STAGE]["max_tokens"])
    if normalized(wire, answer) != bounds[uid]:
        raise ValueError("Grading request differs from archived comparison")
    return wire, scorer


def comparator_contracts():
    safety = run_path(str(BASE / "persist_equal_cap_safety_v1/run_safety.py"))["prepare"]()
    utility = run_path(str(BASE / "persist_equal_cap_development_v1/run_bu.py"))["prepare"]()
    return {0: utility, 1: safety, 2: safety}


def verify_cached_grades(panels, allocations, tasks, cases):
    for wave, rows in allocations.items():
        root, _, stage = prior_wave(int(wave))
        panel = panels[int(wave)]
        for uid, row in rows.items():
            if not row.get("prior_grade") or row["status"] != "OK":
                continue
            grade = row["prior_grade"]
            wire, _ = score_wire(panel[1], panel[-2], panel[-1], tasks[uid], cases[uid], uid, row["answer"])
            if grade["request_sha256"] != sha(wire):
                raise ValueError("Matched-wave score request did not verify")
            if grade["status"] == "OK" and receipt(root, stage, uid, wire) != grade["answer"]:
                raise ValueError("Matched-wave score receipt did not verify")


def run(pin, actors, selection, cases, tasks, allocations, panels):
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {f"Wave{wave}_{phase}": 19 if wave else 12 for wave in (0, 1, 2)
                  for phase in ("Actor", "Judge")}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    result, ledger = [], []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)
        for wave in (0, 1, 2):
            checkpoint = RUN / f"WAVE{wave}.json"
            if checkpoint.exists():
                saved = read(checkpoint)
                if saved["identity"] != identity:
                    raise ValueError("Wave identity drift")
                result.extend(saved["rows"])
                ledger.extend(saved["ledger"])
                continue
            calls = []
            panel = panels[wave]
            api, configuration, bounds = panel[1], panel[-2], panel[-1]
            jobs = {(u, ARM): wire for u, wire in actors.items()
                    if (cases[u]["category"] == BU) == (wave == 0)}
            cache = {(u, ARM): x for u, x in allocations[str(wave)].items()}
            answers = merge_stage(f"Wave{wave}_Actor", jobs, cache, identity, calls)
            grades, score_cache = {}, {}
            scorer = api["persist"].author.ext.parent.persist
            for key, answer in answers.items():
                if answer["status"] != "OK":
                    continue
                uid, _ = key
                wire, scorer = score_wire(api, configuration, bounds, tasks[uid], cases[uid], uid, answer["answer"])
                grades[key] = wire
                prior = answer.get("prior_grade")
                if prior:
                    score_cache[key] = {**prior, "origin": "MATCHED_WAVE"}
            archival, _ = archived({k: w for k, w in grades.items() if k not in score_cache}, ROOT)
            for key, row in archival.items():
                if RUN.name not in Path(row["archive"]).parts:
                    score_cache[key] = row
            reply = merge_stage(f"Wave{wave}_Judge", grades, score_cache, identity, calls)
            records = []
            for key, actor in answers.items():
                uid, _ = key
                judge = reply.get(key, {})
                status = judge.get("status", actor["status"])
                score = None
                if judge.get("status") == "OK":
                    try:
                        score = scorer.score(cases[uid]["category"], judge["answer"])
                    except (ValueError, TypeError, KeyError):
                        status = "INVALID_SCORE"
                records.append({"uid": uid, "wave": wave, "category": cases[uid]["category"],
                                "status": status, "actor": actor, "judge": judge, "score": score,
                                "selected": selection[uid]})
            probe.freeze(checkpoint, {"rows": records, "ledger": calls, "identity": identity})
            result.extend(records)
            ledger.extend(calls)
        if len(ledger) > 100 or len(result) != 50:
            raise ValueError("Matched comparator accounting mismatch")
        probe.freeze(RUN / "RESULTS.json", {"rows": result, "ledger": ledger, "identity": identity})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("check", "freeze", "run"))
    cli.add_argument("assets", type=Path)
    cli.add_argument("embedding", type=Path)
    args = cli.parse_args()
    pin, _, actors, selection, cases, tasks, previous = prepare(args.assets, args.embedding)
    pin["runner_sha256"] = sha(Path(__file__).read_bytes())
    panels = comparator_contracts()
    frozen = read(RUN / "FROZEN.json") if args.action == "run" else None
    allocations = frozen["actor_cache"] if frozen is not None else allocate(actors, cases, previous)
    pin["actor_cache_sha256"] = sha(allocations)
    verify_cached_grades(panels, allocations, tasks, cases)
    if args.action == "run":
        if pin != frozen["pin"]:
            raise ValueError("Experiment input or runner drift")
        run(pin, actors, selection, cases, tasks, allocations, panels)
    elif args.action == "freeze":
        probe.freeze(RUN / "FROZEN.json", {"pin": pin, "actor_cache": allocations})
    print(json.dumps({"cache": {w: dict(Counter(row["origin"] for row in a.values()))
                                for w, a in allocations.items()},
                      "actor_bound": 50 - sum(len(a) for a in allocations.values()),
                      "protocol_sha256": sha(pin)}, sort_keys=True))


if __name__ == "__main__":
    main()
