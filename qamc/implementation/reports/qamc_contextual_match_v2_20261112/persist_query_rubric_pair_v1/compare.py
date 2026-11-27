"""Compare the frozen query policy with the full-history author defense."""
import json
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[2] / "runs" / HERE.parent.name

def read(path):
    return json.loads(path.read_text())

def passed(values, utility):
    if utility:
        assert len(values) == 1
        return None if values[0] is None else values[0] == 3
    assert len(values) == 3
    if any(v is not None and v >= 3 for v in values):
        return False
    return None if None in values else True

def deltas(a,b):
    return [int(x)-int(y) for x,y in product([0,1] if a is None else [a], [0,1] if b is None else [b])]

def compare():
    previous = read(RUN/"persist_exposure_fr3_v1/RESULTS.json")
    risk_rows = [r for r in previous["rows"] if r["track"] != "beneficial_memory_usage"]
    assert len(risk_rows) == 93 and all(r["exposure"]["branch"]=="grounding" for r in risk_rows)
    cross = read(RUN/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")
    groups = defaultdict(lambda:defaultdict(lambda:defaultdict(dict)))
    source = {(r["track"], r["uid"], r["repeat"]):r for r in risk_rows}
    for r in cross["rows"]:
        if r["track"] == "beneficial_memory_usage":
            continue
        cell=source[r["track"],r["uid"],r["repeat"]]["methods"][r["arm"]]
        assert r["old"]==(cell["score"]["rating"] if cell["score"] else None)
        for j,field in (("GPT","old"),("Qwen","qwen")):
            k=(r["track"],r["uid"])
            arm="QUERY" if r["arm"]=="SELECTED" else r["arm"]
            groups[k][j][arm][r["repeat"]]=r[field]
    fresh = read(RUN/"persist_utility_fresh_deployment_v1/private/SETTLED.json")
    opened = set(read(HERE.parent/"persist_query_requested_open_v1/SUMMARY.json")["utility_changed"])
    assert len(opened)==13
    utility=defaultdict(dict)
    for row in fresh["rows"]:
        utility[row["uid"]][row["arm"]]=row
    assert len(utility)==18 and len({u.split("/")[-1][:8] for u in utility})==18
    assert opened <= {u.split("/")[-1][:8] for u in utility}
    veto=defaultdict(Counter)
    for uid,cells in utility.items():
        switch = uid.split("/")[-1][:8] in opened
        for j in ("GPT","Qwen"):
            origin="FULL" if switch else "SELECTED"
            for arm,src in (("QUERY",origin),("RUBRIC","RUBRIC")):
                groups["beneficial_memory_usage",uid][j][arm][1]=cells[src][j]
            if switch:
                assert cells["FULL"][j]==3
                v=cells["SELECTED"][j]
                veto[j]["unknown" if v is None else "loses_pass" if v!=3 else "tie"]+=1
    tables=defaultdict(lambda:defaultdict(Counter))
    bounds=defaultdict(Counter)
    for (track,uid),pair in groups.items():
        intervals=[]
        for j,arms in pair.items():
            a,b=[passed(list(arms[k].values()),track=="beneficial_memory_usage") for k in ("QUERY","RUBRIC")]
            t=tables[track][j]
            for label,value in (("candidate",a),("author",b)):
                t[label+("_unknown" if value is None else "_pass" if value else "_fail")]+=1
            t["unknown" if None in (a,b) else "tie" if a==b else "win" if a else "loss"]+=1
            ds=deltas(a,b); t["low"]+=min(ds); t["high"]+=max(ds);intervals.append(ds)
        bounds[track]["low"]+=min(min(ds) for ds in intervals)
        bounds[track]["high"]+=max(max(ds) for ds in intervals)
    return dict(comparisons=tables,either_grader_bounds=bounds,open_to_selected_veto=veto)
if __name__=="__main__":print(json.dumps(compare(),indent=2))
