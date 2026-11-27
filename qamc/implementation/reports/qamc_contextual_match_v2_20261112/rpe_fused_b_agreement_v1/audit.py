"""Count independently indexed author labels within each frozen fused-B vote pair."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from hashlib import sha256
p=Path(__file__).resolve().parent.parent
rank_path=p/"rpeval_formal_multi_coverage_v1/RPR_RANK_FUSION_AUDIT_300.json"
ranks=json.loads(rank_path.read_text())
ranks_by_uid={r["uid"]:r for r in ranks["rows"]}
assert len(ranks_by_uid)==len(ranks["rows"])
scores=json.loads((p/"ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]
score_by_uid={r["uid"]:r for r in scores}
tab=defaultdict(lambda:defaultdict(Counter));counts=Counter()
for uid,r in ranks_by_uid.items():
    policy=r["policies"]; f=policy["PAPER_FUSION"]; assert f["archived_actor_wire_unchanged"]
    s=score_by_uid[uid];labels=r["author_labels"]
    assert s["labels"]==labels
    cats=["all","all_A" if set(labels)=={"A"} else "has_C" if "C" in labels else "soft"]
    if any(p=="C" for p in policy["IPE_ONLY"]["policy"]):cats.append("IPE_on")
    else:cats.append("IPE_off")
    for cat in cats:counts[cat]+=1
    for gold,actual,m,i in zip(labels,f["policy"],policy["MLE_ONLY"]["policy"],policy["IPE_ONLY"]["policy"],strict=True):
        if actual!="B":continue
        for cat in cats:tab[cat][m+i][gold]+=1
print("# Can two agreeing estimates identify safe supporting preferences?\n")
print(f"Frozen rank audit: {len(ranks_by_uid)} of {ranks['allocated_roots']} allocated tasks. Source SHA256: {sha256(rank_path.read_bytes()).hexdigest()}. Counts are memory positions among fused B only. Order of the two votes: MLE, IPE. Both derive from the same model.\n")
print("|Slice|Tasks|Estimator agreement|Author A|Author B|Author C|")
print("|---|---:|---|---:|---:|---:|")
for cat,t in tab.items():
    for name in ("Both B","Other"):
        c=sum((v for k,v in t.items() if (k=="BB")==(name=="Both B")),Counter())
        print(f"|{cat}|{counts[cat]}|{name}|{c['A']}|{c['B']}|{c['C']}|")
print("\n## Individual vote pairs over the full audit\n\n|Pair|Author A|Author B|Author C|\n|---|---:|---:|---:|")
for pair,c in sorted(tab["all"].items()):print(f"|{pair}|{c['A']}|{c['B']}|{c['C']}|")
print("\nNo answer generated or rescored. Demoting an author-C item already labeled B would further reduce its allowed strength. Counts cannot establish the effect on final answers.")

prior=p/"asymmetric_preference_fusion_rpeval_v1"
settled=json.loads((prior/"SETTLED.json").read_text())
requests=json.loads((prior/"FROZEN.json").read_text())["requests"]
arms=("ORIGINAL_FUSION","CONTEXT_FIRST_FUSION")
sums=[Counter(),Counter()]; stats=Counter(); changes=Counter(); paired_groups=set(); comparisons=[]
for item in settled["rows"]:
    uid=item["uid"]; policy=ranks_by_uid[uid]["policies"]
    f,m,i=(policy[k]["policy"] for k in ("PAPER_FUSION","MLE_ONLY","IPE_ONLY"))
    proposed="".join("A" if before=="B" and {x,y}=={"A","B"} else before for before,x,y in zip(f,m,i,strict=True))
    assert "".join(v["policy"] for v in item["old_policy"])==f
    if proposed==f:continue
    stats["affected"]+=1
    if uid not in requests or proposed!="".join(v["policy"] for v in item["new_policy"]):continue
    stats["exact_policy_pair"]+=1
    for a in arms:assert requests[uid][a]==item["actor"][a]["request_sha256"]
    cells=[item["native"][a]["fields"] or {} for a in arms]
    if not all(v.get("match") and all(isinstance(v.get(k),int) for k in ("OPB","UPB","FM")) for v in cells):continue
    stats["valid"]+=1;paired_groups.add(item["group"])
    for total,v in zip(sums,cells):
        total.update(v["match"]);total.update({k:v[k] for k in ("OPB","UPB","FM")})
    diff=cells[1]["match"]["matched"]-cells[0]["match"]["matched"]
    comparisons.append((uid,diff,cells[1]["match"]["matched"],cells[0]["match"]["matched"]))
    changes["win" if diff>0 else "loss" if diff<0 else "tie"]+=1
print("\n## Existing final-answer intervention\n")
print(f"Among {len(settled['rows'])} previously assigned tasks, narrowing only fused B with exactly one A vote changes {stats['affected']}. The previous context-first experiment produces precisely this policy change on {stats['exact_policy_pair']} of those tasks. There are {stats['valid']} common valid score pairs from {len(paired_groups)} conservative groups. All remaining affected tasks are outside this exact-pair comparison.")
for name,c in zip(arms,sums):print(f"\n{name}: Match {c['matched']}/{c['positions']}, OPB {c['OPB']}, UPB {c['UPB']}, FM {c['FM']}.")
print("\nPaired Match outcomes:",dict(changes))
print("\nThis is a post-hoc exact-policy intersection of archived contemporaneous Actor draws. Reusing the archived score on an unchanged request does not imply scores are deterministic. No causal attribution for individual behaviors or independent confirmation.")

print("\n## Check against frozen IPE-C and the previous RP draw\n")
for name in ("IPE_C","RPR_PAPER_FULL"):
    common=[(u,a,b,score_by_uid[u]["scores"][name]["grade"]["match"]) for u,_,a,b in comparisons if (score_by_uid[u]["scores"][name]["grade"] or {}).get("match")]
    print(f"{name}, {len(common)} tasks: candidate {sum(x[1] for x in common)}, contemporary original {sum(x[2] for x in common)}, archived comparator {sum(x[3]['matched'] for x in common)} of {sum(x[3]['positions'] for x in common)}.")
print("\nThe observed wins occurred on", ", ".join(u.split("/")[-2]+"/"+u.split("/")[-1] for u,d,_,_ in comparisons if d>0), ".")
print("\n## Apply the change only when IPE-C actually opens history\n")
mixed=Counter()
for u,_,candidate,base_draw in comparisons:
    row=score_by_uid[u]
    grade=row["scores"]["IPE_C"]["grade"] or {}
    if not grade.get("match"):continue
    incumbent=grade["match"]["matched"]
    opens="C" in ranks_by_uid[u]["policies"]["IPE_ONLY"]["policy"]
    mixed.update(tasks=1,open=int(opens),positions=grade["match"]["positions"],original=incumbent,
                 variant=(candidate if opens else incumbent),control=(base_draw if opens else incumbent))
print(f"Exact-pair subset only: {mixed['open']} of {mixed['tasks']} open. Archived IPE-C {mixed['original']}, same-route contemporary original {mixed['control']}, same-route narrow veto {mixed['variant']} of {mixed['positions']}. Closed branches reuse their exact old answer.")
