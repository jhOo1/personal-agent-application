import json
import re
from pathlib import Path
import experiment as source
from run_probe import engine, probe
from incremental_panel import sha
import run_qamc_benchpres_three_draw as repeat

here = Path(__file__).resolve().parent
run = source.RUN.with_name(here.name)
out = run / "material"

def strip_recipient(answer):
    lines = answer.splitlines(keepends=True)
    if not lines:
        return answer
    header = re.fullmatch(r"To:\s*(.+)", lines[0].strip(), re.I)
    if not header:
        return answer
    recipient = header[1].strip().casefold()
    front = [s.strip() for s in lines[1:] if s.strip()][:5]
    if any(s.casefold().rstrip(",.:") == "dear " + recipient for s in front):
        return "".join(lines[1:])
    return answer

def main():
    plan = source.read(source.OLD / "PLAN_PRIVATE.json")
    cases = {c["uid"]: c for c in plan["cases"]}
    grading = plan["protocols"]["grading"]
    assert all(not c["independent_confirmation"] for c in cases.values())
    edits = {}
    for path in (source.RUN/"Actor/visible").glob("*/record.json"):
        rec = source.read(path)
        if rec["status"] != "OK" or rec["unit"]["method"] != "baseline":
            continue
        uid = rec["unit"]["root_id"]
        answer = source.read(path.with_name("response.json"))["answer"]
        updated = strip_recipient(answer)
        if updated != answer:
            assert updated == answer[len(answer.splitlines(keepends=True)[0]):]
            edits[uid] = updated
    old = {r["uid"]:r["score"] for r in source.read(source.OUT/"SETTLED.json")["rows"] if r["arm"]=="baseline"}
    out.mkdir(parents=True,exist_ok=True)
    probe.RUN,probe.OUT,engine.OUT = run,out,out
    with probe.runner_lock(run/"runner.lock"):
        roster = {u:sha(a) for u,a in sorted(edits.items())}
        probe.freeze(out/"EDITS.json",roster)
        ident = {"experiment_sha256":sha([roster,sha((here/"PROTOCOL.md").read_bytes())]),"service_reference_sha256":probe.read_reference()[1]}
        batches, refs, raw, ledger = {}, {}, {}, []
        for u,a in edits.items():
            ref=source.read(repeat.ROOT/cases[u]["evaluation_path"])
            assert repeat.digest(ref)==cases[u]["evaluation_hash"]
            refs[u]=ref
            query=repeat.prior.base.task_for(cases[u]).query
            for field,system,content in repeat.prior.score.initial_requests(repeat.ROOT,"benchpres",ref,query,a):
                batches.setdefault(field,{})[u,"edit"]=repeat.prior.text_request(system,content,grading["model"],grading["stages"][field]["max_tokens"])
        for field,items in batches.items():
            name="Grade_"+field
            engine.CAP[name]=len(items)
            for (u,_),r in engine.stage(name,items,ident,True,ledger).items():
                if r["status"]=="OK":
                    raw.setdefault(u,{})[field]=r["answer"]
        new = dict(old)
        for u in edits:
            new[u]=None
            if set(raw.get(u,{}))==set(repeat.STAGES):
                try:
                    new[u]=repeat.prior.score.grade(repeat.ROOT,"benchpres",refs[u],raw[u])
                except (ValueError,TypeError,KeyError):
                    pass
        summary={"assigned":len(cases),"changed":len(edits)}
        for key,pool in (("all",cases),("changed",edits)):
            ids=[u for u in pool if old.get(u) and new.get(u)]
            summary[key]={"paired":len(ids)}
            for arm,records in (("original",old),("edited",new)):
                summary[key][arm]={k:sum(records[u][k] for u in ids) for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness")}
        probe.freeze(out/"SETTLED.json",dict(summary=summary,new=new,ledger=ledger))
        print(json.dumps(summary,indent=2))
if __name__=="__main__":
    main()
