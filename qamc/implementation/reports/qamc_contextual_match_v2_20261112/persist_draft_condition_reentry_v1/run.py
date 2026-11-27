"""Six exposed cases; exact draft reuse and two matched single-call revisions."""
import json
import sys
from pathlib import Path
from trial import select, actor_request
from inspect_answers import read_case
from trial import prepare, judge_wire, engine, probe, persist, sha

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parents[2] / "runs" / HERE.parent.name
OUT = ARCHIVE / HERE.name / "private"
PROMPTS = {
    "general": "Choose omitted sources relevant and helpful for improving this draft for the current user request. Consider appropriate personalization, factual accuracy and completeness.",
    "action": "Examine what the draft actually proposes. Select omitted sources only if a fact about an affected person, place, object or deliverable changes whether or how a concrete proposed action should be carried out. Include jointly necessary facts. Personal beliefs alone cannot settle public facts or others' needs."
}
COMMON = ' Return only a JSON array of omitted integer IDs to add, or [] to keep the draft.'
EDITOR = "Use the newly available source facts where appropriate to revise the draft. Preserve correct content and complete the original request. Return only the user-facing answer or exactly KEEP."

def main():
    cases, items, protocol, judge, bounds = prepare()
    grade = judge_wire(cases, items, judge, bounds)
    previous = probe.read(ARCHIVE/"persist_utility_fresh_deployment_v1/private/SETTLED.json")["rows"]
    drafts, old, initial = {}, {}, {}
    for prefix in ("3776469a", "7b03625e", "ef273934", "eccea61e"):
        case = read_case(prefix)
        u = case["uid"]
        initial[u] = case["selected_sources"]
        drafts[u] = case["arms"]["SELECTED"]["answer"]
        row = next(r for r in previous if r["uid"] == u and r["arm"] == "SELECTED")
        old[u] = {j:row[j] for j in ("GPT","Qwen")}
    risk = probe.read(ARCHIVE/"persist_exposure_fr3_v1/RESULTS.json")["rows"]
    scores = probe.read(ARCHIVE/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"]
    for prefix in ("0029f020","a47fceb8"):
        row = next(r for r in risk if r["uid"].split("/")[-1].startswith(prefix) and r["repeat"] == 1)
        u = row["uid"]
        drafts[u] = row["methods"]["SELECTED"]["actor"]["answer"]
        task = items[u]["public"]
        initial[u] = select(cases[u],task,row["route"]["answer"],row["selector"]["answer"])
        wire = actor_request(cases[u],task["query"],initial[u],protocol,protocol["prompts"]["gepa"])
        assert sha(wire) == row["methods"]["SELECTED"]["actor"]["request_sha256"]
        cross = next(r for r in scores if r["uid"] == u and r["arm"] == "SELECTED" and r["repeat"] == 1)
        old[u] = {"GPT":cross["old"],"Qwen":cross["qwen"]}
    jobs = {}
    for u, draft in drafts.items():
        assert draft
        task = items[u]["public"]
        assert set(initial[u]) <= set(task["memories"])
        memories=[dict(id=i,text=m,already_visible=m in initial[u]) for i,m in enumerate(task["memories"])]
        data = json.dumps(dict(query=task["query"], history=memories, draft=draft), ensure_ascii=False)
        for arm, prompt in PROMPTS.items():
            jobs[u,arm] = persist.author.ext.text_request(prompt+COMMON,data,"qwen3.8-flash",8192)
    OUT.mkdir(parents=True,exist_ok=True)
    pin = dict(wires=sorted(sha(w) for w in jobs.values()), code=sha(Path(__file__).read_bytes()), protocol=sha((HERE/"PROTOCOL.md").read_bytes()))
    probe.freeze(OUT/"FROZEN.json",pin)
    if sys.argv[1] == "freeze": return
    assert sys.argv[1] == "run"
    engine.OUT=probe.OUT=OUT
    probe.RUN=OUT.parent
    ledger=[]
    ident=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    def call(stage, wires):
        unique = {(sha(w),"panel"):w for w in wires.values()}
        if not unique: return {}
        engine.CAP[stage]=len(unique)
        replies=engine.stage(stage,unique,ident,True,ledger)
        return {k:replies[sha(w),"panel"] for k,w in wires.items()}
    with probe.runner_lock(OUT.parent/"runner.lock"):
        decisions=call("Select",jobs)
        answers, edits, additions = {}, {}, {}
        for k,r in decisions.items():
            if r["status"] != "OK": continue
            u=k[0]
            task=items[u]["public"]
            memories=task["memories"]
            try:
                ids=json.loads(r["answer"].strip())
                if not isinstance(ids,list) or not all(type(i) is int and 0<=i<len(memories) and memories[i] not in initial[u] for i in ids) or len(ids)!=len(set(ids)):
                    continue
            except (ValueError,TypeError): continue
            additions[k]=sorted(ids)
            if not ids:
                answers[k]=drafts[u]
                continue
            body=dict(query=task["query"],draft=drafts[u],additional_sources=[memories[i] for i in additions[k]])
            edits[k]=persist.author.ext.text_request(EDITOR,json.dumps(body,ensure_ascii=False),"qwen3.8-flash",8192)
        raw=call("Actor",edits)
        for k,r in raw.items():
            if r["status"]=="OK" and r.get("answer","").strip():
                answers[k]=drafts[k[0]] if r["answer"].strip()=="KEEP" else r["answer"]
        changed={k:grade(k[0],a) for k,a in answers.items() if a!=drafts[k[0]]}
        results=[]
        for j in ("GPT","Qwen"):
            wires={k:w if j=="GPT" else dict(w,model="qwen3.8-flash",max_tokens=8192) for k,w in changed.items()}
            rs=call(j,wires)
            for k in jobs:
                u,arm=k
                value=None
                if k in answers and k not in changed: value=old[u][j]
                elif rs.get(k,{}).get("status")=="OK":
                    try: value=persist.author.ext.parent.persist.score(cases[u]["category"],rs[k]["answer"])["rating"]
                    except (ValueError,KeyError,TypeError): pass
                results.append(dict(uid=u,arm=arm,judge=j,old=old[u][j],added=additions.get(k),rating=value,changed=k in changed,delivered=k in answers))
        probe.freeze(OUT/"RESULTS.json",dict(rows=results,ledger=ledger))
if __name__=="__main__": main()
