"""Re-evaluate two exact archived completeness wires three times each."""
from collections import defaultdict, Counter
from pathlib import Path
import json
from baselines import archive
from run_probe import engine, probe
from qamc.common import sha

here = Path(__file__).resolve().parent
root = here.parents[2]/"runs"/here.parent.name
previous = root/"bench_enrollment_control_v1"
run = root/here.name
out = run/"private"
out.mkdir(parents=True,exist_ok=True)
def read(path):
    return json.loads(path.read_bytes())
wires = {}
raw = defaultdict(dict)
for path in (previous/"EnrollmentGrade/visible").glob("*/record.json"):
    record = read(path)
    arm, field = record["unit"]["method"].split("/")
    assert record["status"]=="OK" and field not in raw[arm]
    raw[arm][field] = read(path.with_name("response.json"))["answer"]
    if field=="BenchComplete":
        wires[arm]=read(path.with_name("request.json"))
        assert sha(wires[arm])==record["request_sha256"]
uid = "benchpres/contextual_dev/2d6ba4ffaa99ad881bc2"
cases,protocol,_ = archive.transfer.context("BenchPreS")
original, = [r for r in archive.transfer.archived_answers("BenchPreS",{uid}) if r["method"]==archive.engine.RP]
_,refs = archive.transfer.grading_jobs("BenchPreS",[original],cases,protocol)
def rating(arm,answer):
    return archive.transfer.bench.score.grade(archive.transfer.bench.ROOT,"benchpres",refs[uid],
            dict(raw[arm],BenchComplete=answer))["task_completeness"]
old={arm:rating(arm,raw[arm]["BenchComplete"]) for arm in wires}
assert old==dict(original=5,corrected=3)
probe.RUN,probe.OUT,engine.OUT=run,out,out
with probe.runner_lock(run/"runner.lock"):
    pin=dict(wires={k:sha(v) for k,v in wires.items()},protocol=sha((here/"PROTOCOL.md").read_bytes()),code=sha(Path(__file__).read_bytes()))
    probe.freeze(out/"FROZEN.json",pin)
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    ledger=[]
    waves=[]
    for i in range(3):
        stage=f"Completeness{i+1}"
        engine.CAP[stage]=2
        order=("corrected","original") if i%2==0 else ("original","corrected")
        results=engine.stage(stage,{(uid,arm):wires[arm] for arm in order},identity,True,ledger)
        values={}
        for (_,arm),receipt in results.items():
            try:
                values[arm]=rating(arm,receipt["answer"]) if receipt["status"]=="OK" else None
            except (ValueError,TypeError,KeyError):
                values[arm]=None
        waves.append(values)
    probe.freeze(out/"SETTLED.json",dict(waves=waves,ledger=ledger))
    summary=dict(previous=old,fresh=waves,requests=len(ledger),statuses=Counter(r["status"] for r in ledger),
                 reported_tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),
                 missing_usage=sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger),
                 retries=sum(r["automatic_retries"] for r in ledger))
    probe.freeze(here/"RESULTS.json",summary)
