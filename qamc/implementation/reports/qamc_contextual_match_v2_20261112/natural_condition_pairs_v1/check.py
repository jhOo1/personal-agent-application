"""Find existing one-source RP contrasts with identical background Actor inputs."""
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
def key(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

def single_change(left, right):
    if len(left) == len(right):
        diff = [i for i, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]
        return ("replace", diff[0]) if len(diff) == 1 else None
    short, long = sorted((left, right), key=len)
    if len(long) == len(short) + 1:
        for i in range(len(long)):
            if short == long[:i] + long[i+1:]:
                return "insert", i
    return None

def main():
    rows = json.loads((BASE / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json").read_text())
    groups = defaultdict(list)
    for row in rows:
        if row["method"] != "RPR_PAPER_FULL" or row["actor_status"] != "OK":
            continue
        wire = dict(row["actor_request"])
        system, user = wire.pop("messages")
        body = json.loads(user["content"])
        sources = body.pop("source_evidence")
        policy = body.pop("preference_use_policy")
        assert [p["memory_id"] for p in policy] == [s["memory_id"] for s in sources]
        groups[key([wire, system, user["role"], body])].append((row["uid"], sources, policy))
    counts = Counter()
    kinds = defaultdict(set)
    print("Available answers / task payload groups", sum(map(len,groups.values())), len(groups))
    for group, variants in groups.items():
        for (a,x,p),(b,y,q) in combinations(variants,2):
            counts["same background"] += 1
            texts_x = Counter(s["text"] for s in x)
            texts_y = Counter(s["text"] for s in y)
            removed, added = texts_x - texts_y, texts_y - texts_x
            edit = (sum(removed.values()), sum(added.values()))
            if edit in {(1,0),(0,1),(1,1)}:
                counts["one unordered text edit"] += 1
                sx = Counter((src["text"], pol["policy"]) for src,pol in zip(x,p))
                sy = Counter((src["text"], pol["policy"]) for src,pol in zip(y,q))
                policy_edit = (sum((sx-sy).values()), sum((sy-sx).values()))
                if policy_edit == edit:
                    counts["unordered with aligned policies"] += 1
                    kinds.setdefault(("unordered",group),set()).add((a,b))
                    print("aligned unordered",a,b,edit,[(pol,n) for (_,pol),n in (sx-sy).items()],
                          [(pol,n) for (_,pol),n in (sy-sx).items()])
            if edit == (0,0):
                counts["identical source text multiset"] += 1
            changes = single_change(x,y)
            if not changes:
                continue
            op,i = changes
            counts[op] += 1
            if op == "replace":
                stable = p[:i]+p[i+1:] == q[:i]+q[i+1:]
            else:
                short,long = sorted((p,q),key=len)
                stable = short == long[:i]+long[i+1:]
            if stable:
                counts["stable remaining policies"] += 1
                kinds[group].add((a,b))
                print("matched",a,b,op,i,p[i] if i<len(p) else None,q[i] if i<len(q) else None)
    print("counts",dict(counts),"matched background groups",sum(isinstance(k,str) for k in kinds), "unordered aligned groups",sum(isinstance(k,tuple) for k in kinds))
if __name__ == "__main__":
    main()
