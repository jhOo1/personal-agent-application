"""Bind saved actions and scores before fitting any portfolio policy."""
from collections import Counter
import json
from pathlib import Path

import collect_interventions as archived
from qamc.common import sha
from qamc_rpeval_terminal_judge_sensitivity import inspect
from portfolio import feature_vector

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
MEM, GATE = archived.engine.RP, archived.engine.GATE
BENCH_ZERO, PERSIST_ZERO = "TASK_ONLY","PB_NO_MEMORY"


def rpe_metrics(score, stratum):
    names = ("match","OPB","UPB","FM")
    if not score or any(k not in score for k in names):
        return None
    value = score["match"]["matched"]
    return {"primary":value,"OPB":-score["OPB"],"UPB":-score["UPB"],"FM":-score["FM"],stratum:value}


def bench_metrics(score):
    names = ("aar_numerator","mr_numerator","task_completeness","decisions")
    if not score or any(k not in score for k in names):
        return None
    nonbold = sum(d["appropriate"] and d["label"]=="follow" and "bold text" not in d["preference"].lower()
                  for d in score["decisions"])
    return {"primary":score["aar_numerator"],"MR":-score["mr_numerator"],
            "completeness":score["task_completeness"],"nonbold":nonbold}


def persist_metrics(score, category):
    if not score or any(type(score.get(k)) is not bool for k in ("failure_release","failure_strict_utility")):
        return None
    release,strict = (1-int(score[k]) for k in ("failure_release","failure_strict_utility"))
    return {"primary":release,category:release,category+"_strict":strict}


def observable(rank):
    if not rank or any(not all(k in r for k in ("memory_id","mle_order","ipe_order","policy")) for r in rank):
        return None
    return feature_vector([r["mle_order"] for r in rank],[r["ipe_order"] for r in rank],
                          [r["policy"] for r in rank])


def observe_archived(rows, roots=None):
    index = {}
    for row in rows:
        if row["method"] not in (GATE,MEM) or row["actor_status"]!="OK" or not row.get("actor_request"):
            continue
        digest = sha(row["actor_request"])
        if digest!=row["actor_request_sha256"]:
            raise ValueError("Saved action wire hash changed")
        uid = row["uid"]
        if roots is not None and row["method"]==MEM and digest!=roots[uid]["archived_actor_sha256"]:
            raise ValueError("RP receipt does not match the exposed root")
        if (uid,row["method"]) in index:
            raise ValueError("Ambiguous answer action")
        index[uid,row["method"]] = row
    return index


def rpe_rows():
    data = archived.read(BASE/"ipe_c_two_endpoint_completion_v1"/"RESULTS.json")["rows"]
    previous = observe_archived(archived.read(archived.v41.formal.OUT/"RESULT_ROWS.json"))
    result = []
    for row in data:
        uid, labels = row["uid"], row["labels"]
        if not labels:
            continue
        s = "all_A" if set(labels)=={"A"} else "contains_C" if "C" in labels else "B_only"
        old = previous.get((uid,MEM),{})
        f = observable(old.get("aggregation"))
        if f is None:
            continue
        scores = row["scores"]
        t,h = scores.get("TASK_ONLY") or {},scores.get(MEM) or {}
        if h.get("answer_sha256") is not None and h["answer_sha256"]!=sha(old["answer"]):
            raise ValueError("RP answer differs from endpoint result")
        g = previous.get((uid,GATE),{})
        g_score = (g.get("native_fields") or {})
        g_reason = (g.get("raw_scores") or {}).get(archived.v41.NATIVE)
        g_flags = inspect(g,labels)["flags"] if g_score.get("match") and g_reason else None
        main = scores.get("IPE_C") or {}
        keep = "H" if f["has_ipe_c"] else "T"
        expected = h if keep=="H" else t
        if main.get("answer_sha256") is not None and main["answer_sha256"]!=expected.get("answer_sha256"):
            raise ValueError("Frozen IPE-C route differs from estimator features")
        if any((e.get("grade") or {}).get("match",{}).get("positions",len(labels))!=len(labels) for e in (t,h)):
            raise ValueError("RPEval positions changed")
        result.append({"domain":"RPEval","uid":uid,"group":row["source_group"],"stratum":s,
                       "features":f,"keep":keep,"ref":"KEEP","denom":len(labels),
                       "metrics":{"T":rpe_metrics(t.get("grade"),s),"H":rpe_metrics(h.get("grade"),s),"G":rpe_metrics(g_score,s)},
                       "flags":{"T":t.get("flags"),"H":h.get("flags"),"G":g_flags},
                       "answers":{"T":t.get("answer_sha256"),"H":h.get("answer_sha256"),"G":sha(g["answer"]) if g else None}})
    return result


def transfer_rows(benchmark):
    cases,protocol,score_rows = archived.transfer.context(benchmark)
    roots = {row["uid"]:row for row in archived.transfer.development_roots(benchmark)}
    source = archived.transfer.archived_answers(benchmark,cases)
    answers = observe_archived(source,roots)
    scores = {}
    for r in score_rows:
        key = r["uid"],r["method"]
        if key in scores and scores[key]!=r["score"]:
            raise ValueError("Inconsistent duplicate score")
        scores[key] = r["score"]
    if benchmark=="BenchPreS":
        zero = archived.read(BASE/"guarded_answer_switch_rpeval_v1"/"BenchPreS"/"SETTLED.json")["rows"]
        zero = {r["uid"]:r for r in zero if r["method"]==BENCH_ZERO and r["actor_status"]=="OK"}
        expected = archived.transfer.draft_wires([roots[uid] for uid in zero])
        for uid,row in zero.items():
            if sha(expected[uid,BENCH_ZERO,archived.transfer.DRAFT])!=row["draft_request_sha256"]:
                raise ValueError("BenchPreS task-only receipt lineage mismatch")
        empty_alias = BENCH_ZERO
    else:
        from effect_scope_transfer import persist_drafts
        zero = persist_drafts(list(roots.values()),source)
        empty_alias = PERSIST_ZERO
        drafts = [{"uid":uid,"method":empty_alias,"actor_status":"OK","answer":row["answer"]}
                  for uid,row in zero.items()]
        wires,_ = archived.transfer.grading_jobs(benchmark,drafts,cases,protocol)
        exact,conflicts = archived.transfer.matching_grading_receipts(benchmark,cases,protocol,source)
        retained = {uid for (uid,_,_),wire in wires.items() if sha(wire) in exact and sha(wire) not in conflicts}
        zero = {uid:row for uid,row in zero.items() if uid in retained}
    result = []
    for uid,case in cases.items():
        h,g = (answers.get((uid,alias),{}) for alias in (MEM,GATE))
        if (f:=observable(h.get("aggregation"))) is None:
            continue
        t = zero.get(uid,{})
        if benchmark=="BenchPreS":
            stratum = "communication"
            group = case["analysis_group_id"]
            if not group.startswith("benchpres/profile/"):
                raise ValueError("BenchPreS must be grouped by profile across exports")
            scores_for_actions = (t.get("score"),scores.get((uid,MEM)) if h else None,
                                  scores.get((uid,GATE)) if g else None)
            profile_shapes = {tuple((d["preference"],d["appropriate"]) for d in score["decisions"])
                              for score in scores_for_actions if score is not None}
            if len(profile_shapes)>1:
                raise ValueError("BenchPreS paired scores use different attributes")
            qualified = {a:bench_metrics(score) for a,score in (
                ("T",t.get("score")),("H",scores.get((uid,MEM)) if h else None),("G",scores.get((uid,GATE)) if g else None))}
            ref,ref_metrics = "G",None
            denom = next((scores[uid,a]["aar_denominator"] for a in (GATE,MEM)
                          if scores.get((uid,a))),0)
        else:
            stratum,group = case["category"],case["group_id"]
            qualified = {a:persist_metrics(score,stratum) for a,score in (
                ("T",scores.get((uid,empty_alias)) if t else None),("H",scores.get((uid,MEM)) if h else None),
                ("G",scores.get((uid,GATE)) if g else None))}
            ref,ref_metrics = "PB_RUBRIC",persist_metrics(scores.get((uid,"PB_RUBRIC")),stratum)
            denom = 1
        result.append({"domain":benchmark,"uid":uid,"group":group,"stratum":stratum,"features":f,
                       "keep":"H" if f["has_ipe_c"] else "T","ref":ref,"ref_metrics":ref_metrics,"denom":denom,
                       "metrics":qualified,"flags":{},
                       "answers":{a:sha(r["answer"]) if r else None for a,r in (("T",t),("H",h),("G",g))}})
    return result


def build():
    rows = rpe_rows()+transfer_rows("BenchPreS")+transfer_rows("PersistBench")
    coverage = Counter((r["domain"],"complete" if all(r["metrics"].values()) and (r["ref"]!="PB_RUBRIC" or r["ref_metrics"])
                        else "missing") for r in rows)
    print(dict(coverage))
    data = {"exposed_only":True,"estimated_new_requests":0,"rows":rows}
    archived.probe.freeze(HERE/"MATRIX.json",data)


if __name__=="__main__":
    build()
