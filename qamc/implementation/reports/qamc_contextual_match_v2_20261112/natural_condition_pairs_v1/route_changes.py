"""Trace the original IPE-C decision on naturally nested explicit source sets."""
import json
from collections import Counter
from itertools import combinations
from check import BASE, backgrounds


def main():
    base = json.loads((BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())
    archive = {r["uid"]: r for r in base["rows"]}
    counts = Counter()
    distinct = set()
    for variants in backgrounds().values():
        for pair in combinations(variants,2):
            (left, x, p), (right, y, q) = sorted(pair,key=lambda v:len(v[1]))
            if len(y) != len(x)+1:
                continue
            old = Counter((s["text"],v["policy"]) for s,v in zip(x,p))
            new = Counter((s["text"],v["policy"]) for s,v in zip(y,q))
            if old-new:
                continue
            (text, prediction), = (new-old).elements()
            indices = [i for i,s in enumerate(y) if s["text"]==text]
            if len(indices)!=1:
                raise ValueError("Ambiguous added source")
            before, after = archive[left], archive[right]
            author = after["labels"][indices[0]]
            routes = []
            for row in (before, after):
                state = "H" if row["old_route"]=="REUSE_RP" else "T"
                assert row["ipe_c"]["answer_sha256"] == row["scores"]["RPR_PAPER_FULL" if state=="H" else "TASK_ONLY"]["answer_sha256"]
                routes.append(state)
            counts["".join(routes)] += 1
            distinct.add(right)
            def match(method):
                m = after["scores"][method]["grade"].get("match")
                return f"{m['matched']}/{m['positions']}" if m else "NA"
            print(left.split("/")[-1],right.split("/")[-1],author,prediction,"".join(routes),
                  *(match(k) for k in ("IPE_C","TASK_ONLY","RPR_PAPER_FULL")))
    print(dict(counts), "distinct augmented tasks",len(distinct))

if __name__ == "__main__":
    main()
