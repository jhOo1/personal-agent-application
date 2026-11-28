"""Reconstruct completed fixed-exposure draws from physical receipts without requests."""
import argparse
from collections import Counter
import json

import repeat as study


def read_wave(wave, pin, mapping, jobs, build_grade):
    study.probe.RUN = study.RUN
    study.probe.OUT = study.engine.OUT = study.OUT
    actor = f"FixedExposureActor{wave}"
    grader = f"FixedExposureGrade{wave}"
    study.engine.CAP = {actor: len(jobs), grader: len(jobs)}
    identity = {"experiment_sha256": study.sha(pin),
                "service_reference_sha256": pin["service_reference_sha256"]}
    saved = study.read(study.OUT / f"WAVE{wave}.json")
    ledger = []

    def reconstruct(stage, requests):
        journal = study.RUN / stage / "visible"
        physical = set()
        for file in journal.glob("*/record.json"):
            record = study.read(file)
            unit = record["unit"]
            key = unit["root_id"], unit["method"]
            if (key in physical or key not in requests
                    or study.read(file.with_name("request.json")) != requests[key]
                    or record["request_sha256"] != study.sha(requests[key])
                    or record["automatic_retries"] != 0):
                raise ValueError(f"Physical request mismatch in {stage}")
            physical.add(key)
        if len(physical) != len({study.sha(wire) for wire in requests.values()}):
            raise ValueError(f"Physical request coverage mismatch in {stage}")
        return study.engine.stage(stage, requests, identity, False, ledger) if requests else {}

    texts = reconstruct(actor, jobs)
    judges = {key: build_grade(key[0], row["answer"]) for key, row in texts.items() if row["status"] == "OK"}
    grades = reconstruct(grader, judges)
    for (uid, arm), key in mapping.items():
        status = texts.get(key, {}).get("status", "RETAINED_FIRST_DRAW_MISSING")
        rating = study.grade(grades.get(key, {}).get("answer"), "sycophancy")
        if (rating, status) != (saved["scores"][uid][arm], saved["status"][uid][arm]):
            raise ValueError("Per-arm result does not reproduce from raw receipts")
    if ledger != saved["ledger"]:
        raise ValueError("Wave ledger does not reproduce")
    return saved


def audit(waves):
    pin, first, mapping, jobs, score = study.prepare_repeat()
    if study.read(study.OUT / "FROZEN.json") != pin:
        raise ValueError("Repeat contract drift")
    records = [read_wave(wave, pin, mapping, jobs, score) for wave in waves]
    outputs = {arm: Counter() for arm in study.POLICIES}
    trajectories = {}
    for uid, row in first.items():
        trajectories[uid] = {}
        for arm in study.POLICIES:
            ratings = [row["ratings"][arm], *(record["scores"][uid][arm] for record in records)]
            trajectories[uid][arm] = ratings
            outputs[arm].update(study.risk_state([rating]) for rating in ratings)
    ledger = [entry for record in records for entry in record["ledger"]]
    return {
        "settled_waves": waves,
        "full_three_draw_scoreboard": study.result_summary(first, mapping, records) if waves == list(study.WAVES) else None,
        "draw_ratings_by_arm": outputs,
        "trajectories": trajectories,
        "requests_by_stage": Counter(r["unit"]["stage"] for r in ledger),
        "request_status": Counter(r["status"] for r in ledger),
        "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
        "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
        "automatic_retries": sum(r["automatic_retries"] for r in ledger),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", nargs="+", type=int, choices=study.WAVES, default=list(study.WAVES))
    args = parser.parse_args()
    if len(set(args.wave)) != len(args.wave) or args.wave != sorted(args.wave):
        parser.error("Provide distinct waves in order")
    print(json.dumps(audit(args.wave), sort_keys=True, indent=2))
