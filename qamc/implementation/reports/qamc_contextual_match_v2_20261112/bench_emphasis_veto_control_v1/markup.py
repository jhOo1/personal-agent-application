"""Score a markup-only change on every available exact veto answer with emphasis restored."""
import contextlib
import io
import re
from collections import Counter, defaultdict
from pathlib import Path
import json
with contextlib.redirect_stdout(io.StringIO()):
    import replay as archive
from run_probe import engine,probe
from qamc.common import sha

here=Path(__file__).resolve().parent
run=here.parents[2]/"runs"/here.parent.name/here.name
out=run/"private";out.mkdir(parents=True,exist_ok=True)
probe.RUN,probe.OUT,engine.OUT=run,out,out
answers=[]; originals={}
for row in archive.rows:
    u=row["uid"]
    if not row["difference"]:continue
    raw=archive.record.get((u,"CONTEXT_FIRST_FUSION"))
    if not raw or raw["actor_request_hash"]!=archive.policy_wire(archive.rp[u],False)[0] or not raw.get("answer"):continue
    text=raw["answer"]
    # First full sentence of first substantive body paragraph, skipping header and salutation.
    paragraphs=list(re.finditer(r"(?:\A|(?<=\n\n))[^\n]+",text))
    span=next((m for m in paragraphs if len(m.group())>=45 and not m.group().startswith(("Subject:","Dear "))),None)
    if not span or "**" in text:continue
    sentence=re.match(r"[^.!?]+[.!?](?=\s|$)",span.group())
    if not sentence:continue
    a=span.start();b=a+sentence.end()
    new=text[:a]+"**"+text[a:b]+"**"+text[b:]
    assert new.replace("**","")==text
    answers.append(dict(uid=u,method="markup",actor_status="OK",answer=new))
    originals[u]=raw["score"]
jobs,refs=archive.t.grading_jobs("BenchPreS",answers,archive.cases,archive.protocol)
assert len(jobs)==6*len(answers) and answers
with probe.runner_lock(run/"runner.lock"):
    pin=dict(jobs=sorted(map(sha,jobs.values())),code=sha(Path(__file__).read_bytes()),selection=sha((here/"replay.py").read_bytes()))
    probe.freeze(out/"FROZEN.json",pin)
    stage="MarkupGrade";ledger=[];engine.CAP[stage]=len(jobs)
    rec=engine.stage(stage,{(u,k):w for (u,_,k),w in jobs.items()},dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1]),True,ledger)
    raws=defaultdict(dict)
    for (u,k),r in rec.items():
        if r["status"]=="OK":raws[u][k]=r["answer"]
    def compact(s):
        return {k:s[k] for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness")} if s else None
    results=[]
    for a in answers:
        u=a["uid"];grade=None
        if len(raws[u])==6:
            try:grade=archive.t.bench.score.grade(archive.t.bench.ROOT,"benchpres",refs[u],raws[u])
            except (ValueError,TypeError,KeyError):pass
        results.append(dict(base=compact(originals[u]),markup=compact(grade),gate=compact(archive.gate.get(u))))
    data=dict(rows=results,requests=len(ledger),status=dict(Counter(r["status"] for r in ledger)),tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),unknown_usage=sum(not r.get("usage") for r in ledger))
    probe.freeze(out/"RESULTS.json",data);print(json.dumps(data))
