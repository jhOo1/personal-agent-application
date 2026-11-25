"""Freeze a group-disjoint NRO development roster from eligible archived rows."""
import argparse
from collections import Counter
import json
from pathlib import Path

from baselines import archive, rpe
from qamc.common import sha

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "transactional_reassembly_v1" / "FROZEN.json"
RPE_ROUTES = HERE.parent / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json"
QUOTAS = {
    "RPEval": {"all_A": {True: 1, False: 2}, "B_only": {True: 2, False: 1},
               "contains_C": {True: 3}},
    "BenchPreS": {"communication": {True: 4}},
    "PersistBench": {"cross_domain": {True: 2}, "sycophancy": {True: 3},
                     "beneficial_memory_usage": {True: 2}},
}


def roster():
    own_routes = {r["uid"]: r["old_route"] for r in archive.read(RPE_ROUTES)["rows"]}
    rows = archive.read(SOURCE)["rows"]
    excluded = {row["group"] for row in rows if row["benchmark"] == "RPEval" and row["diagnostic"]}
    rows = [row for row in rows if row["benchmark"] != "RPEval"] + [
        {**row, "uid": uid, "diagnostic": False} for uid, row in rpe().items()
        if row["group"] not in excluded
    ]

    output = []
    for benchmark, strata in QUOTAS.items():
        groups = set()
        for stratum, routes in strata.items():
            for enabled, count in routes.items():
                candidates = sorted(
                    (row for row in rows if row["benchmark"] == benchmark
                     and row["stratum"] == stratum and not row["diagnostic"]
                         and (benchmark != "RPEval" or
                              (own_routes[row["uid"]] == "REUSE_RP") == enabled)),
                    key=lambda r: sha(["nro-v1", benchmark, r["group"], r["uid"]]),
                )
                selected = []
                for row in candidates:
                    if row["group"] in groups:
                        continue
                    selected.append(row)
                    groups.add(row["group"])
                    if len(selected) == count * 2:
                        break
                if len(selected) != count * 2:
                    raise ValueError(f"Insufficient distinct groups for {benchmark}/{stratum}: {len(selected)}")
                for index, row in enumerate(selected):
                    uid = row["uid"]
                    output.append({
                        "uid": uid, "benchmark": benchmark, "stratum": stratum,
                        "group": row["group"], "split": "search" if index % 2 == 0 else "confirmation",
                        "baseline_answer_sha256": row["baseline_answer_sha256"],
                        "history_enabled": enabled,
                    })
    return {"source_sha256": sha(SOURCE.read_bytes()), "rows": output}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check"))
    action = parser.parse_args().action
    result = roster()
    path = HERE / "ROSTER.json"
    if action == "freeze":
        with path.open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    elif archive.read(path) != result:
        raise ValueError("Roster drift")
    counts = Counter((r["benchmark"], r["split"], r["history_enabled"]) for r in result["rows"])
    for key, count in sorted(counts.items()):
        print(*key, count)
