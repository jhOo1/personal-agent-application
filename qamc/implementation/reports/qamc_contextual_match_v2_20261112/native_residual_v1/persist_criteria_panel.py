"""Find exposed PersistBench first-pass targets and matched protection cases."""
from collections import Counter
from pathlib import Path

from build_jobs import archive_inputs
from qamc.common import sha
from trial_reassembly import probe

HERE = Path(__file__).resolve().parent
CENSUS = HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json"


def prepare():
    wires, cards = archive_inputs()
    candidates = probe.read(CENSUS)["PersistBench"]["roots"]
    candidates.sort(key=lambda row: sha(["persist-criteria", row["uid"]]))
    quota = {("sycophancy", True): 5, ("sycophancy", False): 2,
             ("cross_domain", False): 2, ("beneficial_memory_usage", False): 3}
    counts, groups, rows = Counter(), set(), []
    for row in candidates:
        score = row["score"]
        bucket = row["category"], score["failure_release"]
        if counts[bucket] >= quota.get(bucket, 0) or row["group"] in groups:
            continue
        key = "PersistBench", row["uid"]
        baseline, original = cards[key], wires[key]
        if (sha(baseline["base_answer"]) != row["answer_sha256"]
                or baseline["base_score"] != score
                or sha(original["actor_request"]) != row["actor_request_sha256"]):
            raise ValueError("PersistBench archive drift")
        rows.append(row)
        counts[bucket] += 1
        groups.add(row["group"])
    if counts != quota:
        raise ValueError(f"Coverage differs from frozen quota: {counts}")
    return rows, wires, cards


if __name__ == "__main__":
    rows, _, _ = prepare()
    print(Counter((row["category"], row["score"]["failure_release"]) for row in rows))
