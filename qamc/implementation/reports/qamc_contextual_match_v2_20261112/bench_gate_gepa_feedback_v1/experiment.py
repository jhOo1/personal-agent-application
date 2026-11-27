"""Paired one-mutation GEPA feedback experiment on exact saved Gate evidence."""
import json
import sys
from collections import Counter
from pathlib import Path
from copy import deepcopy

from gepa.strategies.instruction_proposal import InstructionProposalSignature as Proposal
from incremental_panel import sha
from run_probe import engine, probe
import run_qamc_benchpres_three_draw as repeat

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RUN = engine.RUN.with_name(HERE.name)
OUT = RUN / "material"
OLD = RUN.with_name("benchpres_repeat_matched_v1")
GATE = "GEPA_SELECTED_BOUNDS"
SEED = "Deliver the requested answer directly using applicable supplied information. Preserve the necessary facts and task requirements."
ARMS = ("score", "behavior")


def read(p):
    return json.loads(p.read_text())


def prepare():
    plan = read(OLD / "PLAN_PRIVATE.json")
    cases = {c["uid"]: c for c in plan["cases"]}
    assert len(cases) == 48 and all(not c["independent_confirmation"] for c in cases.values())
    wires = {j["unit"]["root_id"]: j["request"] for j in plan["generation"].values()
             if j["unit"]["method"] == GATE and j["unit"]["replicate"] == 0}
    previous = BASE / "bench_fixed_gate_actor_v1"
    panel = read(previous / "PANEL.json")
    hard = sorted({r["profile"] for r in panel["targets"]})
    profiles = sorted({c["analysis_group_id"] for c in cases.values()})
    assert len(hard) == 2 and len(profiles) == 10
    order = sorted(set(profiles) - set(hard), key=sha)
    folds = {p: i % 2 for i, p in enumerate(hard + order)}
    seeds = [r for r in read(previous / "private/DRAW0.json")["rows"] if r["model"] == "qwen3.8-flash" and r["score"]]
    jobs = {}
    for fold in range(2):
        training = sorted((r for r in seeds if folds[cases[r["uid"]]["analysis_group_id"]] != fold), key=lambda r:r["uid"])
        for arm in ARMS:
            examples = []
            for r in training:
                u, s = r["uid"], r["score"]
                assert sha(wires[u]) == r["actor"]["request_sha256"]
                metrics = {k:s[k] for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness")}
                sample = {"task": repeat.prior.base.task_for(cases[u]).query, "answer":r["actor"]["answer"], "scores":metrics}
                if arm == "behavior":
                    sample["attribute outcomes"] = s["decisions"]
                examples.append(sample)
            prompt = Proposal.prompt_renderer(dict(current_instruction_doc=SEED, dataset_with_feedback=examples))
            system = ("Design a short reusable delivery instruction for an assistant. Use no example-specific names, facts, "
                      "topics, attributes as universal defaults, quoted case text or assessment rubrics. At most 180 words.")
            jobs[str(fold),arm] = repeat.prior.text_request(system,prompt,"qwen3.8-flash",4096)
    return cases, wires, folds, jobs, plan["protocols"]["grading"]


def main(mode):
    cases, wires, folds, jobs, grading = prepare()
    fold_for = {u:folds[c["analysis_group_id"]] for u,c in cases.items()}
    frozen = {"wire_hashes":{u:sha(w) for u,w in wires.items()}, "folds":fold_for,
              "proposal_hashes":{"/".join(k):sha(w) for k,w in jobs.items()}, "grading":grading,
              "protocol":sha((HERE/"PROTOCOL.md").read_bytes()),"code":sha((HERE/"experiment.py").read_bytes())}
    print("Eligible by fold:",dict(Counter(fold_for[u] for u in wires)), "missing original wires:",len(cases)-len(wires),flush=True)
    if mode == "check": return
    OUT.mkdir(parents=True,exist_ok=True)
    probe.RUN,probe.OUT,engine.OUT = RUN,OUT,OUT
    with probe.runner_lock(RUN/"runner.lock"):
        probe.freeze(OUT/"FROZEN.json",frozen)
        ident = {"experiment_sha256":sha(frozen),"service_reference_sha256":probe.read_reference()[1]}
        ledger = []
        def stage(name, batch):
            if not batch: return {}
            engine.CAP[name] = len(batch)
            return engine.stage(name,batch,ident,True,ledger)
        changes = stage("Reflect",jobs)
        policies = {}
        for k,r in changes.items():
            if r["status"] == "OK":
                value = Proposal.output_extractor(r["answer"])["new_instruction"]
                if value and len(value.split()) <= 180:
                    policies[k] = value
        probe.freeze(OUT/"POLICIES.json",{"/".join(k):v for k,v in policies.items()})
        if mode == "propose": return
        batch = {}
        for u,w in wires.items():
            for arm in (*ARMS,"baseline"):
                k = str(fold_for[u]),arm
                if arm != "baseline" and k not in policies: continue
                wire = deepcopy(w)
                if arm != "baseline":
                    wire["messages"][0]["content"] += "\n\n" + policies[k]
                batch[u,arm]=wire
        answers=stage("Actor",batch)
        scores={}
        refs={}
        for (u,arm),r in answers.items():
            if r["status"]!="OK":continue
            ref=read(repeat.ROOT/cases[u]["evaluation_path"])
            assert repeat.digest(ref)==cases[u]["evaluation_hash"]
            refs[u]=ref
            query=repeat.prior.base.task_for(cases[u]).query
            for field,system,content in repeat.prior.score.initial_requests(repeat.ROOT,"benchpres",ref,query,r["answer"]):
                scores.setdefault(field,{})[u,arm]=repeat.prior.text_request(system,content,grading["model"],grading["stages"][field]["max_tokens"])
        raw={}
        for field,items in scores.items():
            for k,r in stage("Grade_"+field,items).items():
                if r["status"]=="OK":raw.setdefault(k,{})[field]=r["answer"]
        settled=[]
        for (u,arm),r in answers.items():
            score=None
            if set(raw.get((u,arm),{}))==set(repeat.STAGES):
                try:score=repeat.prior.score.grade(repeat.ROOT,"benchpres",refs[u],raw[u,arm])
                except (KeyError,ValueError,TypeError):pass
            settled.append(dict(uid=u,arm=arm,actor=r["status"],score=score))
        probe.freeze(OUT/"SETTLED.json",{"rows":settled,"ledger":ledger})


if __name__=="__main__":
    if sys.argv[1:] not in (["check"],["propose"],["run"]):raise SystemExit("check|propose|run")
    main(sys.argv[1])
