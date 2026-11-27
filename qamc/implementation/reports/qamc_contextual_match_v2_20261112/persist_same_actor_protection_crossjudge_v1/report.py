"""Compare native rubric adaptations on the allocated roots, preserving missing outcomes."""
import json
from collections import Counter,defaultdict
from pathlib import Path

here=Path(__file__).resolve().parent
doc=json.loads((here.parents[2]/"runs"/here.parent.name/here.name/"private/RESULTS.json").read_text())
groups=defaultdict(list)
for row in doc["rows"]:
    groups[row["track"],row["uid"]].append(row)
def state(rows,field,utility):
    values=[r[field] for r in rows]
    assert len(values)==(1 if utility else 3)
    if any(v is not None and (v!=3 if utility else v>=3) for v in values):
        return False
    return None if None in values else True

print("# Same-Actor subset versus whole-group exposure on protection tasks\n")
print("Fixed selection and GEPA generation prompt. ROOT pass/fail/unknown and ordered pairs compare SELECTED to GROUP. Bounds assign unknown root outcomes to either extreme and are deliberately conservative.\n")
print("|Track|Judge|Selected P/F/?|Group P/F/?|Wins/losses/ties/unknown|Pass-count gap bounds|")
print("|---|---|---|---|---|---|")
changes=[]
for track in sorted({t for t,_ in groups}):
    utility=track=="beneficial_memory_usage"
    for field,label in (("g","GPT-4.1"),("q","Qwen")):
        counts=Counter()
        low=high=0
        for (t,uid),rs in groups.items():
            if t!=track:continue
            a,b=[state(rs,arm+"_"+field,utility) for arm in ("selected","group")]
            counts["a",a]+=1;counts["b",b]+=1
            pair="unknown" if None in (a,b) else ("tie" if a==b else "win" if a else "loss")
            counts[pair]+=1
            if pair in ("win","loss"):changes.append((uid,label,pair))
            low+=int(a is True)-int(b is not False)
            high+=int(a is not False)-int(b is True)
        arms=["/".join(str(counts[arm,s]) for s in (True,False,None)) for arm in ("a","b")]
        pairs="/".join(str(counts[p]) for p in ("win","loss","tie","unknown"))
        print("|"+"|".join([track,label,*arms,pairs,f"[{low:+d}, {high:+d}]"])+"|")
print("\nKnown non-tied outcomes (source, grader, selected relative to group):\n")
for change in changes:print("- "+", ".join(change))
if not changes:print("None.")
ledger=doc["ledger"]
print(f"\n{len(ledger)} new Judge requests, {dict(Counter(r['status'] for r in ledger))}, {sum((r['usage'] or {}).get('total_tokens',0) for r in ledger)} reported tokens, {sum((r['usage'] or {}).get('total_tokens') is None for r in ledger)} unknown usage. Zero new Actor requests. No official Kimi scores.")
