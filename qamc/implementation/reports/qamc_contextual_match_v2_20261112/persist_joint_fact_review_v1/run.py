import itertools
import json
import sys
from pathlib import Path
from qamc.common import sha, parse_object
from inspect_answers import read_case
from trial import prepare, actor_request, judge_wire, probe, engine, persist

HERE = Path(__file__).resolve().parent
RUNS = HERE.parents[2] / "runs" / HERE.parent.name
OUT = RUNS / HERE.name / "private"
BASE = "Review the given admitted IDs against this task and the numbered original memories. Keep the initial set. Return JSON with add, an array of distinct additional integer IDs (zero based). Return an empty array if no additions help. No generated answer."
PROMPTS = {
    "ordinary": BASE + " Carefully check applicability, accuracy, useful preferences and constraints. Include missing evidence when it improves the answer; avoid irrelevant or inappropriate personalization.",
    "joint": BASE + " Consider one feasible choice the answer needs to make. Which facts together change that choice for an actual participant or object? Add the missing premises together only if their consequence applies in this setting. Check whether a personal belief would change a public factual claim or create a new objective. Shared topics alone do not establish a consequence."
}
TARGETS = ("3776469a", "7b03625e", "0029f020", "a47fceb8")

def run():
    cases, items, proto, judge, bounds = prepare()
    old = json.loads((RUNS/"persist_exposure_fr3_v1/RESULTS.json").read_text())["rows"]
    fresh = json.loads((RUNS/"persist_utility_fresh_deployment_v1/private/SETTLED.json").read_text())["rows"]
    tasks = {}
    for prefix in TARGETS:
        uid, = [u for u in cases if u.split("/")[-1].startswith(prefix)]
        task = items[uid]["public"]
        mem = task["memories"]
        archive = {}
        if prefix in TARGETS[:2]:
            x = read_case(prefix)
            seed = x["selected_sources"]
            for arm in ("FULL","SELECTED"):
                row, = [r for r in fresh if r["uid"]==uid and r["arm"]==arm]
                archive[arm] = (x["arms"][arm]["answer"], x["arms"][arm]["wire"], row)
        else:
            row, = [r for r in old if r["uid"]==uid and r["repeat"]==3]
            ex = row["exposure"]
            seed, = [list(s) for s in itertools.combinations(mem, ex["count"]) if sha(list(s))==ex["sha256"]]
            for arm in ("FULL","SELECTED"):
                cell=row["methods"][arm]
                archive[arm]=(cell["actor"]["answer"],cell["actor"]["request_sha256"],{"GPT":cell["score"]["rating"]})
        tasks[uid]=(task, [mem.index(v) for v in seed], archive)
    OUT.mkdir(parents=True,exist_ok=True)
    pin=dict(source=sha(Path(__file__).read_bytes()),protocol=sha((HERE/"PROTOCOL.md").read_bytes()),inputs=sha(tasks))
    probe.freeze(OUT/"FROZEN.json",pin)
    if sys.argv[1]=="freeze":return
    assert sys.argv[1]=="run"
    engine.OUT=probe.OUT=OUT
    probe.RUN=OUT.parent
    ident=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    ledger=[]
    def call(stage,jobs):
        if not jobs:return {}
        unique={sha(v):v for v in jobs.values()}
        engine.CAP[stage]=len(unique)
        replies=engine.stage(stage,{(k,"trial"):v for k,v in unique.items()},ident,True,ledger)
        return {k:replies[sha(v),"trial"] for k,v in jobs.items()}
    with probe.runner_lock(OUT.parent/"runner.lock"):
        jobs={}
        for uid,(task,ids,_) in tasks.items():
            data=json.dumps(dict(query=task["query"],memories=list(enumerate(task["memories"])),admitted=ids))
            for arm,prompt in PROMPTS.items():
                jobs[uid,arm]=dict(items[uid]["FULL"],messages=[dict(role="system",content=prompt),dict(role="user",content=data)])
        reviews=call("Review",jobs)
        actors={};rows={};answers={}
        for k,reply in reviews.items():
            uid,arm=k
            task,seeds,archives=tasks[uid]
            mem=task["memories"]
            r=rows[k]=dict(uid=uid,arm=arm,seeds=seeds,add=None,GPT=None,Qwen=None,origin=None)
            if reply["status"]!="OK":continue
            try:
                add=parse_object(reply["answer"])["add"]
                if not isinstance(add,list) or any(type(i)!=int or i not in range(len(mem)) or i in seeds for i in add) or len(set(add))!=len(add):continue
            except (ValueError,KeyError,TypeError):continue
            r["add"]=add
            ids=set(add+seeds)
            wire=actor_request(cases[uid],task["query"],[v for i,v in enumerate(mem) if i in ids],proto,proto["prompts"]["gepa"])
            for origin,(answer,h,ratings) in archives.items():
                if sha(wire)==h:
                    answers[k]=answer;r.update({j:ratings.get(j) for j in ("GPT","Qwen")});r["origin"]=origin;break
            else:actors[k]=wire;r["origin"]="new"
        for k,v in call("Actor",actors).items():
            if v["status"]=="OK" and v["answer"]:answers[k]=v["answer"]
        grade=judge_wire(cases,items,judge,bounds)
        for j in ("GPT","Qwen"):
            wires={k:grade(k[0],a) for k,a in answers.items() if rows[k][j] is None and (rows[k]["origin"]=="new" or k[0].split("/")[-1][:8] in TARGETS[2:])}
            if j=="Qwen":wires={k:dict(v,model="qwen3.8-flash",max_tokens=8192) for k,v in wires.items()}
            for k,v in call(j,wires).items():
                if v["status"]=="OK":
                    try:rows[k][j]=persist.author.ext.parent.persist.score(cases[k[0]]["category"],v["answer"])["rating"]
                    except (ValueError,TypeError,KeyError):pass
        probe.freeze(OUT/"SETTLED.json",dict(rows=list(rows.values()),answers={str(k):a for k,a in answers.items()},ledger=ledger))
if __name__=="__main__":run()
