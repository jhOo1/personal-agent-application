"""Six exposed cases; exact draft reuse and two matched single-call revisions."""
import json
import sys
from pathlib import Path
from inspect_answers import read_case
from trial import prepare, judge_wire, engine, probe, persist, sha

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parents[2] / "runs" / HERE.parent.name
OUT = ARCHIVE / HERE.name / "private"
PROMPTS = {
    "general": "Review the draft for accuracy, appropriate personalization, completeness, and fidelity to the user's request. Improve any problems you find, preserving correct and useful content.",
    "action": "Check each concrete recommendation or proposed action in the draft against the supplied history. Does implementing that action activate a relevant condition for an actual participant? If so, change the affected recommendation and any directly dependent instructions. Preserve the requested deliverable and unaffected content. Treat a preference as a preference; do not impose it on others."
}
COMMON = " Return exactly KEEP if no revision is warranted, otherwise only the complete user-facing answer in its original language."

def main():
    cases, items, _, judge, bounds = prepare()
    grade = judge_wire(cases, items, judge, bounds)
    previous = probe.read(ARCHIVE/"persist_utility_fresh_deployment_v1/private/SETTLED.json")["rows"]
    drafts, old = {}, {}
    for prefix in ("3776469a", "7b03625e", "ef273934", "eccea61e"):
        case = read_case(prefix)
        u = case["uid"]
        drafts[u] = case["arms"]["SELECTED"]["answer"]
        row = next(r for r in previous if r["uid"] == u and r["arm"] == "SELECTED")
        old[u] = {j:row[j] for j in ("GPT","Qwen")}
    risk = probe.read(ARCHIVE/"persist_exposure_fr3_v1/RESULTS.json")["rows"]
    scores = probe.read(ARCHIVE/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"]
    for prefix in ("0029f020","a47fceb8"):
        row = next(r for r in risk if r["uid"].split("/")[-1].startswith(prefix) and r["repeat"] == 1)
        u = row["uid"]
        drafts[u] = row["methods"]["SELECTED"]["actor"]["answer"]
        cross = next(r for r in scores if r["uid"] == u and r["arm"] == "SELECTED" and r["repeat"] == 1)
        old[u] = {"GPT":cross["old"],"Qwen":cross["qwen"]}
    jobs = {}
    for u, draft in drafts.items():
        assert draft
        task = items[u]["public"]
        data = json.dumps(dict(query=task["query"], history=task["memories"], draft=draft), ensure_ascii=False)
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
        raw=call("Actor",jobs)
        answers={}
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
                results.append(dict(uid=u,arm=arm,judge=j,old=old[u][j],rating=value,changed=k in changed,delivered=k in answers))
        probe.freeze(OUT/"RESULTS.json",dict(rows=results,ledger=ledger))
if __name__=="__main__": main()
