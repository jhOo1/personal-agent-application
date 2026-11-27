"""Compare previously scored complete answers on the same C-bearing development tasks."""
import json
from collections import Counter
from pathlib import Path

base = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads((base / path).read_text())

rows = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
formal = read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
lookup = {(r["uid"], r["method"]): r for r in formal}
assert len(lookup) == len(formal)
arms = sorted({r["method"] for r in formal})
counts = Counter()
exact = Counter()
match = Counter()
profiles = Counter()
unique = Counter()
perfect_roots = set()
perfect_answers = set()
perfect_reasons = set()
for row in rows:
    if not all(v["grade"].get("match") for v in row["scores"].values()) or "C" not in row["labels"]:
        continue
    counts["starting_tasks"] += 1
    scores = {arm:row["scores"][arm]["grade"] for arm in ("IPE_C","TASK_ONLY")}
    for arm in arms:
        scores[arm] = lookup[row["uid"],arm]["native_fields"] or {}
    if not all(s.get("match") for s in scores.values()):
        counts["excluded_incomplete_comparison"] += 1
        continue
    n = len(row["labels"])
    assert all(s["match"]["positions"] == n for s in scores.values())
    counts["paired_tasks"] += 1
    counts["positions"] += n
    winners = []
    values = []
    for arm,score in scores.items():
        k = score["match"]["matched"]
        values.append(k)
        match[arm] += k
        exact[arm] += k == n
        if k == n:
            winners.append(arm)
    counts["any_exact"] += bool(winners)
    profiles[len(winners)] += 1
    counts["hindsight_position_max"] += max(values)
    if len(winners) == 1:
        unique[winners[0]] += 1
    if winners:
        for arm in winners:
            if arm == "TASK_ONLY":
                perfect_roots.add(row["source_group"])
                perfect_answers.add(row["scores"][arm]["answer_sha256"])
                perfect_reasons.add(json.loads(row["no_history_state"]["raw"])["reason"])
print(json.dumps(dict(panel=counts, exact=exact, match=match, exact_method_count_distribution=profiles,
                      exclusively_exact=unique, task_only_exact_unique_roots=len(perfect_roots),
                      task_only_exact_unique_answers=len(perfect_answers), task_only_exact_unique_reasons=len(perfect_reasons)),sort_keys=True,indent=2))
