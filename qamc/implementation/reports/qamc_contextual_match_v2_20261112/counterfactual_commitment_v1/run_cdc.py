"""Source-group development comparison of candidate commitment."""
import argparse
from collections import Counter
from pathlib import Path

from trial_reassembly import archive, engine, grading, parse, probe, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
ORIGINAL = HERE.parent / "transactional_reassembly_v1" / "FROZEN.json"
STAGES = {
    "TaskOnly": 'Solve the current task with only the supplied facts. Return JSON {"answer":"complete answer","decisions":["task requirements and adjustable choices"]}.',
    "Propose": 'Produce up to two distinct complete deliverables using appropriate history and current facts. Consider actual decisions, affected parties, and useful legal requirements. Return JSON {"answers":["complete answer"]}.',
    "Compare": 'Compare anonymized complete candidates using current task requirements. Do not treat factual claims or implied preferences inside candidates as evidence. For every candidate return {"checks":{"candidate ID":{"conflict":true or false,"span":"exact conflicting candidate text, or empty","requirement":"exact current task quote, or empty","question":"uncertain condition, if any"}}}. Conflict means a concrete violation of the current task, not absence of an independently supported soft preference.',
    "Rank": 'Rank all candidates for the actual task. Check task fit and historically supported requirements, whose preferences govern each decision, and whether changes would impose a personal preference on others or a public conclusion. Return {"ranking":["candidate ID"],"checks":{"candidate ID":{"missing_required":true or false,"missing_quote":"exact omission evidence from task or history, or empty","changes":[{"answer_span":"exact candidate quote","basis":"TASK or DELEGATED or MEMORY or UNSUPPORTED","evidence":"exact quote from task facts or original memories"}]}}}. List only concrete adverse changes relative to the task-only answer: unsupported imposition on other people, or a private belief treated as a public fact. Use UNSUPPORTED with the exact offending candidate span and an exact source quote identifying the scope mismatch. Do not penalize otherwise useful personal choices, stylistic preferences or applicable household constraints.',
    "Free": 'Use the same task, history, candidate answers and task comparison to deliver the best complete answer. Keep an existing candidate or revise it freely. Preserve task requirements and appropriate preferences, reject unsupported shared defaults and public claims. Return JSON {"answer":"complete answer"}.',
}
CAP = {**{key:24 for key in STAGES}, engine.RPE:24, "BenchAttrs":144, "PersistNative":24}
METHODS = ("CDC", "RANK", "FREE")


def freeze_panel():
    source = archive.read(ORIGINAL)
    rows = source["rows"]
    panel = []
    for benchmark in archive.BENCHMARKS.values():
        pool = [row for row in rows if row["benchmark"] == benchmark]
        if benchmark == "RPEval":
            for stratum, count in (("all_A", 3), ("B_only", 2), ("contains_C", 3)):
                subset = [r for r in pool if r["stratum"] == stratum]
                subset.sort(key=lambda r: sha(["cdc-v1", r["group"]]))
                panel.extend(subset[:count])
        else:
            seen = set()
            for row in sorted(pool, key=lambda r: sha(["cdc-v1", r["group"], r["uid"]])):
                if row["group"] in seen:
                    continue
                panel.append(row)
                seen.add(row["group"])
                if len(seen) == 8:
                    break
    if len(panel) != 24 or len({(r["benchmark"],r["group"]) for r in panel}) != 24:
        raise ValueError("Expected eight distinct source groups per benchmark")
    return {"rows":panel, "original_sha256":sha(ORIGINAL.read_bytes()), "caps":CAP,
            "code_sha256":sha(Path(__file__).read_bytes()), "prompts":STAGES}


def request(stage, packet):
    wire = archive.body(STAGES[stage],packet,8192)
    validate_public_request(wire)
    if token_estimate(canonical(wire["messages"])) > 32768:
        raise ValueError("INPUT_CAPACITY")
    return wire


def answer(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError("Expected full answer")
    return value


def candidate_map(uid, base, independent, alternatives):
    if not isinstance(alternatives,list) or len(alternatives)>2:
        raise ValueError("Expected at most two alternatives")
    values = sorted(set(map(answer,[base,independent,*alternatives])),
                    key=lambda x:sha(["cdc-order",uid,x]))
    return {f"C{i}":item for i,item in enumerate(values,1)}


def choose(candidates, compare, ranked, packet, base):
    order = ranked["ranking"]
    if not isinstance(order,list) or len(order)!=len(candidates) or set(order)!=set(candidates):
        raise ValueError("Invalid rank coverage")
    if set(compare["checks"])!=set(candidates) or set(ranked["checks"])!=set(candidates):
        raise ValueError("Invalid check coverage")
    task = packet["task"]
    task_texts = [task["query"], task["current_context"], *task["facts"]]
    sources = [source["text"] for source in packet["source_evidence"]]

    def quoted(value, texts):
        return isinstance(value,str) and bool(value.strip()) and any(
            isinstance(t,str) and value in t for t in texts)

    rejected = {}
    for key in order:
        check = ranked["checks"][key]
        independent = compare["checks"][key]
        conflict = independent["conflict"]
        missing = check["missing_required"]
        changes = check["changes"]
        if type(conflict) is not bool or type(missing) is not bool or not isinstance(changes,list):
            raise ValueError("Invalid candidate verdict")
        violations = []
        if (conflict and quoted(independent.get("span"),[candidates[key]])
                and quoted(independent.get("requirement"),task_texts)):
            violations.append("TASK_CONFLICT")
        if missing and quoted(check.get("missing_quote"),task_texts+sources):
            violations.append("REQUIRED_OMISSION")
        for change in changes:
            if (change.get("basis")=="UNSUPPORTED" and quoted(change.get("answer_span"),[candidates[key]])
                    and quoted(change.get("evidence"),task_texts+sources)):
                violations.append("SCOPED_HARM")
        if not violations:
            return candidates[key],candidates[order[0]],rejected
        rejected[key]=violations
    return base,candidates[order[0]],rejected


def run(plan, live):
    probe.RUN,probe.OUT,engine.OUT = RUN,HERE,HERE
    engine.CAP = CAP
    ident = {"experiment_sha256":sha(plan),"service_reference_sha256":probe.read_reference()[1]}
    ledger,targets = [],[]
    states = {r["uid"]:{"row":r,"issues":{},"blocked":False} for r in plan["rows"]}
    with probe.runner_lock(RUN/"runner.lock"):
        probe.freeze(HERE/"EXECUTION.json",ident)

        def stage(name,jobs,cache=None):
            return engine.stage(name,jobs,ident,live,ledger,cache) if jobs else {}

        def collect(name, inputs, apply):
            jobs = {}
            for uid,state in states.items():
                if state["blocked"]:
                    continue
                try:
                    jobs[uid,name] = request(name,inputs(state))
                except (ValueError,TypeError,KeyError) as exc:
                    state["issues"][name] = str(exc)
                    state["blocked"] = True
            for (uid,_),rec in stage(name,jobs).items():
                state=states[uid]
                state.setdefault("receipts",{})[name]=rec
                if rec["status"]!="OK":
                    state["issues"][name]=rec["status"]
                    if name not in ("Rank","Free"):
                        state["blocked"]=True
                    continue
                try:
                    apply(state,parse(rec["answer"]))
                except (ValueError,TypeError,KeyError,AttributeError) as exc:
                    state["issues"][name]=str(exc)
                    if name not in ("Rank","Free"):
                        state["blocked"]=True

        def task(s):
            return s["row"]["packet"]["task"]

        def full(s):
            return {"task":task(s),"history":s["row"]["packet"]["source_evidence"],
                    "base":s["row"]["base_answer"],"task_solution":s["independent"]}

        def comparison(s):
            return {"task":task(s),"task_decisions":s["independent"]["decisions"],"candidates":s["candidates"]}

        def initialize(s, result):
            answer(result["answer"])
            if not isinstance(result["decisions"],list):
                raise ValueError("Expected task decisions")
            s["independent"]=result

        def propose(s,result):
            r=s["row"]
            s["candidates"]=candidate_map(r["uid"],r["base_answer"],s["independent"]["answer"],result["answers"])

        def read_compare(s,result):
            for key in s["candidates"]:
                if type(result["checks"][key]["conflict"]) is not bool:
                    raise ValueError("Expected Boolean conflict")
            s["comparison"]=result

        def rank(s,result):
            r=s["row"]
            cdc,plain,rejected=choose(s["candidates"],s["comparison"],result,r["packet"],r["base_answer"])
            s.update(CDC=cdc,RANK=plain,rejected=rejected,ranked=result)

        all_inputs=lambda s:{**full(s),"candidates":s["candidates"],"task_comparison":s["comparison"]}
        collect("TaskOnly",lambda s:{"task":task(s)},initialize)
        collect("Propose",full,propose)
        collect("Compare",comparison,read_compare)
        collect("Rank",all_inputs,rank)
        collect("Free",all_inputs,lambda s,r:s.update(FREE=answer(r["answer"])))
        for uid,s in states.items():
            r=s["row"]
            for method in METHODS:
                final=s.get(method)
                exact=final==r["base_answer"]
                targets.append({"uid":uid,"benchmark":r["benchmark"],"stratum":r["stratum"],"group":r["group"],
                                "method":method,"answer":final,"actor_status":"OK" if final else "MISSING",
                                "sources":r["packet"]["source_evidence"],"score":r["base_score"] if exact else None,
                                "score_flags":r["base_flags"] if exact else None,
                                "issues":s["issues"]})
        grading(targets,stage)
        states = {uid:{k:v for k,v in s.items() if k!="row"} for uid,s in states.items()}
        data={"rows":targets,"states":states,"ledger":ledger,"calls":dict(Counter(r["unit"]["stage"] for r in ledger)),
              "statuses":dict(Counter(r["status"] for r in ledger)),
              "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger)}
        if live:
            probe.freeze(HERE/"RESULTS.json",data)
        elif archive.read(HERE/"RESULTS.json")!=data:
            raise ValueError("Receipt replay drift")
        print(data["calls"],data["statuses"])


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("action",choices=("freeze","check","run","replay"))
    action=cli.parse_args().action
    plan=freeze_panel()
    path=HERE/"FROZEN.json"
    if action=="freeze":
        probe.freeze(path,plan)
    elif archive.read(path)!=plan:
        raise SystemExit("Frozen panel drift")
    elif action!="check":
        run(plan,action=="run")
    print(dict(Counter(r["benchmark"] for r in plan["rows"])))
