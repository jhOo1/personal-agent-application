"""Freeze paired exposed Actor outputs independently of any Judge outcome."""
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[2]/"runs"/HERE.parent.name/"benchpres_repeat_matched_v1"
METHODS=("GEPA_SELECTED_BOUNDS","PAPER_SELECTIVITY")

def read(path):
    return json.loads(path.read_text())

def inventory():
    plan=read(RUN/"PLAN_PRIVATE.json")
    cases={c["uid"]:c for c in plan["cases"]}
    if len(cases)!=48 or any(c["independent_confirmation"] for c in cases.values()):
        raise ValueError("Not the frozen exposed roster")
    wires = {k:v for k,v in plan["generation"].items()}
    answers={}
    for p in sorted(RUN.glob("wave-*/generation/outputs/*.json")):
        row=read(p)
        if row["status"]!="OK":continue
        job=wires[p.stem]
        wire=json.dumps(job["request"],ensure_ascii=False,sort_keys=True,separators=(",",":"))
        if hashlib.sha256(wire.encode()).hexdigest()!=row["request_sha256"] or job["unit"]!=row["unit"]:
            raise ValueError("Actor receipt mismatch")
        u=row["unit"]
        key=(u["root_id"],u["replicate"],u["method"])
        if key in answers or not isinstance(row["answer"],str) or not row["answer"].strip():
            raise ValueError("Ambiguous completed Actor")
        answers[key]=hashlib.sha256(row["answer"].encode()).hexdigest()
    paired=[{"uid":uid,"draw":draw,"answers":[answers[uid,draw,m] for m in METHODS]}
            for uid in sorted(cases) for draw in range(3) if all((uid,draw,m) in answers for m in METHODS)]
    counts=Counter(r["uid"] for r in paired)
    return {"allocation":144,"pairs":len(paired),"tasks":len(counts),
            "pairs_per_draw":dict(Counter(r["draw"] for r in paired)),
            "pair_count_by_task":dict(Counter(counts.get(uid,0) for uid in cases)),
            "ordered_answer_pair_manifest_sha256":hashlib.sha256(json.dumps(paired,sort_keys=True).encode()).hexdigest()}

if __name__=="__main__": print(json.dumps(inventory(),indent=2))
