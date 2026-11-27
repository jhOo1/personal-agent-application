"""Compare the router with all equal-frequency assignments on fixed reviewed answers."""
import json
from collections import Counter
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from settle import settle

here = Path(__file__).resolve().parent
private = here.parents[2]/"runs"/here.parent.name/here.name
original = json.loads((here/"SUMMARY.json").read_bytes())
assert settle(here.parent, private) == original
key = json.loads((private/"KEY.json").read_bytes())
review = json.loads((private/"REVIEW.json").read_bytes())
cases = sorted(key)
full = "RPR_PAPER_FULL"
observed = {k for k in cases if key[k]["ipe_c_endpoint"]==full}

def counts(enabled):
    total = Counter()
    for k in cases:
        arm = full if k in enabled else "TASK_ONLY"
        side, = (s for s,m in key[k]["mapping"].items() if m==arm)
        values = review[k][side]
        total.update(realized=values.count("REALIZED"), joint=int(all(v=="REALIZED" for v in values)),
                     conflicts=values.count("CONFLICT"))
    return total

def multiplicity(k):
    return len(review[k]["X"])

def describe(assignments):
    result = {}
    for metric, actual in counts(observed).items():
        values = Counter(counts(a)[metric] for a in assignments)
        mean = Fraction(sum(k*n for k,n in values.items()), len(assignments))
        result[metric] = dict(actual=actual, mean_fraction=str(mean), minimum=min(values),
                              maximum=max(values), equal_count=values[actual],
                              strictly_better_count=sum(n for k,n in values.items()
                                                        if (k<actual if metric=="conflicts" else k>actual)))
    return dict(assignments=len(assignments), metrics=result)

alternatives = [set(x) for x in combinations(cases,len(observed))]
same_counts = [a for a in alternatives if Counter(map(multiplicity,a))==Counter(map(multiplicity,observed))]
assert counts(observed)["realized"]==original["scores"]["IPE_C"]["REALIZED"]
assert counts(observed)["joint"]==original["scores"]["IPE_C"]["joint_C_realized"]
print(json.dumps(dict(tasks=len(cases),opened=len(observed),unrestricted=describe(alternatives),
                      matching_C_multiplicity=describe(same_counts)),sort_keys=True,indent=2))
