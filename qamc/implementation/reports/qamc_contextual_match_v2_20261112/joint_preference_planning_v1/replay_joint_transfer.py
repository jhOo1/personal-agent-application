"""Check the joint planning transfer path with actual saved answers and scores."""
from collections import Counter
import json

from qamc.common import sha

import joint_transfer as transfer
from planning import task_text
from transfer_edit import RP


def replay(benchmark):
    roots = {r["uid"]: r for r in transfer.development_roots(benchmark)}
    archived = {r["uid"]: r for r in transfer.archived_answers(benchmark, roots) if r["method"] == RP}
    seen = Counter()

    def offline(jobs):
        values = {}
        for key, wire in jobs.items():
            uid, _, stage = key
            seen[stage] += 1
            answer = None
            if stage in (transfer.PLAN, transfer.ACTOR):
                visible = json.loads(wire["messages"][1]["content"])
                root = roots[uid]
                if (visible["task"] != root["public_task"]
                        or visible["source_evidence"] != root["original_sources"]):
                    raise ValueError("Transfer request changed the public task or memory")
            if stage == transfer.PLAN:
                if visible.keys() != {"task", "source_evidence"}:
                    raise ValueError("Unexpected evaluation input in the planner")
                anchor = next(s for s in task_text(visible["task"]) if s.strip())[:160]
                answer = json.dumps({
                    "decisions": [{"name": "Replay fixture", "task_quote": anchor,
                                   "options": [{"text": "Fixture", "task_cost": 0, "conditional_on": None}]}],
                    "hard": [], "soft": [], "selection": {"D1": "O1"},
                })
            elif stage == transfer.ACTOR:
                if visible["selection"] != {"D1": "O1"}:
                    raise ValueError("Actor did not inherit the approved replay selection")
                answer = archived[uid]["answer"]
            values[key] = {"status": "OK" if answer else "ARCHIVED_FIELD_MISSING",
                           "request_sha256": sha(wire), "answer": answer}
        return values

    outcome = transfer.evaluate(benchmark, offline)
    _, _, controls = transfer.context(benchmark)
    scores = {row["uid"]: row["score"] for row in controls if row["method"] == RP}
    if (len(outcome["rows"]) != 2 * len(roots) or scores.keys() != roots.keys()
            or any(row["score"] != scores[row["uid"]] for row in outcome["rows"])):
        raise ValueError("Replayed scores do not match the frozen RP native result")
    if seen[transfer.PLAN] > len(roots) or seen[transfer.ACTOR] > len(roots):
        raise ValueError("Identical Actor requests were not deduplicated in the replay")
    return {"assigned": outcome["assigned"], "archived_RP_scores_replayed_by_arm": outcome["valid_scores"],
            "archived_grade_reuse": outcome["transport_reuse"]["archived_grade_reuse"],
            "fixture_requests": seen, "new_live_requests": 0}


if __name__ == "__main__":
    print(json.dumps({name: replay(name) for name in ("BenchPreS", "PersistBench")}, ensure_ascii=False, indent=2))
