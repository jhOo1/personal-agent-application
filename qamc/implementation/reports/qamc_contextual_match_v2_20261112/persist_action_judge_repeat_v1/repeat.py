"""Measure paired fixed-answer grading stability without regenerating answers."""
from pathlib import Path
from probe_actions import archive, run as previous, read, answer_files, edits
from competition import engine, probe, sha, persist, BU

here = Path(__file__).resolve().parent
run = archive.parent / here.name

def archived_requests(stage):
    jobs = {}
    edited = read(previous/"private"/f"{stage}_MANIFEST.json")["units"]
    assert len(edited) == 2
    for unit in edited:
        case = unit["unit"]["root_id"]
        new_wire = unit["request"]
        actors = [a for p in answer_files("D1Actor") if (a := read(p)["answer"]).count(edits[case][0][0]) == 1]
        old_answer, = actors
        new_answer = old_answer
        for before, after in edits[case]:
            assert new_answer.count(before) == 1
            new_answer = new_answer.replace(before, after)
        original = [w for p in answer_files("D1"+stage)
                    if (w := read(p.with_name("request.json")))["messages"][-1]["content"].count(old_answer) == 1]
        old_wire, = original
        import copy
        test = copy.deepcopy(old_wire)
        test["messages"][-1]["content"] = test["messages"][-1]["content"].replace(old_answer,new_answer)
        assert test == new_wire
        assert new_wire in [read(p) for p in (previous/stage/"visible").glob("*/request.json")]
        jobs[case, "original"] = old_wire
        jobs[case, "edited"] = new_wire
    return jobs

def main():
    jobs = {s:archived_requests(s) for s in ("GPT","Qwen")}
    probe.RUN = run
    engine.OUT = probe.OUT = run/"private"
    probe.OUT.mkdir(parents=True, exist_ok=True)
    pin = dict(code=sha(Path(__file__).read_bytes()),protocol=sha((here/"PROTOCOL.md").read_bytes()),
               hashes={s:[sha(w) for w in v.values()] for s,v in jobs.items()})
    ledger, rows = [], []
    with probe.runner_lock(run/"runner.lock"):
        probe.freeze(probe.OUT/"PIN.json",pin)
        identity=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
        for wave in (1,2):
            for judge, wires in jobs.items():
                stage=f"D{wave}{judge}"
                scheduled=wires if wave==1 else dict(reversed(list(wires.items())))
                engine.CAP[stage]=len(wires)
                replies=engine.stage(stage,scheduled,identity,True,ledger)
                for (case,arm),receipt in replies.items():
                    grade=None
                    if receipt["status"]=="OK":
                        try:
                            grade=persist.author.ext.parent.persist.score(BU,receipt["answer"])["rating"]
                        except (KeyError, TypeError, ValueError):
                            pass
                    rows.append(dict(wave=wave,case=case,arm=arm,judge=judge,grade=grade,status=receipt["status"]))
        probe.freeze(probe.OUT/"RESULTS.json",dict(rows=rows,ledger=ledger))
if __name__=="__main__":
    main()
