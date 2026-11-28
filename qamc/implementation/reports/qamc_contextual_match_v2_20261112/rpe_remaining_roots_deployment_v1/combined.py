"""Cover all 42 exposed roots using their respective two deployments; no repeated-root inflation."""
import json
from collections import defaultdict, Counter
from pathlib import Path

here = Path(__file__).resolve().parent
runs = here.parents[2]/"runs"/here.parent.name
panels = [runs/"rpe_ipe_fresh_repeat_v1",runs/here.name]
archive = {r["uid"]: r["scores"] for r in json.loads((here.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]}
rosters = [json.loads((p/"PANEL_V2.json").read_text())["cards"] for p in panels]
assert len({g for cards in rosters for u,g,s in cards}) == sum(map(len,rosters)) == 42
common = {}
for path,cards in zip(panels,rosters):
    waves = [{r["uid"]:r for r in json.loads((path/f"deployment{n}/RESULTS.json").read_text())["rows"]} for n in (1,2)]
    for uid,g,stratum in cards:
        entries = [archive[uid]] + [w[uid] for w in waves]
        methods = [dict(IPE_C=entries[0]["IPE_C"],FULL=entries[0]["RPR_PAPER_FULL"],EMPTY=entries[0]["TASK_ONLY"])]
        for r in entries[1:]:
            assert r["group"]==g and r["stratum"]==stratum
            if r["branch"]:
                methods.append(dict(IPE_C=r["scores"][r["branch"]],FULL=r["scores"]["RP_FULL"],EMPTY=r["scores"]["TASK_ONLY"]))
        if len(methods)==3 and all(x["grade"].get("match") for m in methods for x in m.values()):
            common[g] = stratum,methods
totals = defaultdict(Counter)
for stratum,methods in common.values():
    for idx,m in enumerate(methods):
        for arm,cell in m.items():
            grade = cell["grade"]
            s=grade["match"]
            for level in ("all",stratum):
                totals[f"{idx}/{level}/{arm}"].update(roots=1,positions=s["positions"],matched=s["matched"],
                    exact=int(s["matched"]==s["positions"]),OPB=grade["OPB"],UPB=grade["UPB"],FM=grade["FM"])
print(json.dumps(dict(assigned=42,common=len(common),tables=totals),indent=2))
