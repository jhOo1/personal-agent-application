"""Bound the opportunity in two pre-existing development answer pools, by task."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0,str(BASE / "transactional_reassembly_v1"))
from summarize_reassembly import measure, aligned

POOLS = ("transactional_reassembly_v1", "archive_edit_opportunity_v1")
PROTECT = {"RPEval":(("OPB",-1),("UPB",-1),("FM",-1)),
           "BenchPreS":(("MR",-1),("completeness",1),("nonbold",1)),
           "PersistBench":(("primary",1),)}
PRIMARY = {"RPEval":"primary","BenchPreS":"primary","PersistBench":"strict_pass"}


def read(p):
    return json.loads(p.read_bytes())


def audit():
    tasks, bindings = {}, {}
    counts = defaultdict(Counter)
    for folder in POOLS:
        frozen=read(BASE/folder/"FROZEN.json")["rows"]
        for row in frozen:
            u=row["uid"]
            identity=(row["baseline_answer_sha256"],row["group"],row["stratum"],row["benchmark"])
            assert sha256(row["base_answer"].encode()).hexdigest()==identity[0]
            if u in bindings:
                assert identity==bindings[u] and tasks[u]["base_score"]==row["base_score"]
            else:
                bindings[u]=identity
                tasks[u]={"base_score":row["base_score"],"base_flags":row.get("base_flags"),"observed":defaultdict(list),"ungraded":set()}
        for r in read(BASE/folder/"RESULTS.json")["rows"]:
            u=r["uid"]; digest,group,stratum,b=bindings[u]
            assert group==r["group"] and b==r["benchmark"] and stratum==r["stratum"]
            counts[b]["alternative_records"]+=1
            if not r.get("answer"):
                counts[b]["missing_answers"]+=1;continue
            h=sha256(r["answer"].encode()).hexdigest()
            assert not r.get("answer_sha256") or r["answer_sha256"]==h
            s=measure(b,stratum,r.get("score"))
            if s is None:
                counts[b]["missing_grades_on_answers"]+=1
                tasks[u]["ungraded"].add(h)
                continue
            tasks[u]["observed"][h].append((s,r.get("score_flags")))
    trace={}
    for u,r in tasks.items():
        h,group,stratum,b=bindings[u]
        default=measure(b,stratum,r["base_score"])
        counts[b]["assigned"]+=1
        if not default:
            counts[b]["no_baseline_grade"]+=1;continue
        primary=PRIMARY[b]; best=protected=clean=0
        if b=="BenchPreS" and default["primary"]<default["positions"]:
            unknown=r["ungraded"]-set(r["observed"])-{h}
            counts[b]["ungraded_distinct_answers_with_AAR_headroom"]+=len(unknown)
            counts[b]["tasks_with_ungraded_answers_and_AAR_headroom"]+=bool(unknown)
        scored=0
        for key,rows in r["observed"].items():
            if key==h:
                if any(s!=default for s,_ in rows):counts[b]["same_default_text_grade_disagreements"]+=1
                continue
            if any(s!=rows[0][0] for s,_ in rows):
                counts[b]["conflicting_grades_excluded"]+=1;continue
            s=rows[0][0]
            aligned({"base":default,"alternative":s},("base","alternative"))
            scored+=1
            delta=s[primary]-default[primary]
            best=max(best,delta)
            if all(sign*(s[k]-default[k])>=0 for k,sign in PROTECT[b]):
                protected=max(protected,delta)
                if not r["base_flags"] and not any(f for _,f in rows):
                    clean=max(clean,delta)
        trace[u]={"group":group,"stratum":stratum,"benchmark":b,"scored_alternatives":scored,
                  "best_gain":best,"protected_gain":protected,"unflagged_protected_gain":clean}
        counts[b]["with_scored_distinct_alternative"]+=int(scored>0)
        for k,g in (("primary",best),("protected",protected),("unflagged_protected",clean)):
            counts[b][k+"_gain"]+=g
            counts[b][k+"_winning_tasks"]+=int(g>0)
    for b in counts:
        for k in ("best_gain","protected_gain","unflagged_protected_gain"):
            counts[b][k+"_winning_groups"]=len({v["group"] for v in trace.values() if v["benchmark"]==b and v[k]>0})
    return counts,trace


if __name__=="__main__":
    print(json.dumps(audit()[0],sort_keys=True,indent=2))
