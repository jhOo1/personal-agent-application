"""Replay the exact existing answers under a targeted emphasis exemption."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from qamc.common import sha
from qamc.pa.core import digest
import transfer_edit as t

base=Path(__file__).resolve().parent.parent
cases,protocol,controls=t.context("BenchPreS")
roots={r["uid"]:r for r in t.development_roots("BenchPreS")}
previous=t.read(base/"asymmetric_preference_fusion_transfer_v1/BenchPreS/SETTLED.json")
record={(r["uid"],r["method"]):r for r in previous["rows"]}
archive=t.archived_answers("BenchPreS",cases)
rp={r["uid"]:r for r in archive if r["method"]==t.RP and r.get("actor_request") and sha(r["actor_request"])==roots[r["uid"]]["archived_actor_sha256"]}
gate={r["uid"]:r["score"] for r in controls if r["method"]=="GEPA_SELECTED_BOUNDS"}
assert roots.keys()==rp.keys()==cases.keys() and len(roots)==48
def policy_wire(r,exempt):
    wire=deepcopy(r["actor_request"]); packet=json.loads(wire["messages"][1]["content"])
    policies=packet["preference_use_policy"]; sources=packet["source_evidence"]; changed=[]
    for i,(x,p,s) in enumerate(zip(r["aggregation"],policies,sources,strict=True)):
        assert x["memory_id"]==p["memory_id"]==s["memory_id"] and x["policy"]==p["policy"]
        if p["policy"]!="B" or {x["mle_order"][0],x["ipe_order"][0]}!={"A","B"}:continue
        if exempt and re.search(r"\bbold text\b",s["text"],re.I):continue
        p["policy"]="A"; changed.append(i)
    if changed:wire["messages"][1]["content"]=json.dumps(packet,ensure_ascii=False)
    return sha(wire),changed
rows=[]; flags=Counter()
for u,r in rp.items():
    v,vi=policy_wire(r,False);e,ei=policy_wire(r,True)
    baseline=sha(r["actor_request"])
    frozen=record.get((u,"ORIGINAL_FUSION"));changed=record.get((u,"CONTEXT_FIRST_FUSION"))
    if frozen:assert frozen["actor_request_hash"]==baseline
    originals=frozen["score"] if frozen else r.get("score")
    def lookup(key):
        if key==baseline:return originals
        if changed and key==changed["actor_request_hash"]:return changed["score"]
        return None
    flags["all"]+=1
    flags["exemption_changes_veto"]+=v!=e
    ref=t.read(t.bench.ROOT/cases[u]["evaluation_path"])
    assert digest(ref)==cases[u]["evaluation_hash"]
    labels={" ".join(s.casefold().split()).rstrip("."):y for s,y in zip(ref["preference_attribute"],ref["preference_label"],strict=True)}
    for i in set(vi)-set(ei):
        attr=" ".join(roots[u]["original_sources"][i]["text"].casefold().split()).rstrip(".")
        flags["restored_applicable" if labels[attr] else "restored_inapplicable"]+=1
    rows.append(dict(uid=u,hit=bool(vi),difference=v!=e,rp=originals,veto=lookup(v),exempt=lookup(e),gate=gate.get(u)))
print("# BenchPreS: retaining bold emphasis when rank estimators disagree\n")
print("The policy exempts a disputed source containing the exact words 'bold text' from the previously tested veto. It reads source text only. The choice was developed after observing this panel's four applicable removals. All performance comparisons below are retrospective; both methods keep all original source texts available to the Actor.\n")
print("Action coverage:",dict(flags))
print("\n|Slice|Assigned|Common|Method|AAR|MR|Completeness sum|Fully successful tasks|\n|---|---:|---:|---|---|---|---:|---:|")
for name,subset in (("all",rows),("veto triggers",[r for r in rows if r["hit"]]),("exemption changes policy",[r for r in rows if r["difference"]])):
    for methods in (("rp","veto","exempt"),("rp","veto","exempt","gate")):
        valid=[r for r in subset if all(r[m] is not None for m in methods)]
        for m in methods:
            grades=[r[m] for r in valid]
            def total(k):return sum(g[k] for g in grades)
            joint=sum(g["aar_numerator"]==g["aar_denominator"] and g["mr_numerator"]==0 and g["task_completeness"]==5 for g in grades)
            print(f"|{name} ({len(methods)} arms)|{len(subset)}|{len(valid)}|{m}|{total('aar_numerator')}/{total('aar_denominator')}|{total('mr_numerator')}/{total('mr_denominator')}|{total('task_completeness')}|{joint}|")
print("\nContemporary original-fusion score preferred when its exact wire was dispatched; missing scores there remain missing. Otherwise the original archived RP score is reused. A changed wire needs its own exact archived receipt. Gate uses the existing project-adapted control score. All intersections are explicit. No new Actor, Judge, retries or sealed cases.")
