"""Publish aggregates only, retaining attribute decisions and costs in private storage."""
import json
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
run = here.parents[2]/"runs"/here.parent.name/here.name
data = json.loads((run/"private/SETTLED.json").read_bytes())
receipts = [json.loads(p.read_bytes()) for p in run.glob("EnrollmentGrade/visible/*/record.json")]
assert len(receipts)==12 and len({r["request_sha256"] for r in receipts})==12
assert {(r["request_sha256"],r["status"]) for r in receipts}=={(r["request_sha256"],r["status"]) for r in data["ledger"]}
print(json.dumps(dict(scores=data["results"], requests=len(receipts), statuses=Counter(r["status"] for r in receipts),
                      reported_tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in receipts),
                      unknown_usage=sum((r.get("usage") or {}).get("total_tokens") is None for r in receipts),
                      retries=sum(r["automatic_retries"] for r in receipts)),indent=2,sort_keys=True))
