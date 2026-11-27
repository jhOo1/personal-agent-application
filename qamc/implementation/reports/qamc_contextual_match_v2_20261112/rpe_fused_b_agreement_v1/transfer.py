"""Transfer the unchanged fused-B disagreement veto to two exposed archives."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
from qamc.common import sha
from qamc.pa.core import digest
import transfer_edit as t

base=Path(__file__).resolve().parent.parent
def norm(x):return " ".join(x.casefold().split()).rstrip(".")
for bench in ("BenchPreS","PersistBench"):
    cases,protocol,_=t.context(bench)
    roots={r["uid"]:r for r in t.development_roots(bench)}
    assert roots.keys()==cases.keys()
    previous=t.read(base/"asymmetric_preference_fusion_transfer_v1"/bench/"SETTLED.json")
    receipts={(x["uid"],x["method"]):x for x in previous["rows"]}
    rows={r["uid"]:r for r in t.archived_answers(bench,cases) if r["method"]==t.RP and r.get("actor_request") and sha(r["actor_request"])==roots[r["uid"]]["archived_actor_sha256"]}
    assert rows.keys()==cases.keys()
    stats=Counter(); grades=defaultdict(lambda:[Counter(),Counter()]); profiles=Counter(); applicable=Counter()
    for uid,r in rows.items():
        w=deepcopy(r["actor_request"])
        packet=json.loads(w["messages"][1]["content"])
        before=packet["preference_use_policy"]
        ranks=r["aggregation"];sources=packet["source_evidence"]
        assert [(x["memory_id"],x["policy"]) for x in ranks]==[(x["memory_id"],x["policy"]) for x in before]
        assert [s["memory_id"] for s in sources]==[s["memory_id"] for s in before]
        hits=[i for i,x in enumerate(ranks) if x["policy"]=="B" and {x["mle_order"][0],x["ipe_order"][0]}=={"A","B"}]
        cat=cases[uid].get("category","all")
        stats["tasks"]+=1;stats["changed_tasks"]+=bool(hits);stats["veto_positions"]+=len(hits)
        if hits:stats["changed/"+cat]+=1
        if bench=="BenchPreS":
            case=cases[uid];ev=t.read(t.bench.ROOT/case["evaluation_path"])
            assert digest(ev)==case["evaluation_hash"]
            texts=[norm(s["text"]) for s in sources]
            matched=set()
            for attr,yes in zip(ev["preference_attribute"],ev["preference_label"],strict=True):
                assert type(yes)==bool
                pos,=[i for i,v in enumerate(texts) if v==norm(attr)]
                if pos in hits:
                    matched.add(pos);stats["veto_applicable" if yes else "veto_inapplicable"]+=1
                    profiles["applicable/"+case["analysis_group_id"]]+=int(yes)
                    if yes:applicable["bold emphasis" if "bold text" in attr.casefold() else "other applicable expression"]+=1
            stats["veto_unlabeled"]+=len(set(hits)-matched)
        if not hits:continue
        for pos in hits:before[pos]["policy"]="A"
        w["messages"][1]["content"]=json.dumps(packet,ensure_ascii=False)
        left=receipts.get((uid,"ORIGINAL_FUSION"));right=receipts.get((uid,"CONTEXT_FIRST_FUSION"))
        if not left or not right or sha(w)!=right["actor_request_hash"]:continue
        assert sha(r["actor_request"])==left["actor_request_hash"]
        stats["exact_changed_pairs"]+=1
        if not all(x["score"] for x in (left,right)):continue
        stats["graded_changed_pairs"]+=1
        for dst,x in zip(grades[cat],(left,right)):
            s=x["score"];dst["n"]+=1
            if bench=="BenchPreS":
                for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness"):dst[k]+=s[k]
            else:
                for k in ("failure_release","failure_strict_utility"):
                    if s.get(k) is not None:dst[k]+=int(s[k]);dst[k+"_n"]+=1
    print(f"## {bench}\n\nDeployed veto formula applied to {stats['tasks']} exposed tasks. Existing changed-answer pairs were sought only in the settled asymmetric-fusion run. Score model: {protocol['model']}.\n")
    print(dict(sorted(stats.items())))
    if bench=="BenchPreS":print("\nSource groups with at least one labeled applicable preference vetoed:",sum(v>0 for v in profiles.values()))
    if applicable:print("\nApplicable preference types vetoed:",dict(applicable))
    print("\nMatched answer totals, original then veto:",json.dumps(grades,sort_keys=True),"\n")
