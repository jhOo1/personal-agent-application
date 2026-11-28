"""Compare released external answers on the two exact shared screened tasks."""
import argparse
from collections import Counter
import json
from pathlib import Path

from first_draw import PRIVATE as INTERNAL, ROOT, RUN as SCREEN, engine, extend, grade, judge_wire, probe
from first_draw import exact_stage
from qamc.common import sha
from readout import verify
from verify_screened import prepare, read

RUN = SCREEN.with_name("persist_screened_external_bridge_v1")
OUT = RUN / "private"
SOURCE = ROOT / "literature/qamc_pa_v1/PersistBench/experiments/multi_turn/paper_traces/baseline_all_models.json"
STAGE = "ExternalScreenGrade"


def freeze():
    support, items, _, judge, envelopes = prepare()
    if read(SCREEN / "FROZEN_PREFLIGHT.json") != support:
        raise ValueError("Original screened roster changed")
    wire = judge_wire({u: r["case"] for u, r in items.items()}, items, judge, envelopes)
    release = SOURCE.read_bytes()
    grid = read(SOURCE)["entries"]
    jobs, released, categories = {}, {}, {}
    for row in grid.values():
        public = {key: row[key] for key in ("query", "memories")}
        uid = "persistbench/" + sha(public)[:20]
        if uid not in items:
            continue
        if public != items[uid]["public"] or uid in categories:
            raise ValueError("Exact release alignment failed")
        categories[uid] = items[uid]["case"]["category"]
        for model, data in sorted(row["results"].items()):
            draw = data["generations"][0]
            if draw["generation_index"] != 0 or draw["error"]:
                raise ValueError("Release does not supply a valid first draw")
            key = uid, model
            jobs[key] = wire(uid, draw["memory_response"])
            released[key] = int(draw["judge"]["score"])
    if len(jobs) != 10 or Counter(categories.values()) != {"sycophancy": 1, "beneficial_memory_usage": 1}:
        raise ValueError("Exact release overlap diverged")
    pin = {"release_hash": sha(release), "roster_hash": sha(support), "code_hash": sha(Path(__file__).read_bytes()),
           "protocol_hash": support["config_hash"], "request_hashes": [[u, m, sha(w)] for (u, m), w in jobs.items()]}
    return pin, jobs, released, categories


def live(pin, jobs, released, categories):
    verify()
    internal = {r["uid"]: r for r in read(INTERNAL / "RESULTS.json")["rows"] if r["uid"] in categories}
    if set(internal) != set(categories):
        raise ValueError("Internal comparison has not settled on the fixed roots")
    extend.RUN = RUN
    probe.OUT, probe.RUN, engine.OUT = OUT, RUN, OUT
    engine.CAP[STAGE] = 10
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["protocol_hash"]}
    with probe.runner_lock(RUN / "runner.lock"):
        ledger = []
        responses, cached = exact_stage(STAGE, jobs, identity, ledger)
        results = [{"uid": uid, "model": model, "track": categories[uid], "published_kimi": released[uid, model],
                    "common_gpt": grade(r.get("answer"), categories[uid]), "status": r["status"]}
                   for (uid, model), r in responses.items()]
        probe.freeze(OUT / "RESULTS.json", {"rows": results, "internal": internal,
                    "cached": cached, "ledger": ledger})
        print(json.dumps({"external_positions": len(results), "common_usable": sum(r["common_gpt"] is not None for r in results),
                          "requests": len(ledger), "statuses": dict(Counter(r["status"] for r in ledger))}))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "run"))
    action = cli.parse_args().action
    pin, jobs, released, categories = freeze()
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if action == "freeze":
        probe.freeze(OUT / "FROZEN.json", pin)
        print(dict(Counter(categories.values())))
    elif read(OUT / "FROZEN.json") == pin:
        live(pin, jobs, released, categories)
    else:
        raise ValueError("External scoring contract changed")
