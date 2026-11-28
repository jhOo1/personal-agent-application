"""Measure each member of a complementary pair at the original Actor input."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from check_exposure_fr3 import judge_wire, prepare
from complete import actor_request, engine, probe, sha
from transfer_replay import persist

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parents[2] / "runs" / HERE.parent.name
RUN = ARCHIVE / HERE.name
PRIVATE = RUN / "private"
FRESH = ARCHIVE / "persist_utility_fresh_deployment_v1"
ROOTS = {"3776469a": (1, 4), "dbcf603f": (1, 12), "125d165e": (5, 6), "40a9b964": (1, 6)}
CELLS = {"NONE": (False, False), "FIRST": (True, False), "SECOND": (False, True), "BOTH": (True, True)}


def read(path):
    return json.loads(path.read_bytes())


def matching(wires):
    bank = {}
    if not wires:
        return bank
    placeholders = ",".join("?" for _ in wires)
    for path in sorted(ARCHIVE.parent.glob("**/samples.sqlite")):
        if RUN in path.parents:
            continue
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='samples'").fetchone():
                continue
            for digest, body, state, payload in db.execute(
                f"""SELECT request_sha,request_json,status,response_json FROM samples
                    WHERE request_sha IN ({placeholders}) ORDER BY rowid""",
                tuple(wires),
            ):
                assert wires[digest] == json.loads(body)
                data = json.loads(payload) if payload else {}
                accepted = state == "COMPLETE" and bool(data.get("answer"))
                bank.setdefault(digest, {"status": "OK" if accepted else state, "answer": data.get("answer")})
    return bank


def fresh_record(stage, wire):
    digest = sha(wire)
    for path in (FRESH / stage / "visible").glob("*/record.json"):
        metadata = read(path)
        if metadata["request_sha256"] == digest:
            assert read(path.with_name("request.json")) == wire and metadata["status"] == "OK"
            return read(path.with_name("response.json"))
    raise ValueError("Fresh full-history archive does not contain the exact request")


def build():
    cases, inputs, protocol, judge, bounds = prepare()
    grade = judge_wire(cases, inputs, judge, bounds)
    scores = {r["uid"]: r for r in read(FRESH / "private/SETTLED.json")["rows"] if r["arm"] == "FULL"}
    cards, jobs, historical = {}, {}, {}
    scorer = persist.author.ext.parent.persist
    for prefix, pair in ROOTS.items():
        uid, = [u for u in cases if u.split("/")[-1].startswith(prefix)]
        case = cases[uid]
        assert case["category"] == "beneficial_memory_usage"
        task = inputs[uid]["public"]
        memories = task["memories"]
        assert len(set(memories)) == len(memories) and max(pair) < len(memories)
        cards[uid] = case["group_id"]
        for label, present in CELLS.items():
            removed = {index for index, keep in zip(pair, present) if not keep}
            history = [memory for index, memory in enumerate(memories) if index not in removed]
            wire = actor_request(case, task["query"], history, protocol, protocol["prompts"]["gepa"])
            if label != "BOTH":
                jobs[uid, label] = wire
                continue
            assert wire == inputs[uid]["FULL"]
            answer = fresh_record("Actor", wire)["answer"]
            gpt = grade(uid, answer)
            qwen = dict(gpt, model="qwen3.8-flash", max_tokens=8192)
            grades = {}
            for name, request in (("GPT", gpt), ("Qwen", qwen)):
                rating = scorer.score(case["category"], fresh_record(name, request)["answer"])["rating"]
                assert rating == scores[uid][name]
                grades[name] = rating
            historical[uid] = {"answer": answer, "wire": sha(wire), **grades}
    assert len(set(cards.values())) == len(ROOTS)
    cache = matching({sha(w): w for w in jobs.values()})
    pin = {"code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE/"PROTOCOL.md").read_bytes()),
           "wires": [[uid, label, sha(w)] for (uid, label), w in jobs.items()],
           "historical_sha256": sha(historical), "cached_sha256": sha(cache), "service": probe.read_reference()[1]}
    return pin, cards, jobs, historical, cache, grade


def run(pin, jobs, historical, cache, grade):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger = []

    def dispatch(stage, wires, known):
        digests = {key: sha(wire) for key, wire in wires.items()}
        pending = {(digest, "cell"): wires[key] for key, digest in digests.items() if digest not in known}
        engine.CAP[stage] = 12
        new = engine.stage(stage, pending, identity, True, ledger) if pending else {}
        return {key: known[digest] if digest in known else new[digest, "cell"]
                for key, digest in digests.items()}

    with probe.runner_lock(RUN / "runner.lock"):
        if (PRIVATE/"SETTLED.json").exists():
            raise ValueError("Frozen study already settled")
        replies = dispatch("Actor", jobs, cache)
        papers = {key: grade(key[0], result["answer"]) for key, result in replies.items()
                  if result["status"] == "OK" and result.get("answer")}
        qwen = {key: dict(wire, model="qwen3.8-flash", max_tokens=8192) for key, wire in papers.items()}
        grades = {}
        for name, wires in (("GPT", papers), ("Qwen", qwen)):
            grades[name] = dispatch(name, wires, matching({sha(w):w for w in wires.values()}))
        rows = []
        scorer = persist.author.ext.parent.persist
        for (uid, label), rec in replies.items():
            row = {"uid": uid, "cell": label, "status": rec["status"], "answer": rec.get("answer")}
            for name, bank in grades.items():
                row[name] = None
                result = bank.get((uid, label), {})
                if result.get("status") == "OK":
                    try:
                        row[name] = scorer.score("beneficial_memory_usage", result["answer"])["rating"]
                    except (TypeError, KeyError, ValueError):
                        pass
            rows.append(row)
        rows.extend({"uid": uid, "cell": "BOTH", "status": "OK_ARCHIVE", **record}
                    for uid, record in historical.items())
        probe.freeze(PRIVATE/"SETTLED.json", {"rows": rows, "ledger": ledger})


def report():
    data = read(PRIVATE/"SETTLED.json")
    ledger = data["ledger"]
    physical = [read(f) for f in RUN.glob("*/visible/*/record.json")]
    def key(r):
        return r["unit"]["stage"], r["request_sha256"], r["status"]
    assert Counter(map(key,ledger)) == Counter(map(key,physical))
    rows = [{k: v for k, v in row.items() if k not in {"answer", "wire"}} for row in data["rows"]]
    assert len(rows) == 16
    print(json.dumps({"cells": rows, "calls": len(ledger),
                      "status": Counter(r["status"] for r in ledger),
                      "stages": Counter(r["unit"]["stage"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens",0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    if action == "report":
        report()
    else:
        pin, cards, jobs, historical, cache, grade = build()
        PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        file = PRIVATE / "FREEZE.json"
        if action == "freeze":
            probe.freeze(file, pin)
            print(len(cards), "roots;", len(jobs), "new cells;", len(cache), "cached")
        elif read(file) == pin:
            run(pin, jobs, historical, cache, grade)
        else:
            raise ValueError("Frozen inputs changed")
