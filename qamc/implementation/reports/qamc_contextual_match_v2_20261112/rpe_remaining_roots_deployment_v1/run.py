import json
import sys
from pathlib import Path
from collections import Counter

import cross_backbone as cb
from qamc.common import sha

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name
read = cb.read
engine, probe = cb.engine, cb.probe


def main():
    action = sys.argv[1]
    assert action in ("freeze", "run")
    parent = read(cb.v41.formal.OUT / "PLAN.json")
    cases = cb.v41.author_cases(parent)
    assert len(cases) == 300
    roots = {r["uid"]: r for r in read(cb.v41.OUT / "FROZEN.json")["roots"]}
    inventory = read(cb.archive.BASE / "selective_path_frontier_v1/RESULTS.json")["rows"]
    labels = {r["uid"]: r["labels"] for r in read(cb.archive.ZERO_OUT / "RESULTS.json")["roots"]}
    old = read(OUT.parent/"rpe_ipe_fresh_repeat_v1/PANEL_V2.json")
    banned = {g for _,g,_ in old["cards"]}
    assert len(banned) == 18 and len(inventory) == 216
    available = {r["source_group"] for r in inventory} - banned
    cards = []
    for group in sorted(available):
        options = [r for r in inventory if r["source_group"] == group]
        chosen = min(options, key=lambda r: sha(["remaining-ipe-v1",group,r["uid"]]))
        uid = chosen["uid"]
        assert cases[uid]["analysis_group_id"] == group
        cards.append([uid,group,chosen["stratum"]])
    assert len(cards) == 24
    paper = cb.assets()[3]
    est = {(u,k):w for u,_,_ in cards for k,w in cb.initial_bodies(cb.task_for(cases[u]),cb.v41.RP)
           if k in ("RPR_MLE","RPR_IPE")}
    assert len(est) == 2 * len(cards)
    model, = {w["model"] for w in est.values()}
    cb.MODEL = model
    pin = dict(cards=cards, excluded_groups=sorted(banned), estimator_hashes=[sha(w) for w in est.values()],
               model=model, code=sha(Path(__file__).read_bytes()), protocol=sha((HERE/"PROTOCOL.md").read_bytes()))
    OUT.mkdir(parents=True,exist_ok=True)
    previous = read(OUT/"PANEL.json") if (OUT/"PANEL.json").exists() else None
    if previous:
        assert {k:v for k,v in previous.items() if k!="code"} == {k:v for k,v in pin.items() if k!="code"}
    probe.freeze(OUT/"PANEL_V2.json",pin)
    if action == "freeze":
        print(len(cards),model,Counter(c[2] for c in cards))
        return
    for rep in (1,2):
        folder=OUT/f"deployment{rep}"
        folder.mkdir(exist_ok=True)
        engine.OUT=probe.OUT=folder/"private"
        probe.OUT.mkdir(exist_ok=True)
        probe.RUN=folder
        ident=dict(experiment_sha256=sha([pin,rep]),service_reference_sha256=probe.read_reference()[1])
        ledger=[]
        def stage(name,jobs):
            engine.CAP[name]=len(jobs)
            return engine.stage(name,jobs,ident,True,ledger)
        with probe.runner_lock(folder/"runner.lock"):
            e=stage("Estimate",est)
            actors, routes = {}, {}
            for u,_,_ in cards:
                w,route,err=cb.compile_full(cases[u],{k:e[u,k] for k in ("RPR_MLE","RPR_IPE")},paper,roots[u])
                actors[u,cb.ZERO]=cb.v41.task_only_request(roots[u])
                assert actors[u,cb.ZERO]["model"]==model
                if w:
                    actors[u,cb.FULL]=w
                routes[u]=dict(branch=route,error=err)
            probe.freeze(folder/"ROUTES.json",routes)
            a=stage("Actor",actors)
            grades=stage("Judge",{k:engine.rpe_wire(parent,cases[k[0]],dict(uid=k[0],actor_status="OK",answer=v["answer"]))
                                  for k,v in a.items() if v["status"]=="OK"})
            rows=[]
            for u,g,s in cards:
                scores={k:cb.score_of(u,k,grades.get((u,k)),a.get((u,k)),labels[u]) for k in (cb.ZERO,cb.FULL)}
                rows.append(dict(uid=u,group=g,stratum=s,branch=routes[u]["branch"],scores=scores))
            probe.freeze(folder/"RESULTS.json",dict(rows=rows,ledger=ledger))
        print(rep,Counter(v["branch"] for v in routes.values()),flush=True)


if __name__ == "__main__":
    main()
