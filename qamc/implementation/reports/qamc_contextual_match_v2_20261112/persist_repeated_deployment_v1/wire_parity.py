"""Audit GEPA prompt equality and cap differences without contacting the gateway."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path


def audit():
    runner = run_path(str(Path(__file__).with_name("run.py")))
    _, cases, data, factorial, _, _ = runner["prepare"]()
    counts = Counter()
    empty_requests = {}
    for uid, case in cases.items():
        public, _, full_controls = data[uid]
        plain_args = (case, public["query"])
        prompt_args = (factorial, factorial["prompts"]["gepa"])
        full = runner["actor_request"](*plain_args, public["memories"], *prompt_args)
        reference = full_controls["PB_GEPA"]
        delta = tuple(sorted(k for k in full.keys() | reference.keys() if full.get(k) != reference.get(k)))
        counts["fields/" + ",".join(delta)] += 1
        counts[f"output_cap/{full['max_tokens']}/{reference['max_tokens']}"] += 1
        empty_requests[uid] = runner["actor_request"](*plain_args, [], *prompt_args)
    author, _, _ = runner["get_author"]()
    old_empty = {r["uid"]: r for r in author if r["method"] == "PB_NO_MEMORY"}
    historical_empty = Counter()
    for uid, wire in empty_requests.items():
        bucket = cases[uid]["category"]
        row = old_empty[uid]
        historical_empty[f"{bucket}/total"] += 1
        historical_empty[f"{bucket}/same_wire"] += row["actor_request"] == wire
        historical_empty[f"{bucket}/scored"] += row["score"] is not None
    stages = {}
    for draw in range(1, 4):
        stage = f"Draw{draw}_SelectedActor"
        manifest_path = runner["RUN"] / f"{stage}_MANIFEST.json"
        if not manifest_path.exists():
            continue
        manifest = runner["read"](manifest_path)
        counts_by_category = Counter()
        for item in manifest["units"]:
            uid = item["unit"]["root_id"]
            if item["request"] == empty_requests[uid]:
                counts_by_category[cases[uid]["category"]] += 1
        stages[stage] = counts_by_category
    return {"counterfactual_full_vs_archived_gepa": counts,
            "historical_empty_wire": historical_empty,
            "allocated_gepa_empty_wires": stages}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
