"""Compare archived external answers with IPE-C on tasks with B and no C."""
import json
import hashlib
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
def read(p):
    return json.loads(p.read_text())

def digest(obj):
    text=obj if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(text.encode()).hexdigest()

def matched(s):
    return (s.get("match") or {}).get("matched")

controls={r["uid"]:r for r in read(BASE/"ipe_c_full_exposed_panel_v1/RESULTS.json")["rows"]}
cases=read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
formal={(r["uid"],r["method"]):r for r in read(BASE/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")}
frozen={r["uid"]:r for r in read(BASE/"transactional_reassembly_v1/FROZEN.json")["rows"]}
counts={}
candidates=[]
for m in ("RPR_PAPER_FULL","MEMADAPTER_FULL","DES2GEN_FULL"):
    cnt=Counter()
    for r in cases:
        labels=r.get("labels") or ""
        if "B" not in labels or "C" in labels:
            continue
        cnt["eligible_labels"]+=1
        incumbent=r.get("ipe_c") or {}
        alternative=controls[r["uid"]]["controls"].get(m) or {}
        a,b=(cell.get("grade") or {} for cell in (incumbent,alternative))
        if matched(a) is None or matched(b) is None:
            cnt["unknown"]+=1
            continue
        assert a["match"]["positions"]==b["match"]["positions"]==len(labels)
        cnt["paired"]+=1
        if matched(b)<=matched(a):
            continue
        cnt["strict_match_win"]+=1
        if not all(k in a and k in b and b[k]<=a[k] for k in ("OPB","UPB","FM")):
            continue
        cnt["protected_win"]+=1
        uid=r["uid"]
        ext=formal[uid,m]
        assert digest(ext["actor_request"])==ext["actor_request_sha256"]
        assert digest(ext["answer"])==alternative["answer_sha256"]
        inc_text=controls[uid].get("answer")
        assert inc_text and digest(inc_text)==incumbent["answer_sha256"]
        candidates.append(dict(uid=uid,group=r["source_group"],method=m,labels=labels,score=[matched(a),matched(b)],
                               flags=[incumbent["flags"],alternative["flags"]],answers=[digest(inc_text),digest(ext["answer"])]))
    counts[m]=dict(cnt)
for uid in ("rpeval/formal_multi_v1/implicit/008","rpeval/formal_multi_v1/implicit/099"):
    g=frozen[uid]; ext=formal[uid,"DES2GEN_FULL"]
    assert digest(g["base_answer"])==g["baseline_answer_sha256"]
    assert digest(ext["actor_request"])==ext["actor_request_sha256"]
    assert matched(ext["native_fields"])-matched(g["base_score"])==1
(HERE/"SUMMARY.json").write_text(json.dumps(dict(methods=counts,candidates=candidates),indent=2)+"\n")
