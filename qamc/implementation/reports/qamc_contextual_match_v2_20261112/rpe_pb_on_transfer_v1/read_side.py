"""Transfer the frozen read side and record source identities; no author labels in its wires."""
import json
import sys
from panel import HERE, FORMAL, read, roster
from complete import engine, probe
from extend import archived, merge_stage
from persist_grounding_gepa_wires import input_requests, select, transfer
from qamc.common import sha

ROOT = HERE.parents[2]
RUN = engine.RUN.with_name(HERE.name)

def prepare():
    panel = roster()
    if panel != read(HERE / "PANEL.json"):
        raise ValueError("Panel changed")
    tasks = read(FORMAL / "PUBLIC_TASKS.json")
    proto = read(transfer.OUT / "PLAN.json")
    public, wires = {}, {}
    for row in panel:
        uid = row["uid"]
        task = tasks[uid]
        public[uid] = {"query": task["query"], "memories": [m["text"] for m in task["memories"]]}
        wires[uid] = input_requests({"uid":uid}, public[uid], proto)
        for mode, wire in wires[uid].items():
            packet = json.loads(wire["messages"][1]["content"])
            if packet["query"] != task["query"] or uid in str(wire["messages"]):
                raise ValueError("Invalid public translation")
            if mode == "query" and set(packet) != {"query"}:
                raise ValueError("Router read more than Query")
            if mode != "query" and [m["text"] for m in packet["memories"]] != public[uid]["memories"]:
                raise ValueError("Selection evidence drift")
    return public, wires

def run(live):
    public, wires = prepare()
    if not live:
        print(f"{len(public)} ON tasks; {sum(map(len,wires.values()))} possible read-side wires verified")
        return
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {"Route":12,"Select":12}
    ident = {"experiment_sha256":sha([read(HERE/"PANEL.json"),wires,(HERE/"PROTOCOL.md").read_text(),
                                      (HERE/"read_side.py").read_text()]),
             "service_reference_sha256":probe.read_reference()[1]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "READ_EXECUTION.json", ident)
        def stage(label,jobs):
            pin = RUN / f"{label}_prior.json"
            if not pin.exists():
                hits,_ = archived({sha(w):w for w in jobs.values()}, ROOT)
                probe.freeze(pin,hits)
            hits = read(pin)
            cached = {k:hits[sha(w)] for k,w in jobs.items() if sha(w) in hits}
            return merge_stage(label,jobs,cached,ident,ledger)
        routes = stage("Route",{(u,"PB"):w["query"] for u,w in wires.items()})
        branches, jobs, result = {}, {}, {}
        for key,r in routes.items():
            uid,_ = key
            result[uid]={"status":r["status"],"route":r}
            if r["status"]!="OK":
                continue
            try:
                decision=transfer.confirmation.route.decode(r["answer"],public[uid]["query"])
            except (KeyError,TypeError,ValueError):
                result[uid]["status"]="INVALID_ROUTE"
                continue
            branches[uid]="style" if decision["check_history"] else "grounding"
            jobs[key]=wires[uid][branches[uid]]
        for (uid,_),r in stage("Select",jobs).items():
            obj=result[uid]
            obj.update(branch=branches[uid],selector=r,status=r["status"])
            if r["status"]!="OK":
                continue
            try:
                texts=select({"uid":uid},public[uid],obj["route"]["answer"],r["answer"])
                memories=public[uid]["memories"]
                if len(set(texts))!=len(texts) or not set(texts)<=set(memories):
                    raise ValueError("Unmatched selection")
                obj["positions"]=[i for i,text in enumerate(memories) if text in texts]
            except (KeyError,TypeError,ValueError):
                obj["status"]="INVALID_SELECTION"
        probe.freeze(RUN/"READ_RESULTS.json",{"rows":result,"ledger":ledger})

if __name__=="__main__":
    if sys.argv[1:] not in (["check"],["run"]):
        raise SystemExit("check or run")
    run(sys.argv[1]=="run")
