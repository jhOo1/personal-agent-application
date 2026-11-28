"""Check physical selection, actor and judge receipts against the frozen manifests."""
from collections import Counter
import json
from pathlib import Path
from qamc.common import sha

here=Path(__file__).resolve().parent
out=here.parents[2]/"runs"/here.parent.name/here.name
read=lambda p:json.loads(p.read_text())
pin=read(out/"FROZEN.json")
ids=set()
totals=Counter()
for n in (1,2,3):
    record_counts=Counter()
    draw=read(out/f"DRAW_{n}.json")
    grades={}
    for label in ("Select","Actor","gpt","qwen"):
        name=f"D{n}{label}"
        manifest=out/"private"/f"{name}_MANIFEST.json"
        if not manifest.exists():
            assert not (out/name/"visible").exists()
            continue
        expected={r["unit"]["root_id"]:r["request"] for r in read(manifest)["units"]}
        found=set()
        for path in (out/name/"visible").glob("*/record.json"):
            rec=read(path)
            uid=rec["unit"]["root_id"]
            assert uid not in found
            found.add(uid)
            w=read(path.with_name("request.json"))
            assert expected[uid]==w and sha(w)==rec["request_sha256"] and rec["automatic_retries"]==0
            record_counts[name,uid,rec["status"]]+=1
            if rec["status"]=="OK":
                resp=read(path.with_name("response.json"))
                if resp.get("id"):
                    assert resp["id"] not in ids
                    ids.add(resp["id"])
                else:
                    totals["missing_success_ids"]+=1
            if label=="Select":
                assert sha(w)==pin["selectors"][uid]
                payload=json.loads(w["messages"][1]["content"])
                assert set(payload)=={"question","retrieved_memories"}
                assert all(set(m)=={"memory_id","content"} for m in payload["retrieved_memories"])
            if label in ("gpt","qwen"):
                grades.setdefault(uid,{})[label]=w
        assert found==expected.keys()
    assert record_counts==Counter((r["unit"]["stage"],r["unit"]["root_id"],r["status"]) for r in draw["ledger"])
    totals["physical"]+=sum(record_counts.values())
    for g in grades.values():
        if len(g)==2:
            assert g["gpt"]["messages"]==g["qwen"]["messages"]
            totals["physical_double_grades_verified"]+=1
print(json.dumps({**totals,"distinct_success_ids":len(ids)},indent=2))
