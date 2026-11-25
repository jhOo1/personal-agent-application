"""Run the focal transfer path using fixtures and verified archived RP scores."""
from collections import Counter
import json

from qamc.common import sha

import focal_memory as focal
import focal_transfer as transfer


def replay(benchmark):
    roots = {root["uid"]: root for root in transfer.development_roots(benchmark)}
    archived = {row["uid"]: row["answer"] for row in transfer.archived_answers(benchmark, roots)
                if row["method"] == transfer.RP}
    seen = Counter()

    def offline(jobs):
        receipts = {}
        for key, wire in jobs.items():
            uid, method, stage = key
            root = roots[uid]
            data = json.loads(wire["messages"][1]["content"])
            seen[stage] += 1
            if stage == transfer.PLAN:
                source_text = [source["text"] for source in root["original_sources"]]
                if (set(data) != {"task", "focal_memory", "other_memories"}
                        or data["task"] != root["public_task"] or data["focal_memory"] not in source_text
                        or len(data["other_memories"]) != (0 if method == focal.ISOLATED else len(source_text) - 1)):
                    raise ValueError("Fixture predictor does not match the exposed source boundary")
                answer = json.dumps({"policy": "A", "decision": None, "affected_role": None,
                                     "task_quote": None, "source_quote": None})
            elif stage == transfer.ACTOR:
                if (wire["messages"][0] != root["archived_actor_request"]["messages"][0]
                        or data["source_evidence"] != root["original_sources"]
                        or {k: data[k] for k in root["public_task"]} != root["public_task"]
                        or sum(a != b for a, b in zip(data["preference_use_policy"], root["archived_policy"],
                                                     strict=True)) != 1):
                    raise ValueError("Transfer Actor changed outside the focal policy")
                answer = archived[uid]
            else:
                raise ValueError(f"Missing prior score for exact transfer fixture: {stage}")
            receipts[key] = {"status": "OK", "request_sha256": sha(wire), "answer": answer}
        return receipts

    result = transfer.evaluate(benchmark, offline)
    _, _, controls = transfer.context(benchmark)
    old_scores = {row["uid"]: row["score"] for row in controls if row["method"] == transfer.RP}
    if (old_scores.keys() != roots.keys() or len(result["rows"]) != 2 * len(roots)
            or any(row["score"] != old_scores[row["uid"]] for row in result["rows"])):
        raise ValueError("Replayed score differs from the original native RP score")
    return {"assigned": result["assigned"], "grading_model": result["grading_model"],
            "archived_RP_scores_replayed_by_arm": result["valid_scores"], "local_figures": seen,
            "new_live_requests": 0, "new_method_scores": 0}


if __name__ == "__main__":
    print(json.dumps({name: replay(name) for name in ("BenchPreS", "PersistBench")}, ensure_ascii=False, indent=2))
