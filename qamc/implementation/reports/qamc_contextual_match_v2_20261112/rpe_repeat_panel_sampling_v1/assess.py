"""Replay the original group exclusions and six-per-stratum selection offline."""
import hashlib
import json
import random
from pathlib import Path
from statistics import median

here=Path(__file__).resolve().parent
runs=here.parents[2]/"runs"/here.parent.name
panel=json.loads((runs/"rpe_ipe_fresh_repeat_v1/PANEL_V2.json").read_text())
inventory=json.loads((here.parent/"selective_path_frontier_v1/RESULTS.json").read_text())["rows"]
assert len(inventory)==len({r["uid"] for r in inventory})==216
excluded=set(panel["excluded_groups"])
strata=list(dict.fromkeys(c[2] for c in panel["cards"]))

def choose(ordered):
    taken=excluded.copy()
    rows=[]
    for s in strata:
        n=0
        for r in ordered:
            if r["stratum"]!=s or r["source_group"] in taken: continue
            taken.add(r["source_group"])
            rows.append(r)
            n+=1
            if n==6: break
        if n!=6: return None
    return rows

def original_key(r):
    value=["ipe-fresh-two-v1",r["source_group"],r["uid"]]
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()

def totals(rows):
    n=sum(r["positions"] for r in rows)
    routed=sum(r["cells"][r["base"]]["matched"] for r in rows)
    rp=sum(r["cells"]["RPR_PAPER_FULL"]["matched"] for r in rows)
    return n,routed,rp

original=choose(sorted(inventory,key=original_key))
assert [[r["uid"],r["source_group"],r["stratum"]] for r in original]==panel["cards"]
observed=totals(original)
assert observed==(91,39,39)
eligible=[r for r in inventory if r["source_group"] not in excluded]
print("# RPEval fresh-panel sampling sensitivity\n")
print("|Archive scope|Tasks|Groups|Positions|IPE-C|RP|\n|---|---:|---:|---:|---:|---:|")
for name,rows in (("Original inventory",inventory),("After original exclusions",eligible),("Actual repeat panel",original)):
    n,a,b=totals(rows)
    print(f"|{name}|{len(rows)}|{len(set(r['source_group'] for r in rows))}|{n}|{a}|{b}|")
rng=random.Random(154789)
records=[]
applicable_deltas=[]
dropped=0
for _ in range(10000):
    order=list(inventory)
    rng.shuffle(order)
    rows=choose(order)
    if rows is None:
        dropped+=1
        continue
    records.append(totals(rows))
    _,a,b=totals([r for r in rows if r["stratum"]!="all_A"])
    applicable_deltas.append(a-b)
print(f"\n10,000 randomized task orderings, fixed original stratum order and exclusions. Filled {len(records)}; could not fill {dropped}.")
deltas=[a-b for n,a,b in records]
rates=sorted(100*(a-b)/n for n,a,b in records)
print(f"\nStrictly negative / tied / positive archived Match differences: {sum(x<0 for x in deltas)} / {deltas.count(0)} / {sum(x>0 for x in deltas)}. Median net positions {median(deltas):g}.")
print(f"Median paired Match-rate difference {median(rates):.2f} percentage points. Empirical 5th and 95th percentiles (nearest rank): {rates[(len(rates)+19)//20-1]:.2f}, {rates[(95*len(rates)+99)//100-1]:.2f}.")
print("\n|Stratum in actual panel|Positions|IPE-C|RP|\n|---|---:|---:|---:|")
for s in strata:
    print("|"+"|".join([s,*map(str,totals([r for r in original if r["stratum"]==s]))])+"|")
print(f"\nOn the 12 applicable-stratum tasks alone, negative / tied / positive differences: {sum(x<0 for x in applicable_deltas)} / {applicable_deltas.count(0)} / {sum(x>0 for x in applicable_deltas)}. Median net positions {median(applicable_deltas):g}.")
