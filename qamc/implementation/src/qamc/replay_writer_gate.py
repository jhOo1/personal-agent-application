"""Offline replay of saved engineering failures, never a replacement model result."""
import json
import sqlite3
from pathlib import Path

from .common import ROOT, dump, parse_object, sha
from .memory_writer import validate_writer_plan
from .memory_store import MemoryRecord


def replay():
    root = ROOT / "runs/v0/api"
    db = sqlite3.connect(f"file:{root/'ledger.sqlite'}?mode=ro", uri=True)
    results = []
    for data, in db.execute("SELECT data FROM requests"):
        row = json.loads(data)
        if not row["key"].endswith("/writer"):
            continue
        response = root / row["response_path"]
        if not response.exists():
            continue
        request = json.loads((root / row["request_path"]).read_text())
        payload = json.loads(request["messages"][1]["content"])
        raw = json.loads(response.read_text()).get("answer", "")
        try:
            obj = parse_object(raw)
            prior = [MemoryRecord(**r) for r in payload["existing_memories"]]
            validate_writer_plan(obj, {t["id"] for t in payload["segment"]}, prior)
            status, error = "contract_accepted", None
        except (ValueError, AssertionError, KeyError, TypeError) as exc:
            status, error = "contract_rejected", str(exc) or type(exc).__name__
        if row["status"] != "ok":
            # Even a parseable prefix cannot override the original transport finish status.
            status = "transport_failure_retained"
        results.append({"key": row["key"], "response_path": str(response.relative_to(ROOT)),
                        "response_sha256": sha(response.read_bytes()), "original_status": row["status"],
                        "offline_status": status, "contract_error": error, "new_real_requests": 0})
    assert any(r["offline_status"] == "transport_failure_retained" for r in results)
    assert any(r["offline_status"] == "contract_rejected" for r in results)
    dump(ROOT / "reports/WRITER_OFFLINE_REPLAY_v0_to_v0_1.json", {"model_calls": 0, "replays": results,
         "scope": "contract detection only; no fabricated model improvement or benchmark scores"})
    print(json.dumps({"saved_writer_responses_replayed": len(results), "model_calls": 0}))


if __name__ == "__main__":
    replay()
