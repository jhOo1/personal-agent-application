"""Compare actual deployment cost, with scoring cost reported separately."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median

RUN = Path("runs/qamc_contextual_match_v2_20261112") / Path(__file__).parent.name
ACTIVE = "SELECTED_GEPA"
CONTROLS = ("PB_RUBRIC", "PB_GEPA")
METHODS = (ACTIVE, *CONTROLS)
REQUIRED = {ACTIVE: {"Route", "Select", "SelectedActor"},
            **{method: {method} for method in CONTROLS}}


def summarize(checkpoints):
    rows = [r for cp in checkpoints for r in cp["rows"]]
    ledger = [r for cp in checkpoints for r in cp["ledger"]]
    call_groups = defaultdict(list)
    traced = defaultdict(dict)
    seen = set()
    for call in ledger:
        unit = call["unit"]
        wave, stage = unit["stage"].split("_", 1)
        coord = (wave, stage, unit["root_id"], unit["method"])
        if coord in seen or call.get("automatic_retries") != 0:
            raise ValueError("Unexpected duplicate attempt or retry")
        seen.add(coord)
        if stage == "Judge":
            call_groups["SEPARATE_JUDGE"].append(call)
            continue
        method = unit["method"]
        if stage not in REQUIRED[method]:
            raise ValueError(f"Unknown method/stage combination: {method}/{stage}")
        traced[int(wave.removeprefix("Draw")), unit["root_id"], method][stage] = call
        call_groups[method].append(call)

    summary = {}
    for method in (*METHODS, "SEPARATE_JUDGE"):
        calls = call_groups[method]
        time = [c["elapsed_seconds"] for c in calls if isinstance(c.get("elapsed_seconds"), (int, float))]
        summary[method] = {
            "physical_calls": len(calls),
            "statuses": Counter(c["status"] for c in calls),
            "timed_call_seconds_sum": round(sum(time), 4),
            "timed_calls": len(time),
            "median_timed_call_seconds": median(time) if time else None,
            "reported_tokens": sum((c.get("usage") or {}).get("total_tokens", 0) for c in calls),
            "unknown_tokens_calls": sum("total_tokens" not in (c.get("usage") or {}) for c in calls),
        }

    for method in METHODS:
        method_rows = [row for row in rows if row["method"] == method]
        completed_traces = []
        for row in method_rows:
            trace = traced[row["draw"], row["uid"], method]
            if (row["answer"] and trace.keys() == REQUIRED[method]
                    and all(c["status"] == "OK" and isinstance(c.get("elapsed_seconds"), (int, float))
                            for c in trace.values())):
                completed_traces.append(sum(c["elapsed_seconds"] for c in trace.values()))
        summary[method].update({
            "allocated_answers": len(method_rows),
            "completed_answers": sum(bool(r["answer"]) for r in method_rows),
            "scored_answers": sum(r["score"] is not None for r in method_rows),
            "physically_traced_success_paths": len(completed_traces),
            "median_sum_of_call_seconds_on_traced_paths": median(completed_traces) if completed_traces else None,
        })
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waves", type=int, choices=(1, 2, 3))
    args = parser.parse_args()
    data = [json.loads((RUN / f"DRAW{n}.json").read_text()) for n in range(1, args.waves + 1)]
    execution = json.loads((RUN / "EXECUTION.json").read_text())
    if any(cp["identity"] != execution for cp in data):
        raise ValueError("Checkpoint identity differs from the frozen execution")
    print(json.dumps(summarize(data), indent=2, sort_keys=True))
