"""Summarize frozen panels from existing answers and native grading receipts."""
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
RUN=BASE.parents[1]/"runs"/BASE.name/Path(__file__).resolve().parent.name
def read(path):
    return json.loads(path.read_text())

def run():
    observed=read(RUN/"private/RESULTS.json")
    prior={r["uid"]:r for r in read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    cases=defaultdict(dict)
    for r in observed["rows"]:
        cases[r["uid"]][r["arm"]]=r["score"]
    groups=defaultdict(lambda:defaultdict(Counter))
    transitions=defaultdict(Counter)
    for u,arms in cases.items():
        arms["IPE-C"]=prior[u]["ipe_c"]
        panel="diagnostic" if u in {"rpeval/formal_multi_v1/explicit/132","rpeval/formal_multi_v1/explicit/057"} else "primary"
        for names in (("ordinary","scope"),("ordinary","scope","IPE-C")):
            if not all((g:=arms.get(n,{}).get("grade",{})).get("match") and all(g.get(k) is not None for k in ("OPB","UPB","FM")) for n in names):continue
            levels=["raw"]
            if all(arms[n]["flags"]==[] for n in names):levels.append("unflagged")
            for level in levels:
                key=f"{panel}/{len(names)}/{level}"
                match={}
                for name in names:
                    g=arms[name]["grade"];m=g["match"]
                    assert m["positions"]==len(prior[u]["labels"])
                    match[name]=m["matched"]
                    groups[key][name].update(tasks=1,Match=m["matched"],positions=m["positions"],**{k:g[k] for k in ("OPB","UPB","FM")})
                transitions[key]["above_all_controls"]+=int(all(match["scope"]>match[n] for n in names if n!="scope"))
                delta=match["scope"]-match["ordinary"]
                transitions[key]["win" if delta>0 else "loss" if delta<0 else "tie"]+=1
    ledger=observed["ledger"]
    return dict(tables=groups,comparisons=transitions,status=Counter(r["status"] for r in ledger),
                usage=sum((r["usage"] or {}).get("total_tokens",0) for r in ledger),
                unknown_usage=sum((r["usage"] or {}).get("total_tokens") is None for r in ledger))
if __name__=="__main__":print(json.dumps(run(),indent=2))
