"""Fixed-memory three-method deployment on exposed PersistBench source groups."""
import argparse
import importlib.util
import json
import subprocess
from collections import Counter
from pathlib import Path

from complete import engine, probe, select, actor_request, input_requests, transfer, read
from qamc.common import sha
from repeat_receipts import branch
from transfer_replay import persist

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name
OUT = RUN / "private"
UP = RUN / "upstream"
REV = "6b517dc90d4c7e0ebc4d2305684d45051f792cc9"
FILES = ["01_counterfactual_induction_method_aligned.txt",
         "02_context_aware_reflection_method_aligned.txt", "03_memory_use_guided_generation.txt"]
BU = "beneficial_memory_usage"


def author_module():
    path = UP / "methods/memadapter/memadapter.py"
    assert subprocess.check_output(["git", "-C", UP, "rev-parse", "HEAD"], text=True).strip() == REV
    subprocess.run(["git", "-C", UP, "diff", "--exit-code", "HEAD", "--", "methods/memadapter"], check=True)
    spec = importlib.util.spec_from_file_location("released_memadapter", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def inputs():
    roster = read(HERE.parent / "persist_author_controls_v2/PLAN.json")
    previous = read(RUN.parent / "persist_exposure_fr3_v1/RESULTS.json")
    old = {r["uid"] for r in previous["rows"]}
    assert roster["not_confirmation"] and len(old) == 49 and len(roster["cases"]) == 60
    cases, tasks = {}, {}
    for c in roster["cases"]:
        assert c["role"] == "DEV"
        u = c["uid"]
        if c["category"] != BU and u in old:
            continue
        t = persist.author.parent.smoke.task_for(c)
        task = dict(query=t.query, memories=[m.text for m in t.memories])
        assert sha(task) == c["public_sha256"]
        cases[u], tasks[u] = c, task
    assert len({c["group_id"] for c in cases.values()}) == 29
    assert Counter(c["category"] for c in cases.values()) == {BU:20,"sycophancy":8,"cross_domain":1}
    return roster, cases, tasks


def author_wire(mod, task, number, prior=None):
    memories = [dict(memory_id=f"memory_{i:02d}", memory_text=m) for i,m in enumerate(task["memories"], 1)]
    if number == 1:
        values = {"RETRIEVED_MEMORIES":mod.build_stage1_input(memories)}
    else:
        parsed = mod.parse_json_response(prior, stage=f"Stage {number-1}")
        if number == 2:
            mod.validate_stage1(parsed, memories)
            values = mod.build_stage2_input(current_query=task["query"], memories=memories, boundary_cards=parsed)
        else:
            mod.validate_stage2(parsed, memories)
            values = mod.build_stage3_input(current_query=task["query"], memories=memories, use_instructions=parsed)
    system, template = mod.load_prompt_parts(FILES[number-1])
    wire = persist.author.ext.text_request(system, mod.render_prompt(template,values), "qwen3.8-flash", 8192)
    return wire


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze","run"))
    args = parser.parse_args()
    mod = author_module()
    roster,cases,tasks = inputs()
    protocol = read(HERE.parents[2] / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    route_plan = read(transfer.OUT / "PLAN.json")
    routes = {u:input_requests(cases[u], task, route_plan) for u,task in tasks.items()}
    scorer = persist.author.ext.parent.persist
    _, rubrics, formatter = scorer.upstream()
    judge = roster["protocols"]["gpt41"]
    first = {u:author_wire(mod,t,1) for u,t in tasks.items()}
    pin = dict(code=sha(Path(__file__).read_bytes()), protocol=sha((HERE/"PROTOCOL.md").read_bytes()),
               author=REV, roots={u:c["public_sha256"] for u,c in cases.items()},
               first={u:sha(w) for u,w in first.items()}, routes=sha(routes), actor=sha(protocol["prompts"]),
               judge=sha(judge), rubrics=sha({c:rubrics[c] for c in {r["category"] for r in cases.values()}}))
    OUT.mkdir(parents=True,exist_ok=True)
    probe.freeze(OUT/"FROZEN_DEPLOY.json",pin)
    print("Frozen:",len(tasks),"roots, 47 deployments per method",flush=True)
    if args.action == "freeze":
        return
    engine.OUT=probe.OUT=OUT
    probe.RUN=RUN
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    ledger=[]
    def call(stage,jobs):
        if not jobs:
            return {}
        unique={sha(w):w for w in jobs.values()}
        engine.CAP[stage]=len(unique)
        replies=engine.stage(stage,{(h,"deploy"):w for h,w in unique.items()},identity,True,ledger)
        return {k:replies[sha(w),"deploy"] for k,w in jobs.items()}
    with probe.runner_lock(RUN/"runner.lock"):
        for draw in range(1,4):
            ids=sorted(u for u,c in cases.items() if draw==1 or c["category"]!=BU)
            def dispatch(stage,jobs):
                return call(f"D{draw}{stage}",jobs)
            errors={}
            jobs={u:first[u] for u in ids}
            for n in (1,2):
                replies=dispatch(f"MA{n}",jobs)
                jobs={}
                for u,r in replies.items():
                    if r["status"]=="OK":
                        try:
                            jobs[u]=author_wire(mod,tasks[u],n+1,r["answer"])
                        except (ValueError,KeyError,TypeError) as exc:
                            errors[u]=f"stage{n} {type(exc).__name__}"
            actors={(u,"MEMADAPTER"):w for u,w in jobs.items()}
            q=dispatch("Route",{u:routes[u]["query"] for u in ids})
            modes={}
            for u,r in q.items():
                if r["status"]=="OK":
                    try:
                        modes[u]=branch(tasks[u],r["answer"])
                    except (ValueError,KeyError,TypeError):
                        continue
            selected=dispatch("Select",{u:routes[u][mode] for u,mode in modes.items()})
            for u,r in selected.items():
                if r["status"]!="OK":
                    continue
                try:
                    e=select(cases[u],tasks[u],q[u]["answer"],r["answer"])
                except (ValueError,KeyError,TypeError):
                    continue
                wide=tasks[u]["memories"] if modes[u]=="style" and e else e
                for arm,ev in (("SELECTED",e),("BREADTH",wide)):
                    actors[u,arm]=actor_request(cases[u],tasks[u]["query"],ev,protocol,protocol["prompts"]["gepa"])
            answers=dispatch("Actor",actors)
            grades={}
            for model,stage,cap in ((judge["model"],"GPT",judge["stages"][persist.STAGE]["max_tokens"]),("qwen3.8-flash","Qwen",8192)):
                jobs={}
                for (u,a),r in answers.items():
                    if r["status"]=="OK" and r.get("answer"):
                        prompt=formatter["build_judge_prompt"](tasks[u]["memories"],tasks[u]["query"],r["answer"])
                        jobs[u,a]=persist.author.ext.text_request(rubrics[cases[u]["category"]],prompt,model,cap)
                grades[stage]=dispatch(stage,jobs)
            rows=[]
            for u in ids:
                for arm in ("MEMADAPTER","SELECTED","BREADTH"):
                    k=u,arm
                    row=dict(uid=u,arm=arm,draw=draw,track=cases[u]["category"],actor=answers.get(k,{}).get("status","NO_UPSTREAM"))
                    for stage,rs in grades.items():
                        g=rs.get(k,{})
                        row[stage]=None
                        if g.get("status")=="OK":
                            try:
                                row[stage]=scorer.score(row["track"],g["answer"])["rating"]
                            except (ValueError,KeyError,TypeError):
                                pass
                    rows.append(row)
            probe.freeze(OUT/f"DRAW_{draw}.json",dict(rows=rows,errors=errors))
        probe.freeze(OUT/"SETTLED.json",dict(ledger=ledger))

if __name__=="__main__":
    main()
