import json
import sys
import sqlite3
from pathlib import Path
from collections import Counter
from check_exposure_fr3 import prepare, judge_wire
from complete import engine, probe
from transfer_replay import persist
from qamc.common import sha

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ARCH=BASE.parents[1]/"runs"/BASE.name
RUN=ARCH/HERE.name
OUT=RUN/"private"
def read(p):return json.loads(p.read_text())

def build():
    cases,inputs,_,judge,bounds=prepare()
    make=judge_wire(cases,inputs,judge,bounds)
    rows=[];wires={}
    for f in sorted((ARCH/"persist_exposure_fr3_v1").glob("*_SETTLED.json")):
        for row in read(f)["rows"]:
            uid=row["uid"]
            for method in ("SELECTED","RUBRIC"):
                cell=row["methods"][method]
                actor=cell.get("actor") or {}
                digest=None
                if actor.get("status")=="OK":
                    original=make(uid,actor["answer"])
                    old=cell.get("judge") or {}
                    if old.get("request_sha256"):assert sha(original)==old["request_sha256"]
                    wire=dict(original,model="qwen3.8-flash",max_tokens=8192)
                    digest=sha(wire)
                    wires[digest]=wire
                rows.append(dict(uid=uid,arm=method,repeat=row["repeat"],track=row["track"],wire=digest,
                                 old=cell["score"]["rating"] if cell["score"] else None))
    assert len(rows)==222 and len({(r["uid"],r["arm"],r["repeat"]) for r in rows})==222
    # Exact immutable Qwen grading archives; distinct historical grades remain in place.
    cached={}
    for folder in ("persist_repeated_judge_sensitivity_v1","persist_fixed_answer_judge_v1"):
        for path in sorted((ARCH/folder).glob("*/samples.sqlite")):
            with sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True) as conn:
                for digest,body,status,resp in conn.execute("select request_sha,request_json,status,response_json from samples order by rowid"):
                    if digest not in wires or digest in cached:continue
                    assert json.loads(body)==wires[digest]
                    reply=json.loads(resp) if resp else {}
                    cached[digest]=dict(status=status,answer=reply.get("answer"))
                    if status=="OK":assert cached[digest]["answer"]
    return rows,wires,cached

def main():
    rows,wires,cached=build()
    pin=dict(rows=sha(rows),unique=len(wires),cached=len(cached),cached_sha=sha(cached),
             pending=sorted(wires.keys()-cached.keys()),protocol=sha((HERE/"PROTOCOL.md").read_bytes()),code=sha((HERE/"trial.py").read_bytes()))
    OUT.mkdir(parents=True,exist_ok=True)
    probe.freeze(OUT/"FROZEN.json",pin)
    print("Frozen logical, unique, cached, to dispatch:",len(rows),len(wires),len(cached),len(pin["pending"]),flush=True)
    if sys.argv[1]=="freeze":return
    assert sys.argv[1]=="run"
    engine.OUT=probe.OUT=OUT;probe.RUN=RUN
    ident=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    ledger=[]
    jobs={(d,"qwen"):wires[d] for d in pin["pending"]}
    engine.CAP["Judge"]=len(jobs)
    with probe.runner_lock(RUN/"runner.lock"):
        fresh=engine.stage("Judge",jobs,ident,True,ledger) if jobs else {}
        replies={**cached,**{d:v for (d,_),v in fresh.items()}}
        for r in rows:
            v=replies.get(r["wire"],{})
            r["qwen"]=None
            if v.get("status")=="OK":
                try:r["qwen"]=persist.author.ext.parent.persist.score(r["track"],v["answer"])["rating"]
                except (TypeError,ValueError,KeyError):pass
        probe.freeze(OUT/"RESULTS.json",dict(rows=rows,ledger=ledger))
if __name__=="__main__":main()
