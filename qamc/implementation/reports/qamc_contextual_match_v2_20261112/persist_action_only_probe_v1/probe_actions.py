"""Two hand-specified action edits, scored with otherwise identical archived requests."""
from pathlib import Path
import json
from copy import deepcopy
from competition import RUN as archive, engine, probe, sha, persist, BU

here = Path(__file__).resolve().parent
run = archive.parent / here.name
edits = {
    "garden": [("Compact rose of Sharon or a small ornamental grass could work", "Compact rose of Sharon could work")],
    "lunch": [("3 green onions, white and green parts separated", "Green tops of 3 green onions"),
              ("the diced carrots and the white parts of the green onions", "the diced carrots"),
              ("Keep the portion of green onion white parts modest; use mostly the green tops.",
               "Use only the green tops.")],
}
def read(p):
    return json.loads(p.read_text())
def answer_files(stage):
    return (archive / stage / "visible").glob("*/response.json")

def main():
    jobs = {"GPT": {}, "Qwen": {}}
    originals = {}
    scorer = persist.author.ext.parent.persist
    for case, replacements in edits.items():
        matches = [a for p in answer_files("D1Actor") if (a := read(p)["answer"]).count(replacements[0][0]) == 1]
        assert len(matches) == 1
        original, = matches
        revised = original
        for old, new in replacements:
            assert revised.count(old) == 1
            revised = revised.replace(old, new)
        for stage in jobs:
            scored = []
            for p in answer_files("D1" + stage):
                wire = read(p.with_name("request.json"))
                if wire["messages"][-1]["content"].count(original) == 1:
                    scored.append((wire, scorer.score(BU, read(p)["answer"])["rating"]))
            assert len(scored) == 1
            wire, score = scored[0]
            changed = deepcopy(wire)
            changed["messages"][-1]["content"] = wire["messages"][-1]["content"].replace(original, revised)
            jobs[stage][case, "edited"] = changed
            originals[stage, case] = score
    run.mkdir(parents=True, exist_ok=True)
    engine.OUT = probe.OUT = run / "private"
    probe.OUT.mkdir(exist_ok=True)
    probe.RUN = run
    pin = {"edits":sha(edits), "wires":{s:{u:sha(w) for (u,_),w in v.items()} for s,v in jobs.items()},
           "protocol":sha((here/"PROTOCOL.md").read_bytes())}
    ledger = []
    with probe.runner_lock(run/"runner.lock"):
        probe.freeze(probe.OUT/"FROZEN.json", pin)
        identity = dict(experiment_sha256=sha(pin), service_reference_sha256=probe.read_reference()[1])
        rows = []
        for stage, wires in jobs.items():
            engine.CAP[stage] = len(wires)
            receipts = engine.stage(stage, wires, identity, True, ledger)
            for (case,_), r in receipts.items():
                rating = None
                if r["status"] == "OK":
                    try:
                        rating = scorer.score(BU,r["answer"])["rating"]
                    except (ValueError, KeyError, TypeError):
                        pass
                rows.append(dict(case=case, judge=stage, original=originals[stage,case], revised=rating, status=r["status"]))
        probe.freeze(probe.OUT/"SETTLED.json",dict(rows=rows,ledger=ledger))
        print(json.dumps(rows))
if __name__ == "__main__":
    main()
