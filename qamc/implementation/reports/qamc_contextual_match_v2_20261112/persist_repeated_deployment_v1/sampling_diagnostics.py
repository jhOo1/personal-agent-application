"""Check request integrity and aggregate output variation across saved deployments."""
from collections import Counter, defaultdict
import json
from pathlib import Path

RUN = Path("runs/qamc_contextual_match_v2_20261112") / Path(__file__).parent.name


def deployment_variation(rows):
    groups = defaultdict(list)
    keys = set()
    for row in rows:
        key = row["uid"], row["method"], row["draw"]
        if key in keys:
            raise ValueError("Repeated deployment row")
        keys.add(key)
        groups[row["category"], row["method"], row["uid"]].append(row)
    aggregates = defaultdict(Counter)
    for (track, method, _), batch in groups.items():
        tally = aggregates[f"{track}/{method}"]
        tally["tasks"] += 1
        tally["answer_available"] += sum(bool(row["answer"]) for row in batch)
        if len(batch) == 1:
            continue
        for field in ("branch", "selected_sha256", "answer"):
            if field != "answer" and method != "SELECTED_GEPA":
                continue
            values = [row.get(field) for row in batch]
            if all(values):
                tally[f"{field}_complete"] += 1
                tally[f"{field}_varied"] += len(set(values)) > 1
    return aggregates


def receipts(ledger):
    stages = defaultdict(Counter)
    for call in ledger:
        unit = call["unit"]
        knob, stage = unit["stage"].split("_", 1)
        tally = stages[f"{knob}/{stage}"]
        if call.get("automatic_retries") != 0:
            raise ValueError("Unexpected retry receipt")
        tally[call["status"]] += 1
        if call.get("error"):
            tally[f"error/{call['error']}"] += 1
        if (tokens := (call.get("usage") or {}).get("total_tokens")) is None:
            tally["unknown_usage"] += 1
        else:
            tally["reported_tokens"] += tokens
    return stages


if __name__ == "__main__":
    result = json.loads((RUN / "RESULTS.json").read_text())
    print(json.dumps({"variation": deployment_variation(result["rows"]),
                      "physical_receipts": receipts(result["ledger"])}, indent=2, sort_keys=True))
