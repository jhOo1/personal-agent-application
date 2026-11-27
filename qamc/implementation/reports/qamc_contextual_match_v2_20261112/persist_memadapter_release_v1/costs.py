"""Reconcile frozen stage registrations, final transport receipts and the runner ledger."""
from collections import Counter, defaultdict
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[2]/"runs"/HERE.parent.name/HERE.name


def report():
    private=RUN/"private"
    ledger=json.loads((private/"SETTLED.json").read_text())["ledger"]
    total=Counter()
    by_stage=defaultdict(Counter)
    statuses=Counter()
    start=[]
    end=[]
    for f in sorted(private.glob("D*_MANIFEST.json")):
        stage=f.name.removesuffix("_MANIFEST.json")
        expected={r["unit"]["root_id"] for r in json.loads(f.read_text())["units"]}
        seen=set()
        for file in (RUN/stage/"visible").glob("*/record.json"):
            rec=json.loads(file.read_text())
            digest=rec["request_sha256"]
            assert digest not in seen and digest in expected
            seen.add(digest)
            assert rec["unit"]["stage"]==stage and rec["status"]!="PENDING_DELIVERY_UNKNOWN"
            stats=by_stage[stage[2:]]
            stats["requests"]+=1
            stats["automatic_retries"]+=rec["automatic_retries"]
            statuses[rec["status"]]+=1
            if rec["usage"] and rec["usage"].get("total_tokens") is not None:
                stats["reported_tokens"]+=rec["usage"]["total_tokens"]
            else:
                stats["unknown_usage"]+=1
            if rec.get("reported_completion_over_requested") is True:
                stats["above_requested_cap"]+=1
            start.append(rec["started_unix"])
            if rec.get("elapsed_seconds") is not None:
                end.append(rec["started_unix"]+rec["elapsed_seconds"])
        assert seen==expected
    for s in by_stage.values():
        total.update(s)
    assert total["requests"]==len(ledger)
    assert statuses==Counter(r["status"] for r in ledger)
    assert total["reported_tokens"]==sum((r["usage"] or {}).get("total_tokens",0) for r in ledger)
    return dict(total=total,statuses=statuses,by_stage=by_stage,
                first_to_last_timed_receipt_seconds=round(max(end)-min(start),1),
                final_receipts_with_elapsed=len(end))


if __name__=="__main__":
    print(json.dumps(report(),indent=2))
