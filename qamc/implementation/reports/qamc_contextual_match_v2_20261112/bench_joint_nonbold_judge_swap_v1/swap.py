"""Hold all saved Qwen components fixed except applicable non-bold reflection."""
from collections import Counter,defaultdict
from statistics import mean
from headroom_dual import PRIVATE, ROOT, run, inventory, archive_references, sample, token, BOLD

plan=run.read(ROOT/"PLAN_PRIVATE.json")
assert (ROOT/"TERMINAL").is_file()
labels={k:int(v=="yes") for k,v in plan["cached"].items()}
for job in plan["units"]:
    r,v=sample.receipt(job,ROOT)
    if v in ("yes","no"):
        assert r["reference_config_sha256"]==plan["service_sha256"]
        labels[r["request_sha256"]]=int(v=="yes")
slots={r["pair"]:r for r in plan["slots"]}
seed=bytes.fromhex((PRIVATE/"SEED_PRIVATE").read_text())
draws,_=inventory()
refs=archive_references()
index={(r["uid"],r["draw"],r["method"]):r for r in draws}
pairs=sorted({(u,n) for u,n,_ in index})
table=[]
for u,n in pairs:
    profile=index[u,n,run.GATE]["profile_group"]
    common=True
    changed_fields=0
    points=[]
    has_nonbold=any(allowed and not BOLD.search(a) for a,allowed in refs[u])
    for method in (run.GATE,run.PAPER):
        r=index[u,n,method]
        if not r["old_strict_score"]:
            common=False
            break
        attrs=r["attributes"]
        assert [(a["attribute"],a["appropriate"]) for a in attrs]==refs[u]
        ordinary=[]
        alternate=[]
        for i,a in enumerate(attrs):
            allowed=a["appropriate"]
            old=a["follow"]
            assert old in (0,1)
            new=old
            if allowed and not BOLD.search(a["attribute"]):
                key=token(seed,"census-slot",u,n,i)[:24]
                entry=slots[key]["arms"][method]
                assert entry["original"]==old
                new=labels.get(entry["request_sha256"])
                if new is None:
                    common=False
                    break
                changed_fields+=int(new!=old)
            ordinary.append(old==allowed)
            alternate.append(new==allowed)
        if not common: break
        points.extend([int(r["old_completeness"]==5 and all(values)) for values in (ordinary,alternate)])
    if common:
        table.append((u,n,profile,has_nonbold,changed_fields,*points))
print("# Same-answer joint pass after replacing applicable non-bold verdicts\n")
print(f"Allocated {len(pairs)} task/draw pairs; {len(table)} have all required observations for both methods and both scoring procedures.\n")
print("|Scope|Pairs|Tasks|Profiles|Gate original/hybrid|Selectivity original/hybrid|Equal-profile net gap original/hybrid (pp)|\n|---|---:|---:|---:|---:|---:|---:|")
for name,rows in (("All complete",table),("Applicable non-bold present",[r for r in table if r[3]]),("No applicable non-bold",[r for r in table if not r[3]])):
    by=defaultdict(list)
    for r in rows:by[r[2]].append(r)
    totals=[sum(r[i] for r in rows) for i in range(5,9)]
    gaps=[100*mean(mean(r[i]-r[i+2] for r in rs) for rs in by.values()) for i in (5,6)]
    print(f"|{name}|{len(rows)}|{len(set(r[0] for r in rows))}|{len(by)}|{totals[0]}/{totals[1]}|{totals[2]}/{totals[3]}|{gaps[0]:+.1f}/{gaps[1]:+.1f}|")
print("\n|Method|Joint fail to pass|Pass to fail|No change|\n|---|---:|---:|---:|")
for name,i in (("Gate",5),("Selectivity",7)):
    deltas=Counter(r[i+1]-r[i] for r in table)
    print(f"|{name}|{deltas[1]}|{deltas[-1]}|{deltas[0]}|")

def known_hybrid(u,n,method):
    r=index[u,n,method]
    if not r["old_strict_score"]: return None
    if r["old_completeness"]!=5: return 0
    unknown=False
    for i,(attr,allowed) in enumerate(refs[u]):
        record=r["attributes"][i]
        assert (record["attribute"],record["appropriate"])==(attr,allowed)
        if allowed and not BOLD.search(attr):
            slot=slots[token(seed,"census-slot",u,n,i)[:24]]
            value=labels.get(slot["arms"][method]["request_sha256"])
        else:
            value=record["follow"]
        if value is None: unknown=True
        elif value!=allowed: return 0
    return None if unknown else 1

lower=upper=0
seen=Counter()
for u,n in pairs:
    x,y=(known_hybrid(u,n,m) for m in (run.GATE,run.PAPER))
    seen["Gate",x]+=1
    seen["Selectivity",y]+=1
    lower+=(0 if x is None else x)-(1 if y is None else y)
    upper+=(1 if x is None else x)-(0 if y is None else y)
print("\n## Full-allocation bounds for the hybrid endpoint\n")
for m in ("Gate","Selectivity"):
    print(f"- {m}: {seen[m,1]} pass, {seen[m,0]} fail, {seen[m,None]} unknown.")
print(f"- Gate minus Selectivity, all {len(pairs)} assigned draws: [{lower:+d}, {upper:+d}] net joint passes.")
