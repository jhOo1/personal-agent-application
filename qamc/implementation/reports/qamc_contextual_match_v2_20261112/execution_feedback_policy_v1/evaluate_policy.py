"""Source-separated screen of the seed and the two frozen reflection policies."""
import argparse
from collections import Counter
from pathlib import Path

import collect_interventions as setup
from compiled_policy import SEED, actor_wire, adopted_components, select_sources, selection_wire
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from qamc_rpeval_terminal_judge_sensitivity import inspect

HERE = Path(__file__).resolve().parent
OUT = HERE/"held_screen_v1"
REFLECTION = HERE/"reflection_capacity_v2"
ARMS = ("SEED","TRAJECTORIES","INTERVENTION")
CAP = {"FeedbackSelector":24,"FeedbackActor":24,"RPEvalJudge":9,"FeedbackBenchJudge":36,"FeedbackPersistJudge":9}


def freeze():
    _,contexts,labels,roots = setup.freeze()
    roster = setup.read(HERE/"HELD_SCREEN_ROSTER.json")
    inventory = setup.read(HERE/"INVENTORY.json")["benchmarks"]
    proposal = setup.read(REFLECTION/"RESULTS.json")
    policies = {"SEED":SEED,**proposal["proposals"]}
    if set(policies)!=set(ARMS):
        raise ValueError("The matched proposal generation did not yield two usable policies")
    for p in policies.values():
        adopted_components(p)
    panel,requests = [],{}
    for domain, cases in roster.items():
        benchmark = setup.BENCHMARKS[domain]
        allowed = {r["uid"]:r for r in inventory[domain]["policy_evaluation_roster"]}
        for case in cases:
            uid,group = case["uid"],case["group"]
            if case!=allowed[uid] or group in inventory[domain]["training_group_ids"]:
                raise ValueError("Source-group or roster mismatch")
            if uid not in contexts[benchmark][0]:
                raise ValueError("No archived grader case")
            root = roots[benchmark][uid]
            panel.append({**case,"benchmark":benchmark,"public_sha256":sha(root["public_task"]),
                          "source_sha256":sha(root["original_sources"])})
            requests[uid] = {arm:selection_wire(root,policies[arm]) for arm in ARMS}
    if len(panel)!=8:
        raise ValueError("The held screen requires exactly eight tasks")
    if any(token_estimate(canonical(w["messages"]))>32768 for limbs in requests.values() for w in limbs.values()):
        raise ValueError("A Selector request exceeds transport capacity")
    plan = {"panel":panel,"requests":requests,"policies":policies,"caps":CAP,
            "code_sha256":sha(Path(__file__).read_bytes()),
            "compiler_sha256":sha((HERE/"compiled_policy.py").read_bytes()),
            "proposal_sha256":sha(proposal)}
    return plan,contexts,labels,roots


def measure(data,live):
    plan,contexts,labels,roots = data
    probe,engine = setup.probe,setup.engine
    probe.OUT = engine.OUT = OUT
    probe.RUN = engine.RUN.with_name(f"{HERE.name}_{OUT.name}")
    engine.CAP = CAP
    identity = {"experiment_sha256":sha(plan),"service_reference_sha256":probe.read_reference()[1]}
    ledger = []
    with probe.runner_lock(probe.RUN/"runner.lock"):
        probe.freeze(OUT/"EXECUTION.json",identity)

        def stage(name,jobs,cache=None):
            return engine.stage(name,jobs,identity,live,ledger,cache) if jobs else {}

        selection_jobs = {(uid,arm):w for uid,arms in plan["requests"].items() for arm,w in arms.items()}
        selections = stage("FeedbackSelector",selection_jobs)
        rows,actors = [],{}
        for case in plan["panel"]:
            uid,benchmark = case["uid"],case["benchmark"]
            root = roots[benchmark][uid]
            for arm in ARMS:
                sel = selections[uid,arm]
                item = {**case,"method":arm,"selection":sel,"visible_ids":[],
                        "actor_status":"SELECTOR_"+sel["status"],"answer":None,"score":None}
                rows.append(item)
                if sel["status"]!="OK":
                    continue
                try:
                    evidence = select_sources(sel["answer"],root)
                except (TypeError,ValueError) as error:
                    item.update(actor_status="SELECTOR_CONTRACT_FAILURE",selection_error=str(error))
                    continue
                item["visible_ids"] = [s["memory_id"] for s in evidence]
                actors[uid,arm] = actor_wire(root,plan["policies"][arm],evidence)
        answers = stage("FeedbackActor",actors)
        for item in rows:
            reply = answers.get((item["uid"],item["method"]))
            if reply:
                item.update(actor_status=reply["status"],answer=reply["answer"],
                            actor_request_sha256=reply["request_sha256"])
        partial = {b:[r for r in rows if r["benchmark"]==b] for b in setup.BENCHMARKS.values()}
        engine.grade_rpe(roots["RPEval"],partial["RPEval"],stage)
        for row in partial["RPEval"]:
            score,judge = row["score"],row.get("judge")
            row["score_flags"] = inspect({**row,"native_fields":score,"raw_scores":{setup.v41.NATIVE:judge["answer"]}},
                                         labels[row["uid"]])["flags"] if score and score.get("match") and judge else None
        comparisons = {}
        for benchmark,tag in (("BenchPreS","FeedbackBenchJudge"),("PersistBench","FeedbackPersistJudge")):
            cases,protocol = contexts[benchmark]
            present = {row["uid"] for row in partial[benchmark]}
            cases = {uid:case for uid,case in cases.items() if uid in present}
            archive = setup.transfer.archived_answers(benchmark,cases)
            exact,_ = setup.transfer.matching_grading_receipts(benchmark,cases,protocol,archive)

            def dispatch(wires):
                result = stage(tag,{(u,f"{a}/{metric}"):wire for (u,a,metric),wire in wires.items()},exact)
                return {key:result[key[0],f"{key[1]}/{key[2]}"] for key in wires}

            setup.transfer.grade(benchmark,partial[benchmark],cases,protocol,dispatch)
            _,_,controls = setup.transfer.context(benchmark)
            cells = {(r["uid"],r["method"]):r["score"] for r in (*controls,*partial[benchmark])
                     if r["uid"] in present and r["score"] is not None}
            pair = setup.transfer.bench_pair if benchmark=="BenchPreS" else setup.transfer.persist_pair
            methods = sorted({method for _,method in cells} | set(ARMS))
            comparisons[benchmark] = {m:pair(m,"INTERVENTION",cases,cells)
                                      for m in methods if m!="INTERVENTION"}
        archived = {r["uid"]:roots["RPEval"][r["uid"]]["archived"] for r in plan["panel"] if r["benchmark"]=="RPEval"}
        result = {"rows":rows,"archived_RPEval":archived,"archive_comparison_other":comparisons,"ledger":ledger,
                  "calls":dict(Counter(r["unit"]["stage"] for r in ledger)),
                  "statuses":dict(Counter(r["status"] for r in ledger)),
                  "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "usage_unknown":sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        if live:
            probe.freeze(OUT/"RESULTS.json",result)
        elif setup.read(OUT/"RESULTS.json")!=result:
            raise ValueError("Held screen replay drift")
        print({k:result[k] for k in ("calls","statuses","tokens","usage_unknown")})


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action",choices=("freeze","check","run","replay"))
    args = parser.parse_args()
    data = freeze()
    path = OUT/"FROZEN.json"
    if args.action=="freeze":
        setup.probe.freeze(path,data[0])
    elif setup.read(path)!=data[0]:
        raise SystemExit("Held screen manifest drift")
    elif args.action!="check":
        measure(data,args.action=="run")
    print({"tasks":len(data[0]["panel"]),"caps":CAP})
