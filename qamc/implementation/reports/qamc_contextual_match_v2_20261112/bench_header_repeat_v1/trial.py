"""Repeat matched scoring wires without generating new user-facing answers."""
import json
import re
from collections import Counter
from pathlib import Path
import experiment as source
from incremental_panel import sha
from run_probe import engine, probe
import run_qamc_benchpres_three_draw as repeat

here = Path(__file__).resolve().parent
run = source.RUN.with_name(here.name)
out = run / "material"
prev = source.RUN.with_name("bench_duplicate_recipient_v1")
read = source.read

def main():
    uids = sorted(read(prev / "material/EDITS.json"))
    cases = {c["uid"]:c for c in read(source.OLD / "PLAN_PRIVATE.json")["cases"]}
    batches, saved = {}, {}
    for old, method in ((source.RUN, "baseline"), (prev, "edit")):
        for path in old.glob("Grade_*/visible/*/record.json"):
            rec = read(path)
            uid = rec["unit"]["root_id"]
            if uid not in uids or rec["unit"]["method"] != method:
                continue
            field = path.parents[2].name.removeprefix("Grade_")
            wire = read(path.with_name("request.json"))
            assert sha(wire) == rec["request_sha256"] and rec["status"] == "OK"
            saved.setdefault((uid,method),{})[field] = read(path.with_name("response.json"))["answer"]
            payload = json.loads(wire["messages"][-1]["content"])
            if field == "BenchComplete" or re.search(r"\b(concise|brief)\b",payload.get("preference",""),re.I):
                batches.setdefault(field,{})[uid,method] = wire
    out.mkdir(parents=True,exist_ok=True)
    probe.RUN,probe.OUT,engine.OUT = run,out,out
    with probe.runner_lock(run/"runner.lock"):
        ledger, result = [], []
        manifest = {f:{"/".join(k):sha(w) for k,w in b.items()} for f,b in batches.items()}
        probe.freeze(out/"FROZEN.json",manifest)
        ident = {"experiment_sha256":sha([manifest,sha((here/"PROTOCOL.md").read_bytes())]),"service_reference_sha256":probe.read_reference()[1]}
        for field,batch in sorted(batches.items()):
            order = {}
            for i,u in enumerate(uids):
                if (u,"baseline") not in batch:
                    assert (u,"edit") not in batch
                    continue
                for m in (("baseline","edit") if i%2==0 else ("edit","baseline")):
                    order[u,m]=batch[u,m]
            name = "Repeat_"+field
            engine.CAP[name] = len(order)
            records = engine.stage(name,order,ident,True,ledger)
            for (u,m),r in records.items():
                ref=read(repeat.ROOT/cases[u]["evaluation_path"])
                assert repeat.digest(ref)==cases[u]["evaluation_hash"]
                def extract(raw):
                    g=repeat.prior.score.grade(repeat.ROOT,"benchpres",ref,raw)
                    if field=="BenchComplete":
                        return g["task_completeness"]
                    return g["decisions"][int(field.removeprefix("BenchAttr"))]["label"]
                raw=saved[u,m]
                val=None
                if r["status"]=="OK":
                    try:
                        val=extract(dict(raw,**{field:r["answer"]}))
                    except (ValueError,KeyError,TypeError):
                        pass
                result.append(dict(case=uind(uids,u),field=field,arm=m,original=extract(raw),replicate=val))
        probe.freeze(out/"SETTLED.json",dict(rows=result,ledger=ledger))
        print(json.dumps(result,indent=2))
def uind(uids,u):
    return uids.index(u)+1
if __name__=="__main__":
    main()
