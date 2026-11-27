"""Compare fixed full methods and the hindsight protected envelope on the 92-root roster."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from baselines import archive
from qamc.common import sha
from qamc_rpeval_terminal_judge_sensitivity import inspect

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"archived_pool_frontier_v1"))
from frontier import audit,measure,aligned,PROTECT,PRIMARY,read


def candidates(refs):
    names=(archive.engine.GATE,archive.engine.RP,"MEMADAPTER_FULL","DES2GEN_FULL")
    labels={r["uid"]:r["labels"] for r in read(HERE.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    for r in read(archive.v41.formal.OUT/"RESULT_ROWS.json"):
        if r["uid"] in refs and r["method"] in names and r["actor_status"]=="OK" and r.get("raw_scores",{}).get(archive.v41.NATIVE):
            assert sha(r["actor_request"])==r["actor_request_sha256"]
            yield r["uid"],r["method"],r["answer"],r["native_fields"],(inspect(r,labels[r["uid"]]) or {}).get("flags",[])
    for b,names in (("BenchPreS",(*names,"PAPER_SELECTIVITY")),("PersistBench",(archive.engine.GATE,archive.engine.RP,"PB_RUBRIC","PB_GEPA","PB_NO_MEMORY"))):
        cases,protocol,rows=archive.transfer.context(b)
        cases={u:v for u,v in cases.items() if u in refs and refs[u]["benchmark"]==b}
        saved=archive.transfer.archived_answers(b,cases)
        receipts,_=archive.transfer.matching_grading_receipts(b,cases,protocol,saved)
        scores={(r["uid"],r["method"]):r["score"] for r in rows if r["uid"] in cases and r.get("score")}
        for r in saved:
            k=r["uid"],r["method"]
            if k not in scores or k[1] not in names or r["actor_status"]!="OK":
                continue
            wires,_=archive.transfer.grading_jobs(b,[r],cases,protocol)
            if wires and all(sha(w) in receipts for w in wires.values()):
                yield *k,r["answer"],scores[k],[]


def replay():
    refs={r["uid"]:r for r in read(HERE.parent/"transactional_reassembly_v1/FROZEN.json")["rows"]}
    old=audit()[1]; methods=defaultdict(Counter); opportunities=defaultdict(dict); seen={}
    clean=defaultdict(dict)
    for u,m,a,s,flags in candidates(refs):
        r=refs[u];b=r["benchmark"];key=(u,m)
        if key in seen:
            assert seen[key]==(sha(a),s)
            continue
        seen[key]=(sha(a),s)
        base,alt=(measure(b,r["stratum"],v) for v in (r["base_score"],s))
        if not aligned({"base":base,"alt":alt},("base","alt")):continue
        total=methods[b+"/"+m]
        if sha(a)==r["baseline_answer_sha256"] and base!=alt:
            total["identical_answer_score_conflict"]+=1
            continue
        k=PRIMARY[b];gain=alt[k]-base[k]
        total["common"]+=1;total["primary_difference"]+=gain;total["incumbent"]+=base[k];total["alternative"]+=alt[k]
        total["units"]+=base["positions"]
        total["wins" if gain>0 else "losses" if gain<0 else "ties"]+=1
        protected=all(sign*(alt[p]-base[p])>=0 for p,sign in PROTECT[b])
        if protected and gain>0:
            opportunities[u][m]=gain
            if not flags and not r.get("base_flags"):clean[u][m]=gain
    summary={}
    for b in PROTECT:
        roots=[u for u in refs if refs[u]["benchmark"]==b]
        gain={u:max(opportunities[u].values(),default=0) for u in roots}
        added={u:max(0,v-old[u]["protected_gain"]) for u,v in gain.items()}
        summary[b]={"assigned":len(roots),"external_oracle_gain":sum(gain.values()),
                    "unflagged_external_gain":sum(max(clean[u].values(),default=0) for u in roots),
                    "unflagged_winning_groups":len({refs[u]["group"] for u in roots if clean[u]}),
                    "external_winning_groups":len({refs[u]["group"] for u in roots if gain[u]}),
                    "combined_gain_beyond_revision_oracle":sum(added.values()),
                    "additional_gain_groups":len({refs[u]["group"] for u in roots if added[u]})}
    return {"fixed_methods":methods,"protected_envelope":summary}, opportunities


if __name__=="__main__":print(json.dumps(replay()[1 if "--cases" in sys.argv else 0],indent=2,sort_keys=True))
