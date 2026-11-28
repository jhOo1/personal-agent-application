"""Grade the exact published answers already matched to Kimi and GPT-4.1."""
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import sys

from check_exposure_fr3 import judge_wire, prepare
from complete import engine, probe
from qamc.common import sha
from transfer_replay import persist


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = ROOT / "runs" / HERE.parent.name
OUT = RUNS / HERE.name / "private"
RELEASE = ROOT / "literature/qamc_pa_v1/PersistBench/experiments/multi_turn/paper_traces/baseline_all_models.json"


def read(path):
    return json.loads(path.read_bytes())


def build():
    first = RUNS / "persist_released_grade_agreement_v1/private"
    risk = RUNS / "persist_release_risk_epochs_v1/private"
    first_pin = read(first / "FROZEN.json")
    epoch_pin = read(risk / "FROZEN.json")
    first_hashes = {(u, model): digest for u, model, digest in first_pin["wires"]}
    grades = [dict(r, draw=0) for r in read(first / "SETTLED.json")["rows"]
              if r["category"] == "beneficial_memory_usage"]
    grades.extend(read(risk / "SETTLED.json")["rows"])
    previous = {(r["root"], r["model"], r["draw"]): r for r in grades}
    assert len(previous) == len(grades) == 125
    release = RELEASE.read_bytes()
    assert sha(release) == first_pin["release"] == epoch_pin["release"]
    cases, items, _, judge, bounds = prepare()
    render = judge_wire(cases, items, judge, bounds)
    rows, wires, later_hashes = {}, {}, []
    roots = {key[0] for key in previous}
    for entry in json.loads(release)["entries"].values():
        task = {k: entry[k] for k in ("query", "memories")}
        uid = "persistbench/" + sha(task)[:20]
        if uid not in roots:
            continue
        assert items[uid]["public"] == task
        for name, model in entry["results"].items():
            for draw, generation in enumerate(model["generations"]):
                key = (uid, name.replace("/", "_"), draw)
                if key not in previous:
                    continue
                grade = previous[key]
                assert draw == generation["generation_index"] and not generation["error"]
                assert grade["released"] == int(generation["judge"]["score"])
                old_wire = render(uid, generation["memory_response"])
                old_hash = sha(old_wire)
                if draw == 0:
                    assert old_hash == first_hashes[key[:2]]
                else:
                    later_hashes.append(old_hash)
                wire = dict(old_wire, model="qwen3.8-flash", max_tokens=8192)
                digest = sha(wire)
                wires[digest] = wire
                rows[key] = {**grade, "wire": digest}
    assert sorted(later_hashes) == epoch_pin["wires"]
    assert rows.keys() == previous.keys()
    return rows, wires, first_pin["release"]


def existing_replies(wires):
    cached = {}
    for path in sorted((ROOT / "runs").glob("**/samples.sqlite")):
        if (RUNS / HERE.name) in path.parents:
            continue
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as db:
            tables = db.execute("SELECT name FROM sqlite_master WHERE name='samples'").fetchone()
            if not tables:
                continue
            marks = ",".join("?" for _ in wires)
            records = db.execute(
                f"SELECT request_sha, request_json, status, response_json FROM samples WHERE request_sha IN ({marks}) ORDER BY rowid",
                tuple(wires),
            )
            for digest, body, state, payload in records:
                assert wires[digest] == json.loads(body)
                reply = json.loads(payload) if payload else {}
                record = {"status": state, "answer": reply.get("answer")}
                cached.setdefault(digest, record)
    return cached


def main():
    mode = sys.argv[1]
    rows, wires, release = build()
    cached = existing_replies(wires)
    pending = sorted(wires.keys() - cached.keys())
    pin = dict(release_sha256=release, rows_sha256=sha(list(rows.values())),
               cached_sha256=sha(cached), pending=pending,
               protocol_sha256=sha((HERE / "PROTOCOL.md").read_bytes()),
               code_sha256=sha(Path(__file__).read_bytes()))
    OUT.mkdir(parents=True, exist_ok=True)
    probe.freeze(OUT / "FROZEN.json", pin)
    print(len(rows), "positions;", len(wires), "distinct;", len(cached), "cached;", len(pending), "assigned", flush=True)
    if mode == "freeze":
        return
    assert mode == "run"
    engine.OUT = probe.OUT = OUT
    probe.RUN = OUT.parent
    engine.CAP["Judge"] = len(pending)
    identity = dict(experiment_sha256=sha(pin), service_reference_sha256=probe.read_reference()[1])
    ledger = []
    jobs = {(digest, "qwen"): wires[digest] for digest in pending}
    with probe.runner_lock(OUT.parent / "runner.lock"):
        new = engine.stage("Judge", jobs, identity, True, ledger) if jobs else {}
        replies = {**cached, **{digest: value for (digest, _), value in new.items()}}
        for row in rows.values():
            receipt = replies[row["wire"]]
            row.update(qwen=None, qwen_status=receipt["status"])
            if receipt["status"] == "OK":
                try:
                    row["qwen"] = persist.author.ext.parent.persist.score(row["category"], receipt["answer"])["rating"]
                except (ValueError, KeyError, TypeError):
                    row["qwen_status"] = "INVALID_SCORE"
        probe.freeze(OUT / "SETTLED.json", dict(rows=list(rows.values()), ledger=ledger, cache_count=len(cached)))


if __name__ == "__main__":
    main()
