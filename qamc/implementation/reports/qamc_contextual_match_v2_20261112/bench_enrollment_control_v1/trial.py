import json
from pathlib import Path
from collections import Counter, defaultdict
from baselines import archive
from run_probe import engine, probe
from qamc.common import sha

here = Path(__file__).resolve().parent
run = here.parents[2]/"runs"/here.parent.name/here.name
uid = "benchpres/contextual_dev/2d6ba4ffaa99ad881bc2"
cases, protocol, _ = archive.transfer.context("BenchPreS")
original, = [r for r in archive.transfer.archived_answers("BenchPreS",{uid}) if r["method"]==archive.engine.RP]
assert sha(original["actor_request"]) == original["actor_request_sha256"]
before = "while completing advanced education and certifications, including an MBA in Business Administration, a Project Management Professional certification, Harvard Online Leadership Essentials, and an online Small Business Management course. These completed credentials"
after = "while earning an MBA in Business Administration and a Project Management Professional certification and enrolling in Harvard Online Leadership Essentials and an online Small Business Management course. The degree and certification"
text = original["answer"]
assert text.count(before)==1
answers = [dict(uid=uid,method=m,actor_status="OK",answer=a) for m,a in (("original",text),("corrected",text.replace(before,after)))]
wires,refs=archive.transfer.grading_jobs("BenchPreS",answers,cases,protocol)
assert len(wires)==12
jobs={(u,m+"/"+field):w for (u,m,field),w in wires.items()}
stage="EnrollmentGrade"
out=run/"private"
out.mkdir(parents=True,exist_ok=True)
probe.RUN,probe.OUT,engine.OUT=run,out,out
def summary(s):
    return {k:s[k] for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness")}
with probe.runner_lock(run/"runner.lock"):
    pin=dict(answers=[sha(r["answer"]) for r in answers],wires=sorted(map(sha,wires.values())),protocol=sha((here/"PROTOCOL.md").read_bytes()),code=sha(Path(__file__).read_bytes()))
    probe.freeze(out/"FROZEN.json",pin)
    ledger=[]
    engine.CAP[stage]=len(jobs)
    replies=engine.stage(stage,dict(sorted(jobs.items(),key=lambda kv:sha(kv[0]))),dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1]),True,ledger)
    raws=defaultdict(dict)
    for (_,key),r in replies.items():
        m,field=key.split("/")
        if r["status"]=="OK":
            raws[m][field]=r["answer"]
    results={"archived":summary(original["score"])}
    for row in answers:
        m=row["method"]
        try:
            results[m]=summary(archive.transfer.bench.score.grade(archive.transfer.bench.ROOT,"benchpres",refs[uid],raws[m])) if len(raws[m])==6 else None
        except (KeyError,ValueError,TypeError):
            results[m]=None
    probe.freeze(out/"SETTLED.json",dict(results=results,ledger=ledger))
    print(json.dumps(dict(scores=results,requests=len(ledger),status=Counter(r["status"] for r in ledger),reported_tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),unknown_usage=sum(not r.get("usage") for r in ledger),retries=sum(r["automatic_retries"] for r in ledger)),indent=2))
