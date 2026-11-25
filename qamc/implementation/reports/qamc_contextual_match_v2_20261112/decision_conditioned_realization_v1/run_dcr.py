"""Matched local versus shared evidence exposure for decision realization."""
import argparse
from collections import Counter
from pathlib import Path

from run_cdc import archive, engine, grading, parse, probe, sha, validate_public_request, canonical, token_estimate

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
PARENT = HERE.parent / "counterfactual_commitment_v1" / "FROZEN.json"
ARMS = ("LOCAL", "SHARED")
PROMPTS = {
    "Prepare": """Read the current task and exact historical sources. Return JSON {"groups":[{"question":"concrete decision to solve","evidence":[{"source":0,"quote":"exact contiguous source substring"}]}],"state":[{"source":0,"quote":"exact current object state"}],"style":[{"source":0,"quote":"exact applicable expression preference"}]}. Use one or two groups, merging coupled decisions. Source is the zero-based index. Preserve scope and limiting clauses. Do not put proposed decisions or preferences in shared state. Do not promote private beliefs to public facts or ordinary habits to shared requirements. Do not generate an answer.""",
    "Solve": """Resolve the specified decision for this task using the available evidence and known state. Produce actual deliverable content, not instructions to another model. Respect applicable constraints and affected parties. Leave unsupported details unknown. Return JSON {"content":"concrete deliverable content"}.""",
    "Realize": """Produce only the requested complete answer. Faithfully realize the resolved content and known task state. Preserve all necessary facts and constraints. Use applicable expression preferences through wording, compression and organization. Do not introduce new private facts or re-decide the content. Return JSON {"answer":"complete final answer"}.""",
}
CAP = {"Prepare":24,"Solve":96,"Realize":48,engine.RPE:16,"BenchAttrs":96,"PersistNative":16}


def freeze():
    parent = archive.read(PARENT)
    return {"rows":parent["rows"],"parent_sha256":sha(PARENT.read_bytes()),
            "code_sha256":sha(Path(__file__).read_bytes()),"prompts":PROMPTS,"caps":CAP}


def wire(stage, payload):
    request = archive.body(PROMPTS[stage], payload, 8192)
    validate_public_request(request)
    if token_estimate(canonical(request["messages"])) > 32768:
        raise ValueError("INPUT_CAPACITY")
    return request


def compile_plan(reply, sources):
    def evidence(entries):
        if not isinstance(entries,list):
            raise ValueError("expected evidence list")
        values = []
        for entry in entries:
            index, quote = entry["source"], entry["quote"]
            if type(index) is not int or not 0 <= index < len(sources):
                raise ValueError("invalid source")
            if not isinstance(quote,str) or not quote.strip() or quote not in sources[index]["text"]:
                raise ValueError("invalid source quote")
            item = {"source":index,"quote":quote}
            if item not in values:
                values.append(item)
        return values
    groups = reply["groups"]
    if not isinstance(groups,list) or not 1 <= len(groups) <= 2:
        raise ValueError("expected one or two groups")
    compiled = []
    for group in groups:
        question = group["question"]
        if not isinstance(question,str) or not question.strip():
            raise ValueError("missing decision question")
        compiled.append({"question":question,"evidence":evidence(group["evidence"])})
    return {"groups":compiled,"state":evidence(reply["state"]),"style":evidence(reply["style"])}


def solve_payload(task, plan, index, arm):
    group = plan["groups"][index]
    pool = group["evidence"] if arm == "LOCAL" else [
        quote for group in plan["groups"] for quote in group["evidence"]]
    unique = {(q["source"],q["quote"]):q for q in pool}
    return {"task":task,"known_state":plan["state"],"decision":group["question"],
            "evidence":[unique[key] for key in sorted(unique)]}


def nonempty(reply, key):
    value = reply[key]
    if not isinstance(value,str) or not value.strip():
        raise ValueError(f"empty {key}")
    return value


def run(plan, live):
    probe.RUN,probe.OUT,engine.OUT = RUN,HERE,HERE
    engine.CAP = CAP
    identity = {"experiment_sha256":sha(plan),"service_reference_sha256":probe.read_reference()[1]}
    ledger, rows, issues, compiled = [], [], {}, {}
    inputs = {row["uid"]:row for row in plan["rows"]}
    with probe.runner_lock(RUN/"runner.lock"):
        probe.freeze(HERE/"EXECUTION.json",identity)

        def stage(name, jobs, cache=None):
            return engine.stage(name,jobs,identity,live,ledger,cache) if jobs else {}

        def request(jobs, name, key, payload):
            try:
                jobs[key] = wire(name,payload)
            except (ValueError,TypeError,KeyError) as exc:
                issues[str((name,key))] = str(exc)

        def decode(name, key, rec, extract):
            if rec["status"] != "OK":
                issues[str((name,key))] = rec["status"]
                return None
            try:
                return extract(parse(rec["answer"]))
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                issues[str((name,key))] = str(exc)
                return None

        jobs = {}
        for uid,row in inputs.items():
            sources = row["packet"]["source_evidence"]
            request(jobs,"Prepare",(uid,"prep"),{"task":row["packet"]["task"],
                "sources":[{"source":i,"text":s["text"]} for i,s in enumerate(sources)]})
        for key,rec in stage("Prepare",jobs).items():
            uid,_ = key
            value = decode("Prepare",key,rec,lambda reply:compile_plan(
                reply,inputs[uid]["packet"]["source_evidence"]))
            if value is not None:
                compiled[uid] = value

        jobs = {}
        for uid,context in compiled.items():
            task = inputs[uid]["packet"]["task"]
            for arm in ARMS:
                for i in range(len(context["groups"])):
                    request(jobs,"Solve",(uid,f"{arm}/{i}"),solve_payload(task,context,i,arm))
        solved = {key:decode("Solve",key,rec,lambda r:nonempty(r,"content"))
                  for key,rec in stage("Solve",jobs).items()}
        jobs = {}
        for uid,context in compiled.items():
            for arm in ARMS:
                content = [solved.get((uid,f"{arm}/{i}")) for i in range(len(context["groups"]))]
                if all(content):
                    request(jobs,"Realize",(uid,arm),{"task":inputs[uid]["packet"]["task"],
                      "known_state":context["state"],"content":content,"expression":context["style"]})
        final = stage("Realize",jobs)
        for uid,source in inputs.items():
            for arm in ARMS:
                key = uid,arm
                answer = decode("Realize",key,final[key],lambda r:nonempty(r,"answer")) if key in final else None
                exact = answer == source["base_answer"]
                rows.append({**{k:source[k] for k in ("uid","group","benchmark","stratum")},
                    "method":arm,"answer":answer,"actor_status":"OK" if answer else "MISSING",
                    "sources":source["packet"]["source_evidence"],
                    "score":source["base_score"] if exact else None,
                    "score_flags":source["base_flags"] if exact else None})
        grading(rows,stage)
        result = {"rows":rows,"compiled":compiled,"issues":issues,"ledger":ledger,
                  "calls":dict(Counter(r["unit"]["stage"] for r in ledger)),
                  "statuses":dict(Counter(r["status"] for r in ledger)),
                  "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger)}
        probe.freeze(HERE/"RESULTS.json",result)
        print(result["calls"],result["statuses"])


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("action",choices=("freeze","run"))
    action = cli.parse_args().action
    plan = freeze()
    if action == "freeze":
        probe.freeze(HERE/"FROZEN.json",plan)
    else:
        if archive.read(HERE/"FROZEN.json") != plan:
            raise SystemExit("Frozen configuration drift")
        run(plan,True)
