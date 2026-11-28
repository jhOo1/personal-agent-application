import json
import re
import sys
from pathlib import Path
import cross_backbone as cb
from qamc.common import parse_object, sha

here = Path(__file__).resolve().parent
out = here.parents[2] / "runs" / here.parent.name / here.name
previous = out.parent / "rpe_remaining_roots_deployment_v1" / "deployment1"
read = cb.read
common = """Improve this existing answer only if a concrete local change is justified for this task by the visible history. Preserve task facts, hard constraints, other people’s decisions and the requested deliverable. If already satisfied, return {"action":"KEEP"}. Otherwise return JSON {"action":"REPLACE","old":"exact unique draft substring","new":"replacement in answer language","source":"memory ID","quote":"exact source substring","object":"exact name of existing object or action in draft"}. One replacement only. No new line or paragraph. Do not explain your answer."""
prompts = {"GENERIC": "Use strong local editorial judgment on the most useful change. "+common,
           "VALUE": "Change only an adjustable attribute value of an already chosen object or action. The object must be separately named in the same sentence as the old value. Keep the object, decision maker, goal and surrounding plan. Personal history must actually apply to the person deciding that value. Do not promote an individual preference into a group requirement. "+common}

def render(draft, sources, arm, reply):
    try:
        obj = parse_object(reply)
        if obj == {"action":"KEEP"}:
            return draft, "KEEP"
        old, new, name, source, quote = (obj[k] for k in ("old","new","object","source","quote"))
        if not (obj["action"] == "REPLACE" and all(isinstance(v,str) and v.strip() for v in (old,new,name,source,quote))
                and source in sources and quote in sources[source] and name in draft and draft.count(old)==1
                and old != new and not any(c in old+new for c in "\n\r")):
            return draft, "INVALID"
        if arm == "VALUE":
            pos = draft.index(old)
            left = re.split(r"[。！？!?；;\n]",draft[:pos])[-1]
            right = re.split(r"[。！？!?；;\n]",draft[pos+len(old):])[0]
            if name not in left and name not in right:
                return draft, "INVALID"
            if re.search(r"[。！？!?；;]",old+new):
                return draft, "INVALID"
        return draft.replace(old,new,1), "REPLACED"
    except (TypeError, ValueError, KeyError, AttributeError):
        return draft, "INVALID"

def main():
    cards = read(previous.parent/"PANEL_V2.json")["cards"]
    routes = read(previous/"ROUTES.json")
    drafts, inputs, models, cached = {}, {}, {}, {}
    for p in (previous/"Actor/visible").glob("*/record.json"):
        u = read(p)["unit"]
        uid, arm = u["root_id"], u["method"]
        w = read(p.with_name("request.json"))
        if arm == routes[uid]["branch"]:
            drafts[uid] = read(p.with_name("response.json"))["answer"]
        if arm == cb.FULL:
            task = json.loads(w["messages"][1]["content"])
            inputs[uid] = {k:task[k] for k in ("query","current_context","facts","source_evidence")}
            models[uid] = {k:v for k,v in w.items() if k!="messages"}
    jobs = {(u,arm):{**models[u],"messages":[{"role":"system","content":prompt},
            {"role":"user","content":json.dumps({**inputs[u],"draft":drafts[u]},ensure_ascii=False)}]}
            for u,_,_ in cards for arm,prompt in prompts.items()}
    assert len(jobs)==48 and len(drafts)==24
    probe, engine = cb.probe, cb.engine
    probe.RUN = out
    probe.OUT = engine.OUT = out/"private"
    probe.OUT.mkdir(exist_ok=True,parents=True)
    pin = dict(jobs=[sha(w) for w in jobs.values()],code=sha(Path(__file__).read_bytes()),
               protocol=sha((here/"PROTOCOL.md").read_bytes()), roster=cards)
    probe.freeze(out/"FREEZE.json",pin)
    if sys.argv[1]=="freeze": return
    assert sys.argv[1]=="run"
    plan=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    parent=read(cb.v41.formal.OUT/"PLAN.json")
    cases=cb.v41.author_cases(parent)
    labels={r["uid"]:r["labels"] for r in read(cb.archive.ZERO_OUT/"RESULTS.json")["roots"]}
    for p in (previous/"Judge/visible").glob("*/record.json"):
        cached[read(p)["request_sha256"]]=read(p.with_name("response.json"))["answer"]
    ledger=[]
    with probe.runner_lock(out/"runner.lock"):
        engine.CAP["Edit"]=engine.CAP["Judge"]=48
        edits=engine.stage("Edit",jobs,plan,True,ledger)
        grades, rendered={},{}
        for (uid,arm),reply in edits.items():
            if reply["status"]!="OK": continue
            sources={s["memory_id"]:s["text"] for s in inputs[uid]["source_evidence"]}
            answer,action=render(drafts[uid],sources,arm,reply["answer"])
            rendered[uid,arm]=dict(answer=answer,action=action)
            grades[uid,arm]=engine.rpe_wire(parent,cases[uid],dict(uid=uid,answer=answer,actor_status="OK"))
        scores=engine.stage("Judge",grades,plan,True,ledger,cache=cached)
        rows=[]
        for (uid,arm),reply in edits.items():
            a=rendered.get((uid,arm),{})
            rows.append(dict(uid=uid,arm=arm,action=a.get("action",reply["status"]),
                             score=cb.score_of(uid,arm,scores.get((uid,arm)),a,labels[uid])))
        probe.freeze(out/"RESULTS.json",dict(rows=rows,ledger=ledger))
if __name__=="__main__": main()
