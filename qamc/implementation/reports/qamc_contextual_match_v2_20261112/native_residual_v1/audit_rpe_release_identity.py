"""Verify author multi-roster identity and score existing explicit/implicit pairs."""
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
import json

from qamc.common import sha
from qamc.pa.core import rpeval_public
from compare_ipe_c_external import read

ROOT = Path(__file__).resolve().parents[3]
FORMAL = "rpeval_formal_multi_coverage_v1"
METHODS = ("IPE_C", "RPR_PAPER_FULL")


def identity(row):
    return sha([row["question"], row["persona"], row["intent_type"]])


def unique(rows, key):
    indexed = {key(row): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("Duplicate frozen identity")
    return indexed


def grades(route):
    return (route["ipe_c"]["grade"], route["controls"].get(METHODS[1], {}).get("grade") or {})


def strict(row, score):
    match = score.get("match")
    if match and match["positions"] != len(row["intent_type"]):
        raise ValueError("Stored Match denominator disagrees with the verified author row")
    return match["matched"] if match else None


def summarize():
    manifest = read(f"{FORMAL}/MANIFEST_300.json")
    tasks = read(f"{FORMAL}/PUBLIC_TASKS.json")
    pins = read(f"{FORMAL}/FROZEN_DATA.json")["files"]
    routes = unique(read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"], lambda r: r["uid"])
    indexed = unique(manifest, lambda r: (r["source_file"], r["row_index"]))
    if set(routes) != set(tasks) or set(routes) != {r["uid"] for r in manifest}:
        raise ValueError("Archive rosters do not match")
    sources, buckets = {}, defaultdict(lambda: defaultdict(list))
    summary, cells, format_pairs = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for track in ("explicit", "implicit"):
        cases = [r for r in manifest if r["track"] == f"{track}/multi"]
        path, = {r["source_file"] for r in cases}
        body = (ROOT / path).read_bytes()
        if sha(body) != pins[path]:
            raise ValueError("Released source bytes differ from frozen source")
        data = json.loads(body)
        if len(cases) != len(data) or len(data) != 150:
            raise ValueError("Incomplete track")
        sources[track] = data
        for i, row in enumerate(data):
            card = indexed[path, i]
            uid = card["uid"]
            data_path = card["evaluation_path"]
            frozen_bytes = (ROOT / data_path).read_bytes()
            if (sha(row) != card["native_row_sha256"] or json.loads(frozen_bytes) != row
                    or sha(frozen_bytes) != pins[data_path]
                    or json.loads(json.dumps(asdict(rpeval_public(row, uid, track == "implicit")))) != tasks[uid]):
                raise ValueError(f"Frozen native row or public input changed: {uid}")
            route = routes[uid]
            if (route["source_group"] != card["analysis_group_id"]
                    or route["labels"] not in (None, row["intent_type"])):
                raise ValueError(f"Stored groups or gold differ: {uid}")
            buckets[identity(row)][track].append((row, route))
            counts = summary[track]
            counts.update({"tasks": 1, "author_positions": len(row["intent_type"]),
                           "legacy_uid": bool(card["legacy_same_configuration_uid"]),
                           "missing_route_labels": route["labels"] is None})
            values = [strict(row, m) for m in grades(route)]
            counts.update({"common_tasks": all(v is not None for v in values),
                           "ipe_c_missing": values[0] is None, "rp_missing": values[1] is None,
                           "both_missing": all(v is None for v in values)})
            if all(v is not None for v in values):
                counts.update(dict(zip(METHODS, values)))
                counts["common_positions"] += len(row["intent_type"])
    for members in buckets.values():
        shape = tuple(len(members[t]) for t in ("explicit", "implicit"))
        cells["pairs"][f"{shape[0]}:{shape[1]}_keys"] += 1
        if shape != (1, 1):
            continue
        (row, exp), (_, imp) = (members[t][0] for t in ("explicit", "implicit"))
        intent = row["intent_type"]
        stratum = "contains_C" if "C" in intent else "only_B" if "B" in intent else "all_A"
        cells["pairs"]["unique_matched_keys_across_same_group"] += exp["source_group"] == imp["source_group"]
        values = [strict(row, item) for route in (exp, imp) for item in grades(route)]
        for key in ("all", stratum):
            format_pairs[key]["assigned"] += 1
            if any(v is None for v in values):
                continue
            counts = format_pairs[key]
            counts.update({"four_way_tasks": 1, "positions_each_track": len(intent)})
            counts.update(dict(zip(("explicit_ipec", "explicit_rp", "implicit_ipec", "implicit_rp"), values)))
            counts["same_history_route_decision"] += (exp["old_route"] == "REUSE_RP") == (imp["old_route"] == "REUSE_RP")
    cells["pairs"]["same_index_shared_identity"] = sum(identity(a) == identity(b)
                                                        for a, b in zip(sources["explicit"], sources["implicit"]))
    return {"release": summary, "source_identity_pairs": cells["pairs"], "matched_formats": format_pairs}


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
