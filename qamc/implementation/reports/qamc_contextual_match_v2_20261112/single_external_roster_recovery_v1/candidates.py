"""Complete only MemAdapter for the 20 development rows with two verified answers."""
from collections import Counter
import json
from cache_coverage import archive_paths, search, MemAdapterBridge
from wires import ROOT, LEGACY, PublicTask, Memory, read, key, roster, sha
from run_bridge import engine, probe

HERE = ROOT / "reports/qamc_contextual_match_v2_20261112/single_external_roster_recovery_v1"
RUN = engine.RUN.with_name("single_external_memadapter_v1")


def batch():
    cases = roster()[-1]
    tasks = {}
    for row in read(LEGACY / "qamc_des2gen/ALL_NINE_CASE_DETAILS.json"):
        c = row["case"]
        if c["benchmark"] != "rpeval" or key(c) not in cases:
            continue
        if not all(row["methods"][m]["answer"] for m in ("RPR_PAPER_XBENCH","D2G_PAPER_ADAPT")):
            continue
        v = row["original_public_input"]
        tasks[v["uid"]] = PublicTask(v["uid"],v["query"],tuple(Memory(m["memory_id"],m["text"],tuple(map(tuple,m["ranges"])))
                                     for m in v["memories"]),v["current_context"],tuple(v["fixed_facts"]))
    assert len(tasks) == 20
    bridge = MemAdapterBridge(ROOT / "literature/qamc_contextual_match_20261111/MemAdapter")
    engine.OUT = probe.RUN = probe.OUT = RUN
    engine.CAP = {s:20 for s in ("Stage1","Stage2","Stage3")}
    RUN.mkdir(exist_ok=True,parents=True)
    with probe.runner_lock(RUN / "runner.lock"):
        lock = {"inputs":{u:sha(t.payload()) for u,t in tasks.items()},"code":sha((HERE/"candidates.py").read_bytes()),
                "bridge":bridge.manifest(),"service":probe.read_reference()[1]}
        probe.freeze(RUN/"FROZEN.json",lock)
        paths = [p for p in archive_paths() if RUN.name not in p.parts]
        states = dict.fromkeys(tasks)
        ledger = []
        counts = {}
        for stage in engine.CAP:
            wires = {(u,stage):bridge.request(tasks[u],stage,v) for u,v in states.items()}
            hits = search(wires,paths)
            fresh = {k:w for k,w in wires.items() if k not in hits}
            replies = engine.stage(stage,fresh,{"experiment_sha256":sha(lock),"service_reference_sha256":lock["service"]},
                                   True,ledger) if fresh else {}
            states = {}
            status = Counter()
            for u,k in wires:
                if (u,k) in hits:
                    answers = set(filter(None,hits[u,k]))
                    answer = answers.pop() if len(answers)==1 else None
                else:
                    record = replies[u,k]
                    answer = record.get("answer") if record["status"]=="OK" else None
                if not answer:
                    status["missing"]+=1
                    continue
                try:
                    states[u] = answer if stage=="Stage3" else bridge.parse(tasks[u],stage,answer)
                    status["valid"]+=1
                except (KeyError,ValueError,TypeError):
                    status["invalid"]+=1
            counts[stage]=dict(status)
            probe.freeze(RUN/(stage+"_OUTPUT.json"),states)
        probe.freeze(RUN/"LEDGER.json",ledger)
        result={"stage_counts":counts,"requests":len(ledger),"reported_tokens":sum((v.get("usage") or {}).get("total_tokens",0) for v in ledger),
                "unknown_usage":sum((v.get("usage") or {}).get("total_tokens") is None for v in ledger),"statuses":dict(Counter(v["status"] for v in ledger))}
        probe.freeze(RUN/"SUMMARY.json",result)
        print(json.dumps(result))


if __name__=="__main__":
    batch()
