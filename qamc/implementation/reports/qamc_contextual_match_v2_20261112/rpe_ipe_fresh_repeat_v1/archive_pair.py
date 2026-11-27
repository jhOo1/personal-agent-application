"""Contextualize fresh scores against the identical historical task slice."""
from pathlib import Path
import json

here=Path(__file__).resolve().parent
out=here.parents[2]/"runs"/here.parent.name/here.name
archive=json.loads((here.parent/"selective_path_frontier_v1/RESULTS.json").read_text())
lookup={r["uid"]:r for r in archive["rows"]}
panel=json.loads((out/"PANEL_V2.json").read_text())
data={}
for group,uids in [("assigned",[c[0] for c in panel["cards"]])]+[
    (f"deployment{n}_common",[r["uid"] for r in json.loads((out/f"deployment{n}"/"RESULTS.json").read_text())["rows"]
                             if r["branch"] and all(s["grade"].get("match") for s in r["scores"].values())]) for n in (1,2)]:
    rows=[lookup[u] for u in uids]
    data[group]=dict(roots=len(rows),positions=sum(r["positions"] for r in rows))
    for method in ("IPE_C","TASK_ONLY","RPR_PAPER_FULL"):
        data[group][method]=sum(r["cells"][r["base"] if method=="IPE_C" else method]["matched"] for r in rows)
(here/"ARCHIVE_PAIR.json").write_text(json.dumps(data,indent=2)+"\n")
