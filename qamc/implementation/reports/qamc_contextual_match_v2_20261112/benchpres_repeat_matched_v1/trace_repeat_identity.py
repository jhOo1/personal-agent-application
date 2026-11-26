"""Check whether settled BenchPreS draws are distinct transport and answer observations."""

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from heapq import heappop, heappush
import json

from audit_qamc_benchpres_repeat_costs import audit as costs
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import sha
from trace_misuse import jobs, run


def peak_overlap(starts, ends):
    pending = []
    peak = 0
    for start, end in zip(starts, ends, strict=True):
        while pending and pending[0] <= start:
            heappop(pending)
        if end > start:
            heappush(pending, end)
        peak = max(peak, len(pending))
    return peak


def audit(waves):
    reconciled = costs(waves)
    answers = defaultdict(list)
    records = []
    origins = defaultdict(Counter)
    models = defaultdict(Counter)
    for wave in waves:
        area = run.RUN / f"wave-{wave}"
        for stage, name in (("generation", "ACTOR"), ("grading", "JUDGE")):
            units = jobs(area, name)
            output_paths = {path.stem: path for path in (area / stage / "outputs").glob("*.json")}
            if set(output_paths) != {sampling_key(job["unit"]) for job in units.values()}:
                raise ValueError("Logical output roster differs from its manifest")
            records.extend(run.read(path) for path in
                           (area / stage / "execution" / "visible").glob("*/record.json"))
            for (uid, method, draw, _), job in units.items():
                fingerprint = sampling_key(job["unit"])
                output = run.read(output_paths[fingerprint])
                if output["unit"] != job["unit"] or output["request_sha256"] != sha(job["request"]):
                    raise ValueError("Logical output differs from the frozen request")
                origins[stage][output.get("origin", "UNKNOWN")] += 1
                if stage == "generation" and output["status"] == "OK" and output["answer"]:
                    answers[uid, method].append((draw, sha(output["answer"])))

    records.sort(key=lambda row: row["started_unix"])
    if len(records) != sum(stage["calls"] for method in reconciled["methods"].values()
                           for stage in method.values()):
        raise ValueError("Reconciled physical call counts differ")
    starts = [row["started_unix"] for row in records]
    ends = [row["started_unix"] + row["elapsed_seconds"] for row in records]
    for row in records:
        if row["status"] == "OK":
            unit = row["unit"]
            surfaced = ",".join(row.get("returned_models") or []) or "UNKNOWN"
            stage = "actor" if unit["stage"] == "Actor" else "judge"
            models[f"{unit['method']}/{stage}"].update([surfaced])
    cooldowns = []
    for row, end in zip(records, ends, strict=True):
        if row["status"] == "OK":
            continue
        following = bisect_left(starts, end)
        if following < len(starts):
            cooldowns.append(starts[following] - end)
    unique = defaultdict(Counter)
    for (_, method), observed in answers.items():
        if len(observed) == len(run.REPEATS):
            if {draw for draw, _ in observed} != set(run.REPEATS):
                raise ValueError("Unexpected repeated draw identity")
            hashes = len({value for _, value in observed})
            unique[method].update({f"{hashes}_distinct_of_{len(run.REPEATS)}": 1})
    return {
        "waves": waves, "physical_calls": len(records), "logical_output_origins": origins,
        "reported_model_alias_on_success": models, "complete_actor_cells_by_unique_texts": unique,
        "recorded_minimum_start_gap_seconds": min(b - a for a, b in zip(starts, starts[1:])),
        "recorded_max_overlap": peak_overlap(starts, ends),
        "observed_next_start_after_failed_response_seconds": cooldowns,
        "model_calls_added": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", nargs="+", type=int, choices=range(6), required=True)
    args = parser.parse_args()
    print(json.dumps(audit(sorted(set(args.wave))), indent=2, sort_keys=True))
