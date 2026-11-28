"""Secondary observations only on roots not issued to the independent reviewer."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import trial as primary

HERE = Path(__file__).resolve().parent
RUN = primary.RUN.with_name(HERE.name + "_qwen_unissued")
PRIVATE = RUN / "private"
MODEL = "qwen3.8-flash"
STAGE = "FocalSecondary"
read, sha = primary.read, primary.sha


def prepare():
    _, roster, original = primary.setup()
    prior = read(primary.PRIVATE / "RESULTS.json")
    statuses = Counter(r["status"] for r in prior["rows"])
    if statuses != {"FAILED_DELIVERY_UNKNOWN": 2, "UNISSUED": 12}:
        raise ValueError("The independent reviewer was not stopped at the two transport attempts")
    unissued = {r["key"] for r in prior["rows"] if r["status"] == "UNISSUED"}
    cards = {k: v for k, v in roster.items() if k in unissued}
    jobs = {key: dict(w, model=MODEL, max_tokens=4096, temperature=0,
                      stream_options={"include_usage": True}) for key, w in original.items() if key[0] in cards}
    marker = {"requests": [[key[0], sha(w)] for key, w in jobs.items()],
              "prior": sha((primary.PRIVATE / "RESULTS.json").read_bytes()),
              "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "FALLBACK_PROTOCOL.md").read_bytes()),
              "service": primary.probe.read_reference()[1]}
    return marker, cards, jobs


def trial(pin, cards, jobs):
    engine, probe = primary.engine, primary.probe
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {STAGE: 12}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        received = engine.stage(STAGE, jobs, {"experiment_sha256": sha(pin),
                                "service_reference_sha256": pin["service"]}, True, ledger)
        rows = {}
        for key, rec in received.items():
            disposition = rec["status"]
            focal, observations = None, {}
            if disposition == "OK":
                packet = json.loads(jobs[key]["messages"][-1]["content"])
                try:
                    focal, observations = primary.parse(rec["answer"], packet["answers"])
                except (ValueError, TypeError, KeyError):
                    disposition = "INVALID_SCHEMA"
            rows[key[0]] = {"status": disposition, "focal": focal, "cells": observations,
                            "uid": cards[key[0]]["uid"]}
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": rows, "ledger": ledger})


def report(cards):
    data = read(PRIVATE / "RESULTS.json")
    stats, acts = defaultdict(Counter), defaultdict(Counter)
    for key, row in data["rows"].items():
        c = cards[key]
        for model, names in primary.crossed["NAMES"].items():
            k = f"{c['intent']}/{model}"
            per = stats[k]
            per["assigned"] += 1
            states = {arm: row["cells"].get(side, {}).get("state") for side, (alias, arm)
                      in c["sides"].items() if alias == model}
            left, right = (states[a] for a in names)
            if left in (None, "UNCLEAR") or right in (None, "UNCLEAR"):
                per["unknown"] += 1
                continue
            per[left + " -> " + right] += 1
            for role, selector in (("Task", names[0]), ("History", names[1]), ("IPE_C", c["selected"][model])):
                acts[k + "/" + role][states[selector]] += 1
    ledger = data["ledger"]
    physical = [read(f) for f in RUN.glob("*/visible/*/record.json")]
    def match(row):
        return row["unit"]["root_id"], row["request_sha256"], row["status"]
    if Counter(map(match, ledger)) != Counter(map(match, physical)):
        raise ValueError("Ledger drift")
    print(json.dumps({"paired": stats, "states": acts, "parser": Counter(r["status"] for r in data["rows"].values()),
                      "physical": Counter(r["status"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    pin, cards, jobs = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = PRIVATE / "FREEZE.json"
    if action == "freeze":
        primary.probe.freeze(marker, pin)
        print("Only previously unissued roots", len(cards))
    elif read(marker) != pin:
        raise ValueError("Frozen fallback identity changed")
    elif action == "run":
        trial(pin, cards, jobs)
    else:
        report(cards)
