"""Use the frozen veto and default-aware control on external development triples."""
from collections import Counter
import json

from candidates import RUN as PARENT, HERE, engine, probe
from cache_coverage import archive_paths, search
from default_control import PROMPT as CONTROL
from selection import METHODS, blind_order, serialize_task, parse_compare
from veto import PROMPT, decide
from wires import ROOT, LEGACY, key, roster, read, sha, text_request, parse_object, load_rubrics, judge_prompt
from qamc.pa.rpeval_scoring import parse_score

RUN = PARENT.with_name("single_external_veto_comparison_v1")


def evaluate():
    final = read(PARENT/"Stage3_OUTPUT.json")
    planned = read(PARENT/"FROZEN.json")["inputs"]
    refs, orders, packets, candidates = {}, {}, {}, {}
    cases = roster()[-1]
    for r in read(LEGACY/"qamc_des2gen/ALL_NINE_CASE_DETAILS.json"):
        c = r["case"]
        if c["benchmark"]!="rpeval" or key(c) not in cases or c["uid"] not in planned:
            continue
        u = c["uid"]
        refs[u] = LEGACY.parent/c["evaluation_path"]
        answers = {METHODS[0]:r["methods"]["RPR_PAPER_XBENCH"]["answer"],METHODS[1]:r["methods"]["D2G_PAPER_ADAPT"]["answer"]}
        if u in final:
            answers[METHODS[2]] = final[u]
        candidates[u] = answers
        if u not in final:
            continue
        order = orders[u] = blind_order(u)
        packets[u] = {"context":serialize_task(r["original_public_input"]),
                      "candidates":{i:answers[m] for i,m in order.items()},
                      "default_id":next(i for i,m in order.items() if m==METHODS[0])}
    assert set(planned)==set(candidates)
    RUN.mkdir(exist_ok=True,parents=True)
    engine.OUT = probe.RUN = probe.OUT = RUN
    engine.CAP = {"Choose":40,"Score":60}
    with probe.runner_lock(RUN/"runner.lock"):
        wires = {(u,m):text_request(p,pkt,"qwen3.8-flash",8192) for u,pkt in packets.items()
                 for m,p in (("V1",PROMPT),("Default",CONTROL))}
        lock = {"selector_requests":[sha(w) for w in wires.values()],"code":sha((HERE/"compare.py").read_bytes()),
                "source":sha(read(PARENT/"FROZEN.json")),"service":probe.read_reference()[1]}
        probe.freeze(RUN/"FROZEN.json",lock)
        identity={"experiment_sha256":sha(lock),"service_reference_sha256":lock["service"]}
        paths=[p for p in archive_paths() if RUN.name not in p.parts]
        ledger=[]
        def stage(name, requests):
            found=search(requests,paths)
            unique={k:list(set(filter(None,values))) for k,values in found.items()}
            missing={k:w for k,w in requests.items() if k not in found}
            replies=engine.stage(name,missing,identity,True,ledger) if missing else {}
            answers={k:r["answer"] for k,r in replies.items() if r["status"]=="OK"}
            answers.update({k:values[0] for k,values in unique.items() if len(values)==1})
            return answers
        replies=stage("Choose",wires)
        choices={}
        for u,pkt in packets.items():
            choices[u]={}
            for m in ("Default","V1"):
                cid=pkt["default_id"]
                status="MISSING_FALLBACK"
                if (u,m) in replies:
                    try:
                        if m=="V1":
                            cid,status=decide(replies[u,m],pkt)
                        else:
                            cid,status=parse_compare(replies[u,m]),"VALID"
                    except (ValueError,TypeError,KeyError):
                        status="INVALID_FALLBACK"
                choices[u][m]={"method":orders[u][cid],"status":status}
        probe.freeze(RUN/"LOCKED_CHOICES.json",choices)
        rubrics=load_rubrics(ROOT/"literature/qamc_pa_v1/RPEval/prompts/prompts_715.py")
        jobs={(u,m):text_request("Evaluate the completed answer using the supplied benchmark rubric. Return JSON.",
                                 judge_prompt(rubrics,read(refs[u]),ans,False),"qwen3.8-flash",8192)
              for u,ans_by_method in candidates.items() for m,ans in ans_by_method.items()}
        grades={}
        for k,answer in stage("Score",jobs).items():
            try:
                grades[k]=parse_score(parse_object(answer))
            except (ValueError,TypeError,KeyError):
                pass
        rows={}
        for u in planned:
            score={m:grades.get((u,m)) for m in METHODS}
            for m in ("Default","V1"):
                score[m]=score[choices.get(u,{}).get(m,{}).get("method",METHODS[0])]
            rows[u]=score
        probe.freeze(RUN/"SCORES.json",rows)
        common=[s for s in rows.values() if all(s.values())]
        summary={"allocated":len(planned),"triples":len(final),"strict_common":len(common),
                 "scores":{m:sum(s[m]["matched"] for s in common) for m in (*METHODS,"V1","Default")},
                 "choices":{m:dict(Counter(v[m]["status"] for v in choices.values())) for m in ("Default","V1")},
                 "requests":len(ledger),"statuses":dict(Counter(v["status"] for v in ledger)),
                 "reported_tokens":sum((v.get("usage") or {}).get("total_tokens",0) for v in ledger)}
        summary["severity"]={m:{k:sum(s[m]["severity"][k] for s in common) for k in ("OPB","UPB","FM")}
                             for m in (*METHODS,"V1","Default")}
        summary["paired_v1"]={}
        for m in (*METHODS,"Default"):
            diffs=[s["V1"]["matched"]-s[m]["matched"] for s in common]
            summary["paired_v1"][m]={"wins":diffs.count(1),"losses":diffs.count(-1),"ties":diffs.count(0)}
        summary["unknown_usage"]=sum((v.get("usage") or {}).get("total_tokens") is None for v in ledger)
        probe.freeze(RUN/"LEDGER.json",ledger)
        probe.freeze(RUN/"SUMMARY.json",summary)
        print(json.dumps(summary))


if __name__=="__main__":
    evaluate()
