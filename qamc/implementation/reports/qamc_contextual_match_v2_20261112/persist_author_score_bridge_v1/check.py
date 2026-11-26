"""Verify the fixed-answer Inspect Judge inputs without dispatching any calls."""
from collections import Counter
import json

from complete import AUTHOR, BASE, RUN, archive, get_author, normalized, persist, read
from compare_controls import STAGES, load_verified_scores
from qamc.common import sha
from qamc.contextual_match.inspect_judge import COMMIT, InspectPersistJudge

ROOT = BASE.parents[1]
LOCK = ROOT / "reports/qamc_contextual_match_20261111/persist_judge_route_v1/AUTHOR_SOURCE_LOCK.json"
ACTIVE = "SELECTED_GEPA"
REFERENCES = ("PB_RUBRIC", "PB_GEPA")


def checked_answers():
    selected, controls = load_verified_scores()
    author, bounds, _ = get_author()
    rows = {(r["uid"], r["method"]): r for r in author if r["method"] in REFERENCES}
    for stage in STAGES:
        records, _ = archive["supplementary"](BASE / "native_residual_v1" / stage, bounds, Counter())
        for record in records:
            if record["method"] == ACTIVE:
                key = record["uid"], ACTIVE
                if key in rows:
                    raise ValueError("Duplicate selected answer")
                rows[key] = record
    factorial, _ = archive["factorial"](bounds, Counter())
    latest = read(RUN / "RESULTS.json")["rows"]
    for row in [*factorial, *(r for r in latest if r["score"] is not None)]:
        key = row["uid"], ACTIVE
        if key in rows:
            raise ValueError("Duplicate selected answer")
        rows[key] = row
    cases = {r["uid"]: r for r in read(AUTHOR.parent / "PLAN.json")["cases"] if r["role"] == "DEV"}
    return selected, controls, rows, cases


def check():
    judge = InspectPersistJudge(ROOT, read(LOCK))
    selected, controls, rows, cases = checked_answers()
    requests, counts, intersections = {}, Counter(), {}
    for control in REFERENCES:
        common = {uid for uid in selected if control in controls[uid]}
        intersections[control] = common
        counts.update((control, selected[uid][0]) for uid in common)
        for uid in sorted(common):
            case = cases[uid]
            task = persist.author.parent.smoke.task_for(case)
            memories = [m.text for m in task.memories]
            if sha({"query": task.query, "memories": memories}) != case["public_sha256"]:
                raise ValueError("Original source or task changed")
            category, selected_score = selected[uid]
            if category != case["category"]:
                raise ValueError("Category changed")
            envelopes = set()
            for method, score in ((ACTIVE, selected_score), (control, controls[uid][control])):
                row = rows[uid, method]
                if row["score"] != score:
                    raise ValueError("Answer is not paired with its verified archive score")
                answer = row["answer"]
                wire = judge.request(memories, task.query, answer, category, "kimi-k2-thinking")
                envelopes.add(sha(normalized(wire, answer)))
                requests[uid, method] = sha(wire)
            if len(envelopes) != 1:
                raise ValueError("Inspect grading input differs beyond the answer")
    primary, secondary = (intersections[control] for control in REFERENCES)
    return {
        "inspect_commit": COMMIT,
        "dev_pair_counts": {f"{m}/{t}": n for (m, t), n in sorted(counts.items())},
        "primary_pairs": len(primary), "secondary_pairs": len(secondary),
        "shared_tasks": len(primary & secondary),
        "unique_task_method_positions": len(requests),
        "unique_gateway_template_hashes": len(set(requests.values())),
        "aggregate_input_fingerprint": sha(sorted((uid, method, digest) for (uid, method), digest in requests.items())),
        "generation_calls": 0, "judge_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
