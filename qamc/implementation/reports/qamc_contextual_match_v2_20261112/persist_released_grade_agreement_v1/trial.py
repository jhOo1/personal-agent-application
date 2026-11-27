import json
import sys
from collections import Counter
from pathlib import Path

from qamc.common import sha
from check_exposure_fr3 import prepare, judge_wire
from complete import engine, probe
from transfer_replay import persist

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "runs" / HERE.parent.name / HERE.name / "private"
SOURCE = ROOT / "literature/qamc_pa_v1/PersistBench/experiments/multi_turn/paper_traces/baseline_all_models.json"


def main():
    mode = sys.argv[1]
    assert mode in {"freeze", "run"}
    cases, items, _, judge, bounds = prepare()
    build = judge_wire(cases, items, judge, bounds)
    data = SOURCE.read_bytes()
    release = json.loads(data)
    wires, ratings = {}, {}
    for entry in release["entries"].values():
        task = {k: entry[k] for k in ("query", "memories")}
        uid = "persistbench/" + sha(task)[:20]
        if uid not in cases:
            continue
        assert task == items[uid]["public"]
        for model, history in sorted(entry["results"].items()):
            draw = history["generations"][0]
            assert draw["generation_index"] == 0 and not draw["error"]
            key = uid, model.replace("/", "_")
            assert key not in wires
            wires[key] = build(uid, draw["memory_response"])
            ratings[key] = int(draw["judge"]["score"])
    assert len(wires) == 65 and len({u for u, _ in wires}) == 13
    pin = dict(release=sha(data), protocol=sha((HERE / "PROTOCOL.md").read_bytes()),
               code=sha(Path(__file__).read_bytes()), wires=[[u,m,sha(w)] for (u,m),w in wires.items()])
    OUT.mkdir(parents=True, exist_ok=True)
    probe.freeze(OUT / "FROZEN.json", pin)
    if mode == "freeze":
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN = OUT.parent
    stage = "ExternalGrade"
    engine.CAP[stage] = len(wires)
    identity = dict(experiment_sha256=sha(pin), service_reference_sha256=probe.read_reference()[1])
    ledger = []
    with probe.runner_lock(OUT.parent / "runner.lock"):
        receipts = engine.stage(stage, wires, identity, True, ledger)
        rows = []
        for (uid, model), receipt in receipts.items():
            rating = None
            if receipt["status"] == "OK":
                try:
                    rating = persist.author.ext.parent.persist.score(cases[uid]["category"], receipt["answer"])["rating"]
                except (ValueError, KeyError, TypeError):
                    pass
            rows.append(dict(root=uid, model=model, category=cases[uid]["category"], released=ratings[uid,model], project=rating))
        probe.freeze(OUT / "SETTLED.json", dict(rows=rows, ledger=ledger))


if __name__ == "__main__":
    main()
