"""Materialize native scorer inputs privately; print aggregate counts and digests only."""
import ast
from collections import Counter
from pathlib import Path
import json
import subprocess
from check_exposure_fr3 import prepare
from complete import probe
from qamc.common import sha
from qamc.contextual_match.inspect_judge import KINDS

here=Path(__file__).resolve().parent
root=here.parents[2]
archive=root/"runs"/here.parent.name
author=root/"literature/qamc_pa_v1/PersistBench"
rev="d2ded18be6d15ebb14008d081a44bd03c20670e4"
source=subprocess.check_output(["git","-C",str(author),"show",rev+":src/benchmark/prompts.py"])
tree=ast.parse(source)
imports=[n for n in tree.body if isinstance(n,(ast.ImportFrom,ast.Import))]
assert len(imports)==1 and imports[0].module=="benchmark.config" and {v.name for v in imports[0].names}==set(KINDS)
tree.body.remove(imports[0])
prompts=dict(KINDS)
exec(compile(tree,"pinned_prompts","exec"),prompts)
cases,items,_,_,_=prepare()
wires={}
assignments=[]
def add(uid,draw,method,answer):
    task=items[uid]["public"]
    assert sha(task)==cases[uid]["public_sha256"]
    key=None
    if answer:
        track=cases[uid]["category"]
        messages=[dict(role="system",content=prompts["get_judge_system_prompt"](track)),
                  dict(role="user",content=prompts["build_judge_prompt"](**task,memory_response=answer))]
        wire=dict(model="moonshotai/kimi-k2-thinking",messages=messages,temperature=0,
                  provider=dict(order=["google-vertex"],allow_fallbacks=False),reasoning=dict(enabled=True,effort="high"))
        key=sha([uid,draw,wire])
        assert wires.setdefault(key,wire)==wire
    assignments.append([uid,draw,method,key])
for row in probe.read(archive/"persist_exposure_fr3_v1/RESULTS.json")["rows"]:
    for arm in ("SELECTED","RUBRIC"):
        actor=row["methods"][arm]["actor"]
        add(row["uid"],row["repeat"],arm,actor["answer"] if actor and actor["status"]=="OK" else None)
release_file=author/"experiments/multi_turn/paper_traces/baseline_all_models.json"
raw=release_file.read_bytes()
assert sha(raw)==probe.read(archive/"persist_released_grade_agreement_v1/private/FROZEN.json")["release"]
for e in json.loads(raw)["entries"].values():
    task={k:e[k] for k in ("query","memories")}
    uid="persistbench/"+sha(task)[:20]
    if uid not in cases: continue
    assert task==items[uid]["public"] and e["failure_type"]==cases[uid]["category"]
    history=next(v for k,v in e["results"].items() if k.split("/")[-1]=="gpt-5.2")
    n=1 if e["failure_type"]=="beneficial_memory_usage" else 3
    for i,gen in enumerate(history["generations"][:n],1):
        assert gen["generation_index"]==i-1 and not gen["error"]
        add(uid,i,"Released GPT-5.2",gen["memory_response"])
counts=Counter(a[2] for a in assignments)
assert sorted(counts.values())==[25,111,111] and len({tuple(a[:3]) for a in assignments})==247
assert len({a[0] for a in assignments})==49
packet=dict(author=rev,wires=wires,assignments=assignments)
out=archive/here.name/"private/FROZEN.json"
out.parent.mkdir(parents=True,exist_ok=True)
probe.freeze(out,packet)
print(json.dumps(dict(assigned=dict(counts),missing=dict(Counter(a[2] for a in assignments if a[-1] is None)),
                      unique=len(wires),packet_sha=sha(packet),author=rev),indent=2))
