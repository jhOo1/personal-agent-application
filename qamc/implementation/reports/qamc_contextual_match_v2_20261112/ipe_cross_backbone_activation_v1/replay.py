"""Swap only the history activation bit; do not rerun either model."""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

def run():
    base = HERE.parent
    rows = json.loads((base/"ipe_c_second_backbone_v1/format_recovery/RESULTS.json").read_text())["rows"]
    first = json.loads((base/"ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]
    qwen = {r["uid"]:r for r in first}
    totals = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    disagreements = []
    skipped = []
    for r in rows:
        u = r["uid"]
        q = qwen[u]
        assert q["labels"] == r["labels"] and q["source_group"] == r["source_group"]
        paths = {"Qwen":[q["scores"][k] for k in ("TASK_ONLY","RPR_PAPER_FULL")],
                 "GPT":[r["scores"].get(k,{}) for k in ("TASK_ONLY","RP_FULL")]}
        cells = sum(paths.values(),[])
        if any(not c.get("grade",{}).get("match") for c in cells):
            skipped.append(u);continue
        assert r["qwen_path"] in ("TASK_ONLY","RPR_PAPER_FULL") and r["branch"] in ("TASK_ONLY","RP_FULL")
        a,b = r["qwen_path"]=="RPR_PAPER_FULL", r["branch"]=="RP_FULL"
        n=len(r["labels"])
        if a!=b:
            disagreements.append(dict(uid=u,stratum=r["stratum"],qwen_on=a,gpt_on=b,
                                      off_on_matches={model:[x["grade"]["match"]["matched"] for x in ends] for model,ends in paths.items()}))
        for model,ends in paths.items():
            for rule,on in (("Qwen",a),("GPT",b),("both",a and b),("either",a or b),("off",False),("on",True)):
                g=ends[int(on)]["grade"]
                assert g["match"]["positions"]==n
                value=g["match"]["matched"]
                for scope in ["all",r["stratum"]]+(["clean"] if all(c["flags"]==[] for c in cells) else []):
                    totals[scope][model][rule].update(tasks=1,positions=n,match=value,exact=int(value==n),OPB=g["OPB"],UPB=g["UPB"],FM=g["FM"])
    assert len(rows)==24 and totals["all"]["Qwen"]["Qwen"]["match"]==70 and totals["all"]["GPT"]["GPT"]["match"]==80
    return dict(totals=totals,disagreements=disagreements,missing=skipped)
if __name__=="__main__":
    print(json.dumps(run(),indent=2))
