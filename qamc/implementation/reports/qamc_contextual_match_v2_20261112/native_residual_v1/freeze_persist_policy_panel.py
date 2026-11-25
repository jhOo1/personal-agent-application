"""Freeze exposed PersistBench source groups for policy search and evaluation."""
from collections import Counter
import json

from persist_criteria_panel import CENSUS, HERE
from persist_policy_block import locate
from build_jobs import archive_inputs
from qamc.common import sha

QUOTAS = {
    ("sycophancy", True): (3, 2),
    ("sycophancy", False): (3, 3),
    ("cross_domain", False): (3, 4),
    ("beneficial_memory_usage", False): (3, 3),
}
OUT = HERE / "PERSIST_POLICY_PANEL.json"


def build():
    wires, cards = archive_inputs()
    census = json.loads(CENSUS.read_text())["PersistBench"]["roots"]
    seen = set()
    rows, counts, blocks = [], Counter(), set()
    root_order = sorted(census, key=lambda row: (
        not row["score"]["failure_release"], sha(["persist-native-policy-v1", row["uid"]]),
    ))
    for entry in root_order:
        category = entry["category"], entry["score"]["failure_release"]
        search_cap, group_cap = QUOTAS.get(category, (0, 0))
        rank = counts[category]
        if rank >= search_cap + group_cap or entry["group"] in seen:
            continue
        key = "PersistBench", entry["uid"]
        wire = wires[key]["actor_request"]
        card = cards[key]
        if (sha(wire) != entry["actor_request_sha256"]
                or sha(card["base_answer"]) != entry["answer_sha256"]
                or card["base_score"] != entry["score"]):
            raise ValueError("Baseline archive drift")
        system, = [m["content"] for m in wire["messages"] if m["role"] == "system"]
        blocks.add(locate(system)[1])
        rows.append({
            "uid": entry["uid"], "group": entry["group"], "category": entry["category"],
            "actor_sha256": sha(wire), "baseline_sha256": sha(card["base_answer"]),
            "grade_sha256": sha(card["base_score"]),
            "split": "search" if rank < search_cap else "group_out",
        })
        counts[category] += 1
        seen.add(entry["group"])
    if counts != Counter({key: sum(caps) for key, caps in QUOTAS.items()}) or len(blocks) != 1:
        raise ValueError("Unexpected cohort coverage or policy drift")
    policy, = blocks
    return {"policy_sha256": sha(policy), "byte_cap": len(policy.encode()) + 768, "rows": rows}


if __name__ == "__main__":
    value = build()
    if OUT.exists():
        if json.loads(OUT.read_text()) != value:
            raise ValueError("Frozen panel changed")
    else:
        OUT.write_text(json.dumps(value, indent=2) + "\n")
    print(dict(Counter(row["split"] for row in value["rows"])))
