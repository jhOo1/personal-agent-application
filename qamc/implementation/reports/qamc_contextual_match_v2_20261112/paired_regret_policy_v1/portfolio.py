"""A benchmark-agnostic action selector and source-group-separated offline search."""
import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path

ACTIONS = ("T","H","G")
HERE = Path(__file__).resolve().parent


def feature_vector(mle, ipe, fused):
    if not len(mle)==len(ipe)==len(fused) or not mle:
        raise ValueError("Need aligned MLE, IPE and fused source rankings")
    if any(set(r)!=set("ABC") or len(r)!=3 for r in (*mle,*ipe)) or any(r not in "ABC" for r in fused):
        raise ValueError("Invalid action-estimator rank receipt")
    m,i = [r[0] for r in mle],[r[0] for r in ipe]
    n = len(m)
    return {"n":n,"has_ipe_c":"C" in i,"mle_c":m.count("C")/n,"ipe_c":i.count("C")/n,
            "mle_b":m.count("B")/n,"ipe_b":i.count("B")/n,"fused_c":fused.count("C")/n,
            "fused_b":fused.count("B")/n,
            "top_disagreement":sum(x!=y for x,y in zip(m,i,strict=True))/n,
            "both_non_a":sum(x!="A" and y!="A" for x,y in zip(m,i,strict=True))/n,
            "both_c":sum(x==y=="C" for x,y in zip(m,i,strict=True))/n,
            "ipe_c_mle_a":sum(x=="A" and y=="C" for x,y in zip(m,i,strict=True))/n}


def comparison(value,rule):
    return value<=rule["threshold"] if rule["direction"]=="le" else value>rule["threshold"]


def route(features,policy):
    """Select one action from rank receipts. No scores, benchmark metadata, or saved answers."""
    for rule in policy:
        if comparison(features[rule["feature"]],rule):
            return rule["action"]
    return "H" if features["has_ipe_c"] else "T"


def clean(row):
    return row["domain"]!="RPEval" or all(row["flags"].get(a)==[] for a in ACTIONS)


def good(row):
    return row["denom"]>0 and all(row["metrics"].get(a) is not None and row["answers"].get(a) for a in ACTIONS) and (
        row["ref"]!="PB_RUBRIC" or row["ref_metrics"] is not None)


def reference(row):
    return row["ref_metrics"] if row["ref"]=="PB_RUBRIC" else row["metrics"][row["keep"] if row["ref"]=="KEEP" else row["ref"]]


def aggregates(rows):
    total = defaultdict(Counter)
    for r in rows:
        d = r["domain"]
        total[d]["tasks"]+=1
        total[d]["denom"]+=r["denom"]
    return total


def totals(rows, action):
    result = defaultdict(Counter)
    for r in rows:
        action_id = action(r)
        metrics = reference(r) if action_id=="REF" else r["metrics"][action_id]
        result[r["domain"]].update(metrics)
    return result


def delta(score, base, ds):
    return {(d,k):score.get(d,{}).get(k,0)-v for d,ms in base.items() for k,v in ms.items()}


def hash_group(d,group):
    return hashlib.sha256(("paired-regret-policy-v1\0"+d+"\0"+group).encode()).hexdigest()


def fold_map(rows):
    groups = defaultdict(set)
    for r in rows:
        groups[r["domain"]].add(r["group"])
    return {(d,g):i%3 for d,values in groups.items() for i,g in enumerate(sorted(values,key=lambda x:hash_group(d,x)))}


def thresholds(rows):
    from numpy import quantile
    for feature in sorted(rows[0]["features"]):
        if feature=="has_ipe_c":
            continue
        values = sorted({r["features"][feature] for r in rows})
        if len(values)<2:
            continue
        for t in sorted({float(quantile(values,p,method="lower")) for p in (.25,.5,.75)}):
            for direction in ("le","gt"):
                yield {"feature":feature,"threshold":t,"direction":direction}


def fit(rows, protected):
    """Enumerate at most two overrides. Evaluate support on each effective rule leaf."""
    import numpy as np
    ds = aggregates(rows)
    if len(ds)!=3:
        return [],False,0
    groups = [(r["domain"],r["group"]) for r in rows]
    group_names = sorted(set(groups))
    gindex = np.array([group_names.index(g) for g in groups])
    names = sorted({(r["domain"],k) for r in rows for k in reference(r)})
    keyindex = {k:i for i,k in enumerate(names)}
    primary = [keyindex[d,"primary"] for d in ds]
    denominator = np.array([ds[d]["denom"] for d in ds])
    base = np.zeros((len(rows),len(names)),dtype=np.int64)
    actions = {}
    for a in ACTIONS:
        dv = np.zeros_like(base)
        for i,r in enumerate(rows):
            ref = reference(r)
            for key in ref:
                j = keyindex[r["domain"],key]
                base[i,j] = r["metrics"][r["keep"]][key]-ref[key]
                dv[i,j] = r["metrics"][a][key]-r["metrics"][r["keep"]][key]
        actions[a] = dv
    base = base.sum(axis=0)
    action_is_change = {a:np.array([a!=r["keep"] for r in rows]) for a in ACTIONS}
    primary_delta = {a:v[:,primary].sum(axis=1) for a,v in actions.items()}
    ds_per_task = np.array([ds[r["domain"]]["denom"] for r in rows])
    candidates = []
    seen=set()
    for rule in thresholds(rows):
        mask = np.array([comparison(r["features"][rule["feature"]],rule) for r in rows])
        for a in ACTIONS:
            key = a,mask.tobytes()
            if key in seen or not mask.any():
                continue
            seen.add(key)
            candidates.append(({**rule,"action":a},mask))
    qualified = []
    best = None
    best_rules = []
    count = 0

    def support(a,m):
        m = m & action_is_change[a]
        if not m.any():
            return False
        idx = gindex[m]
        group_effect = np.bincount(idx,weights=primary_delta[a][m]/ds_per_task[m],minlength=len(group_names))
        return len(np.unique(idx))>=3 and (group_effect>0).sum()>=2 and (
            group_effect.sum()-group_effect.max()>1e-12)

    def consider(rules, change):
        nonlocal count, best,best_rules
        values=base+change
        if protected and (values<0).any():
            return
        count+=1
        obj = values[primary]/denominator
        key = (float(obj.min()),float(obj.mean()),-len(rules)) if protected else (float(obj.mean()),-len(rules))
        if best is None or key>best:
            best,best_rules=key,rules

    consider([],np.zeros_like(base))
    for rule,mask in candidates:
        if not protected or support(rule["action"],mask):
            d = actions[rule["action"]][mask].sum(axis=0)
            qualified.append((rule,mask,d))
            consider([rule],d)
    for (one,one_mask,d1),(two,two_mask) in itertools.product(qualified,candidates):
        if one["action"]==two["action"] and one["feature"]==two["feature"]:
            continue
        effective = two_mask & ~one_mask
        if effective.any() and (not protected or support(two["action"],effective)):
            consider([one,two],d1+actions[two["action"]][effective].sum(axis=0))
    return best_rules,best is not None,count


def oracle(rows):
    from scipy.optimize import Bounds, LinearConstraint, milp
    import numpy as np
    out = {}
    for domain in sorted({r["domain"] for r in rows}):
        group = [r for r in rows if r["domain"]==domain]
        keys = sorted({k for r in group for k in reference(r)})
        n = len(group)
        gains = np.array([[r["metrics"][a].get(k,0)-reference(r).get(k,0) for k in keys]
                          for r in group for a in ACTIONS],dtype=float).T
        # Exactly one action per question plus non-negative aggregate deltas on protected axes.
        assignment = np.kron(np.eye(n),np.ones((1,3)))
        lhs = np.vstack((assignment,gains))
        lo = np.r_[np.ones(n),np.zeros(len(keys))]
        hi = np.r_[np.ones(n),np.full(len(keys),np.inf)]
        objective=-gains[keys.index("primary")]
        opt=milp(objective,integrality=np.ones(3*n),bounds=Bounds(np.zeros(3*n),np.ones(3*n)),
                 constraints=LinearConstraint(lhs,lo,hi),options={"time_limit":10.0})
        feasible=opt.x is not None
        out[domain]={"tasks":n,"status":int(opt.status),"feasible":feasible,
                     "primary_gain":int(round(-opt.fun)) if feasible and opt.status==0 else None}
    return out


def run(matrix):
    rows = [r for r in matrix["rows"] if good(r)]
    registry = fold_map(rows)
    policies,predictions = {},{}
    for fold in range(3):
        train = [r for r in rows if registry[r["domain"],r["group"]]!=fold and clean(r)]
        test = [r for r in rows if registry[r["domain"],r["group"]]==fold]
        p,feasible,n = fit(train,protected=True)
        q,_,plain_n = fit(train,protected=False)
        policies[fold] = {"training_tasks":len(train),"test_tasks":len(test),
                          "protected":p,"found_feasible":feasible,"feasible_count":n,
                          "plain":q,"plain_count":plain_n}
        for r in test:
            predictions[r["uid"]] = {"fold":fold,"protected":route(r["features"],p),"plain":route(r["features"],q)}
    final = {}
    for name,subset in (("common",rows),("unflagged",list(filter(clean,rows)))):
        arms={"strong_reference":lambda r:"REF","ipe_c":lambda r:r["keep"],"always_task":lambda r:"T",
              "always_rp":lambda r:"H","always_gate":lambda r:"G"}
        arms.update({m:lambda r,m=m:predictions[r["uid"]][m] for m in ("protected","plain")})
        final[name]={"assigned":aggregates(subset),"metrics":{a:totals(subset,f) for a,f in arms.items()},
                     "action_counts":{a:dict(Counter((r["domain"]+"_"+f(r)) for r in subset)) for a,f in arms.items()},
                     "constrained_oracle":oracle(subset)}
    return {"results":final,"folds":policies,"predictions":predictions,"new_requests":0,
            "coverage":dict(Counter(r["domain"] for r in matrix["rows"])),
            "protocol":"exposed-source cross-fit, not independent confirmation"}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--matrix",type=Path,default=HERE/"MATRIX.json")
    args=parser.parse_args()
    value=run(json.loads(args.matrix.read_text()))
    print(json.dumps(value,ensure_ascii=False,indent=2))
