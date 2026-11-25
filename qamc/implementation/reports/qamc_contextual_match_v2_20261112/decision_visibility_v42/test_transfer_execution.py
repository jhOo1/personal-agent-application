"""Run the whole transfer pipeline offline using actual archived Judge replies."""
from collections import Counter
from copy import deepcopy
import json

from qamc.common import sha

import transfer_execution as run


def test_benchmark(benchmark):
    panel = run.development_roots(benchmark)
    by_uid = {row["uid"]: row for row in panel}
    old = {row["uid"]: row for row in run.read(run.development.OUT / "RESULT_ROWS.json")
           if row["uid"] in by_uid and row["method"] == run.RP}
    grade_by_uid = ({row["uid"]: row["raw_scores"] for row in old.values()} if benchmark == "BenchPreS" else
                    {row["uid"]: {run.persist.STAGE: row["raw_score"]}
                     for row in run.read(run.PERSIST_RP / "RESULTS.json")["rows"]})
    terminal_scores = ({uid: row["score"] for uid, row in old.items()} if benchmark == "BenchPreS" else
                       {row["uid"]: row["score"] for row in run.read(run.PERSIST_RP / "RESULTS.json")["rows"]})
    counts, signatures = Counter(), {}

    def dispatch(jobs):
        output = {}
        for key, wire in jobs.items():
            uid, arm, stage = key
            counts[stage] += 1
            if stage == run.SELECTOR:
                public = json.loads(wire["messages"][1]["content"])
                assert set(public) == {"query", "current_context", "facts", "source_evidence"}
                source = public["source_evidence"][0]
                result = {"decisions": [{"id": "D1", "anchor": public["query"][:35], "beneficiary": "fixture"}],
                          "uses": [] if arm == "SCOPED" else [
                              {"memory_id": source["memory_id"], "decision_id": "D1", "level": "B",
                               "source_quote": source["text"][:35]}]}
                answer = json.dumps(result, ensure_ascii=False)
            elif stage == run.ACTOR:
                result = json.loads(wire["messages"][1]["content"])
                assert result["query"] == by_uid[uid]["public_task"]["query"]
                if arm == "SCOPED_MASKED":
                    assert result["source_evidence"] == []
                if arm == "SCOPED_FULL":
                    assert result["source_evidence"] == by_uid[uid]["original_sources"]
                answer = old[uid]["answer"]
            else:
                answer = grade_by_uid[uid].get(stage)
                signatures[uid, stage] = sha(wire)
            output[key] = {"status": "OK" if answer else "ARCHIVED_FIELD_MISSING",
                           "answer": answer, "request_sha256": sha(wire)}
        return output

    scored, summary = run.evaluate(benchmark, dispatch)
    assert len(scored) == len(panel) * 3
    for row in scored:
        assert row["score"] == terminal_scores[row["uid"]]
    assert counts[run.SELECTOR] == 2 * len(panel) and counts[run.ACTOR] == 3 * len(panel)
    assert sum(counts.values()) - counts[run.SELECTOR] - counts[run.ACTOR] == (
        6 * len(scored) if benchmark == "BenchPreS" else len(scored))
    assert len(summary["paired"]) == (9 if benchmark == "BenchPreS" else 8)
    unreachable = deepcopy(panel[0])
    unreachable["public_task"]["query"] = "not an archived task"

    def fail_if_dispatched(_):
        raise AssertionError("Changed public input reached dispatch")

    try:
        run.evaluate(benchmark, fail_if_dispatched, panel=[unreachable])
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted a changed input")

    def failed_selection(jobs):
        if jobs:
            assert set(job[2] for job in jobs) == {run.SELECTOR}
        return {key: {"status": "PENDING_DELIVERY_UNKNOWN", "answer": None,
                      "request_sha256": sha(wire)} for key, wire in jobs.items()}

    failed, _ = run.evaluate(benchmark, failed_selection, panel=panel[:1])
    assert len(failed) == 3 and all(row["actor_status"] == "NO_VALID_SELECTOR" and row["score"] is None for row in failed)
    if benchmark == "PersistBench":
        for row in run.read(run.PERSIST_RP / "RESULTS.json")["rows"]:
            assert signatures[row["uid"], run.persist.STAGE] == row["RP_gpt41_request_sha256"]
    return {"roots": len(panel), "logical_stage_slots": counts, "archived_strict_reproduced": sum(
        result is not None for result in terminal_scores.values()), "fresh_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps({name: test_benchmark(name) for name in ("BenchPreS", "PersistBench")}, indent=2))
