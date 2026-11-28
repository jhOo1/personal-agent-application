"""Verify actual task-only input and reply identity for the four highlighted all-A endpoints."""
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
audit = run_path(str(HERE / "audit.py"))
archive, sha = audit["archive"], audit["sha"]
figure = audit["previous"]
old = figure["old"]
v41, ext = old["v41"], old["ext"]


def check():
    _, cards, _, _ = audit["prepare"]()
    all_a = {u: c for u, c in cards.items() if c["stratum"] == "all_A"}
    _, _, _, archived, ranking, _, snapshots, old_inputs = ext.prepare()
    endpoints = {r["uid"]: r for r in archive.read(old["ENDPOINTS"] / "RESULTS.json")["rows"]}
    records = []
    for uid, meta in all_a.items():
        row = endpoints[uid]
        req = v41.task_only_request(ext.source_root(archived[uid, old["FULL"]], ranking[uid]))
        digest = sha(req)
        # The completion file logs this field only for requests that it completed itself.
        reference = row["task_wire_sha256"] or old_inputs[uid]["task_wire_sha256"]
        if digest != reference:
            raise ValueError(f"Actor envelope differs for {meta['case']}")
        snapshot = snapshots[digest]
        answer = row["no_history_state"]["answer"]
        if snapshot["answer"] != answer or sha(answer) != row["scores"][old["ZERO"]]["answer_sha256"]:
            raise ValueError("Archived receipt and scored answer differ")
        packet = json.loads(req["messages"][1]["content"])
        if packet["source_evidence"] or packet["preference_use_policy"]:
            raise ValueError("Task-only exposure mismatch")
        records.append({"case": meta["case"], "source_records": len(packet["source_evidence"]),
                        "policy_records": len(packet["preference_use_policy"]),
                        "fact_records": len(packet["facts"]), "answer_verified": True,
                        "figure_upb": meta["figure_grade"][old["ZERO"]]["severity"]["UPB"]})
    return {"cases": records, "new_model_requests": 0}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
