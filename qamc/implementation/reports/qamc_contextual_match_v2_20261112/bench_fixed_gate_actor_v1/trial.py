"""Reuse frozen Strong Gate messages and the original repeat-study scoring pipeline."""
import sys
from panel import HERE, RUN as OLD, GATE, read, panel
from incremental_panel import sha
from run_probe import engine, probe
import run_qamc_benchpres_three_draw as repeat

MODELS = ("qwen3.8-flash","deepseek-v4.1-flash")
OUT = HERE / "private"
RUN = engine.RUN.with_name(HERE.name)

def main(live):
    roster = panel()
    if roster != read(HERE/"PANEL.json"):
        raise ValueError("Frozen panel drift")
    cards = {r["uid"]: r for group in roster.values() for r in group}
    old = read(OLD/"PLAN_PRIVATE.json")
    cases = {r["uid"]: r for r in old["cases"] if r["uid"] in cards}
    originals = {j["unit"]["root_id"]:j["request"] for j in old["generation"].values()
                 if j["unit"]["method"]==GATE and j["unit"]["replicate"]==0 and j["unit"]["root_id"] in cards}
    if set(originals)!=set(cards) or any(sha(w)!=cards[u]["request_sha256"] for u,w in originals.items()):
        raise ValueError("Actor hash drift")
    ident={"experiment_sha256":sha([roster,sha((HERE/"trial.py").read_bytes()),MODELS,old["protocols"]["grading"]]),
           "service_reference_sha256":probe.read_reference()[1]}
    if not live:
        print(len(cards),len(originals)*6,old["protocols"]["grading"]["model"])
        return
    OUT.mkdir(exist_ok=True)
    probe.RUN, probe.OUT, engine.OUT = RUN,OUT,OUT
    with probe.runner_lock(RUN/"runner.lock"):
        probe.freeze(OUT/"EXECUTION.json",ident)
        ledger=[]
        rows=[]
        for rep in range(3):
            answers={}
            for m in MODELS[::1 if rep%2==0 else -1]:
                stage=f"Actor{rep}_{m}"
                wires={(u,m):{**w,"model":m} for u,w in originals.items()}
                engine.CAP[stage]=len(wires)
                answers.update(engine.stage(stage,wires,ident,True,ledger))
            jobs={}
            refs={}
            prot=old["protocols"]["grading"]
            for (uid,m),reply in answers.items():
                if reply["status"]!="OK":continue
                c=cases[uid]
                ref=read(repeat.ROOT/c["evaluation_path"])
                if repeat.digest(ref)!=c["evaluation_hash"]:raise ValueError("Eval reference drift")
                refs[uid]=ref
                query=repeat.prior.base.task_for(c).query
                for field,system,content in repeat.prior.score.initial_requests(repeat.ROOT,"benchpres",ref,query,reply["answer"]):
                    jobs.setdefault(field,{})[uid,m]=repeat.prior.text_request(system,content,prot["model"],prot["stages"][field]["max_tokens"])
            grades={}
            for field,wires in jobs.items():
                stage=f"Grade{rep}_{field}"
                engine.CAP[stage]=len(wires)
                result=engine.stage(stage,wires,ident,True,ledger)
                for k,v in result.items():
                    if v["status"]=="OK":grades.setdefault(k,{})[field]=v["answer"]
            for k,reply in answers.items():
                raw=grades.get(k,{})
                score=None
                if set(raw)==set(repeat.STAGES):
                    try:
                        score=repeat.prior.score.grade(repeat.ROOT,"benchpres",refs[k[0]],raw)
                    except (KeyError,ValueError,TypeError):
                        pass
                rows.append(dict(uid=k[0],model=k[1],rep=rep,actor=reply,score=score))
            probe.freeze(OUT/f"DRAW{rep}.json",{"rows":rows.copy(),"ledger":ledger.copy()})
if __name__=="__main__":
    if sys.argv[1:] not in (["check"],["run"]):raise SystemExit("check or run")
    main(sys.argv[1]=="run")
