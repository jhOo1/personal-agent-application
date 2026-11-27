"""Score missing same-Actor group controls on the fixed protection panels."""
from pathlib import Path
from collections import Counter, defaultdict
import json
import sqlite3
import sys
from check_exposure_fr3 import prepare, judge_wire
from complete import engine, probe
from transfer_replay import persist
from qamc.common import sha

here=Path(__file__).resolve().parent
archive=here.parents[2]/"runs"/here.parent.name
run=archive/here.name
out=run/"private"
read=probe.read
prior=read(archive/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"]
known={r["wire"]:r["qwen"] for r in prior if r["wire"]}
assert all(not r["wire"] or known.get(r["wire"])==r["qwen"] for r in prior)
selected={(r["uid"],r["repeat"]):r for r in prior if r["arm"]=="SELECTED"}
cases,inputs,_,judge,bounds=prepare()
make=judge_wire(cases,inputs,judge,bounds)
rows=[];wires={}
for r in read(archive/"persist_exposure_fr3_v1/RESULTS.json")["rows"]:
    if r["track"]=="sycophancy":
        continue
    cell=r["methods"]["GROUP"]
    digest=None
    if (cell.get("actor") or {}).get("status")=="OK":
        wire=make(r["uid"],cell["actor"]["answer"])
        if cell.get("judge"):
            assert sha(wire)==cell["judge"]["request_sha256"]
        qwire=dict(wire,model="qwen3.8-flash",max_tokens=8192)
        digest=sha(qwire)
        wires[digest]=qwire
    s=selected[r["uid"],r["repeat"]]
    rows.append(dict(uid=r["uid"],rep=r["repeat"],wire=digest,selected_q=s["qwen"],selected_g=s["old"],
                     track=r["track"],group_g=cell["score"]["rating"] if cell["score"] else None,same=bool(digest) and s["wire"]==digest))
assert len(rows)==75 and len({(r["uid"],r["rep"]) for r in rows})==75
tracks={r["wire"]:r["track"] for r in rows if r["wire"]}
for folder in ("persist_same_actor_syc_crossjudge_v1","persist_repeated_judge_sensitivity_v1","persist_fixed_answer_judge_v1"):
    for path in sorted((archive/folder).glob("*/samples.sqlite")):
        with sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True) as db:
            for digest,body,status,response in db.execute("select request_sha,request_json,status,response_json from samples order by rowid"):
                if digest not in wires or digest in known:
                    continue
                assert json.loads(body)==wires[digest]
                known[digest]=None
                if status=="OK":
                    try:
                        known[digest]=persist.author.ext.parent.persist.score(tracks[digest],json.loads(response)["answer"])["rating"]
                    except (TypeError,ValueError,KeyError):
                        pass
jobs={(d,"group"):w for d,w in wires.items() if d not in known}
out.mkdir(parents=True,exist_ok=True)
pin={"rows":sha(rows),"requests":sorted(d for d,_ in jobs),"known":sha({d:known[d] for d in wires if d in known}),"code":sha(Path(__file__).read_bytes()),"protocol":sha((here/"PROTOCOL.md").read_bytes())}
probe.freeze(out/"FROZEN.json",pin)
engine.OUT=probe.OUT=out
probe.RUN=run
engine.CAP["Judge"]=len(jobs)
live=sys.argv[1]=="run"
print(f"{len(rows)} deployments, {len(jobs)} additional Judge requests",flush=True)
ledger=[]
with probe.runner_lock(run/"runner.lock"):
    answers=engine.stage("Judge",jobs,{"service_reference_sha256":probe.read_reference()[1],"experiment_sha256":sha(pin)},live,ledger) if jobs else {}
    for (d,_),resp in answers.items():
        known[d]=None
        if resp["status"]=="OK":
            try:
                known[d]=persist.author.ext.parent.persist.score(tracks[d],resp["answer"])["rating"]
            except (ValueError,KeyError,TypeError):
                pass
    for r in rows:r["group_q"]=known.get(r["wire"])
    doc={"rows":rows,"ledger":ledger}
    if live:probe.freeze(out/"RESULTS.json",doc)
    assert read(out/"RESULTS.json")==doc
