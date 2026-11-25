"""Collect fixed-Actor exposure contrasts on induction groups only."""
import argparse
from collections import Counter
import json
from pathlib import Path

from census import BASE, prior, read, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from prepare_qamc_rpeval_actor_development import body
from qamc_rpeval_terminal_judge_sensitivity import inspect
from score_task_only import OUT as ZERO_OUT

HERE = Path(__file__).resolve().parent
v41 = prior.R["archived"].v41
engine, probe = prior.engine, prior.probe
transfer = engine.transfer
ARMS = ("EMPTY","COMPLETE")
ACTOR = "InterventionActor"
BENCHMARKS = {"rpeval":"RPEval","benchpres":"BenchPreS","persistbench":"PersistBench"}
SYSTEM = """Write the user-facing answer to the current task. Deliver what the request asks for, in its language and appropriate form. Treat current facts and constraints as authoritative. The historical evidence may be empty. Use historical evidence only where useful and applicable to the person, decision and scope of this request. Do not infer that another person shares the user's preferences, treat subjective opinions as public facts, or invent facts. Honor restrictions that apply to the current task and keep all required deliverable details. Return the complete final answer."""


def task_packet(root, arm):
    return {**root["public_task"],"source_evidence":root["original_sources"] if arm=="COMPLETE" else []}


def freeze():
    split = read(HERE/"INVENTORY.json")
    rpe_frozen = read(v41.OUT/"FROZEN.json")
    if rpe_frozen["independent_confirmation"]:
        raise ValueError("Not an exposed archive")
    parent = read(v41.formal.OUT/"PLAN.json")
    contexts = {"RPEval": (v41.author_cases(parent),parent),
                **{b:transfer.context(b)[:2] for b in ("BenchPreS","PersistBench")}}
    roots = {"RPEval":{r["uid"]:r for r in rpe_frozen["roots"]},
             **{b:{r["uid"]:r for r in transfer.development_roots(b)}
                for b in ("BenchPreS","PersistBench")}}
    labels = {r["uid"]:r["labels"] for r in read(ZERO_OUT/"RESULTS.json")["roots"]}
    cards = []
    for domain,title in BENCHMARKS.items():
        registry = split["benchmarks"][domain]
        eligible = registry["training_pairs"]
        held = {r["group"] for r in registry["policy_evaluation_roster"]}
        used = set()
        for stratum in sorted({r["stratum"] for r in eligible}):
            n = 4 if title=="BenchPreS" else 2
            subset = sorted((r for r in eligible if r["stratum"]==stratum),
                            key=lambda r:sha(["fixed-execution-contrast-v1",r["group"],r["uid"]]))
            for row in subset:
                uid,group = row["uid"],row["group"]
                if group in held or group not in registry["training_group_ids"]:
                    raise ValueError("Evaluation data entered induction")
                if uid not in roots[title] or uid not in contexts[title][0] or group in used:
                    continue
                root = roots[title][uid]
                if not root["original_sources"]:
                    continue
                wires = {arm:body(SYSTEM,task_packet(root,arm),4096) for arm in ARMS}
                for wire in wires.values():
                    validate_public_request(wire)
                if wires["EMPTY"]["messages"][0]!=wires["COMPLETE"]["messages"][0]:
                    raise ValueError("Intervention altered Actor instructions")
                cards.append({"uid":uid,"group":group,"benchmark":title,"stratum":stratum,
                              "source_ids":[s["memory_id"] for s in root["original_sources"]],
                              "wires":wires})
                used.add(group)
                n-=1
                if n==0:
                    break
            if n:
                raise ValueError(f"Insufficient training cases for {domain}/{stratum}")
    plan = {"cards":cards,"split_sha256":sha(split),"code_sha256":sha(Path(__file__).read_bytes()),
            "model":"qwen3.8-flash","allowed_actor_cap":2*len(cards),
            "allowed_judge_caps":{title:sum(2 for c in cards if c["benchmark"]==title)*(
                6 if title=="BenchPreS" else 1) for title in BENCHMARKS.values()}}
    return plan,contexts,labels,roots


def execution(action, data):
    plan, contexts, labels, roots = data
    probe.OUT = engine.OUT = HERE
    probe.RUN = engine.RUN.with_name(HERE.name)
    stages = {"RPEval":engine.RPE,"BenchPreS":"FeedbackBenchJudge","PersistBench":"FeedbackPersistJudge"}
    engine.CAP = {ACTOR:plan["allowed_actor_cap"],
                  **{stages[b]:n for b,n in plan["allowed_judge_caps"].items()}}
    identity = {"experiment_sha256":sha(plan),"service_reference_sha256":probe.read_reference()[1]}
    live, ledger = action=="run", []
    with probe.runner_lock(probe.RUN/"runner.lock"):
        probe.freeze(HERE/"EXECUTION.json",identity)

        def stage(name,jobs):
            return engine.stage(name,jobs,identity,live,ledger) if jobs else {}

        jobs = {(c["uid"],m):c["wires"][m] for c in plan["cards"] for m in
                sorted(ARMS,key=lambda method:sha([c["uid"],method]))}
        actors = stage(ACTOR,jobs)
        rows = []
        for c in plan["cards"]:
            for arm in ARMS:
                v = actors[c["uid"],arm]
                rows.append({**{k:c[k] for k in ("uid","group","benchmark","stratum")},
                             "method":arm,"actor_status":v["status"],
                             "answer":v["answer"],"actor_request_sha256":v["request_sha256"],
                             "visible_ids":c["source_ids"] if arm=="COMPLETE" else [],
                             "score":None})
        rpe = [r for r in rows if r["benchmark"]=="RPEval"]
        engine.grade_rpe(roots["RPEval"],rpe,lambda name,jobs,cache=None:
                         engine.stage(name,jobs,identity,live,ledger,cache) if jobs else {})
        for row in rpe:
            score, judge = row["score"], row.get("judge")
            row["score_flags"] = inspect({"uid":row["uid"],"method":row["method"],"answer":row["answer"],
                "native_fields":score,"raw_scores":{v41.NATIVE:judge["answer"]}},labels[row["uid"]])["flags"] if (
                score and score.get("match") and judge and judge.get("answer")) else None
        for b in ("BenchPreS","PersistBench"):
            cases, protocol = contexts[b]

            def dispatch(wires):
                keyed = {(uid,f"{arm}/{field}"):wire for (uid,arm,field),wire in wires.items()}
                out = stage(stages[b],keyed)
                return {(u,a,f):out[u,f"{a}/{f}"] for u,a,f in wires}

            transfer.grade(b,[r for r in rows if r["benchmark"]==b],cases,protocol,dispatch)
        result = {"rows":rows,"ledger":ledger,"calls":Counter(r["unit"]["stage"] for r in ledger),
                  "statuses":Counter(r["status"] for r in ledger),
                  "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "usage_unknown":sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        path = HERE/"RESULTS.json"
        if live:
            probe.freeze(path,result)
        elif read(path)!=result:
            raise ValueError("Controlled execution feedback does not replay")
        print({k:v for k,v in result.items() if k not in ("rows","ledger")})


if __name__=="__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("action",choices=("freeze","check","run","replay"))
    args = cli.parse_args()
    data = freeze()
    path = HERE/"FROZEN_PAIR_COLLECTION.json"
    if args.action=="freeze":
        probe.freeze(path,data[0])
    elif data[0]!=read(path):
        raise SystemExit("Intervention manifest drift")
    elif args.action!="check":
        execution(args.action,data)
    print({"roster":Counter(c["benchmark"] for c in data[0]["cards"]),
           "actor_cap":data[0]["allowed_actor_cap"],"judge_caps":data[0]["allowed_judge_caps"]})
