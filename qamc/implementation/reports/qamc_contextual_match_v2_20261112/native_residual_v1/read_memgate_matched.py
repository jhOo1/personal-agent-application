"""Score previously published MemGate comparisons on exact common panels."""
from collections import Counter, defaultdict
import json

from audit_persist_switch_receipts import HERE, load, normalized, read

RPE_METHODS = ("IPE_C", "MG_RELEASE", "RPR_PAPER_FULL", "GEPA_SELECTED_BOUNDS")
PB_METHODS = ("SELECTED_GEPA", "SELECTED_RUBRIC")


def rpe():
    result = read(HERE / "rpe_memgate_bridge_v1/RESULTS.json")
    pair = {(r["uid"], r["method"]): r["native_fields"] for r in read(
        HERE.parent / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json") if r["method"] in RPE_METHODS[2:]}
    by_slice = defaultdict(Counter)
    for r in result["rows"]:
        uid, labels = r["uid"], r["labels"]
        bucket = "contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"
        scores = (r["base_score"], r["score"], *(pair.get((uid, m)) for m in RPE_METHODS[2:]))
        for opponent in ("all_four", *RPE_METHODS):
            if opponent == "all_four":
                methods, cells = RPE_METHODS, scores
            elif opponent in ("IPE_C", *RPE_METHODS[2:]):
                i = RPE_METHODS.index(opponent)
                methods, cells = ("MG_RELEASE", opponent), (scores[1], scores[i])
            else:
                continue
            for k in ("all", bucket):
                total = by_slice[opponent, k]
                total["assigned"] += 1
                if not all(s and s.get("match") for s in cells):
                    continue
                if {s["match"]["positions"] for s in cells} != {len(labels)}:
                    raise ValueError(f"Wrong strict denominator: {uid}")
                total.update(common=1, positions=len(labels))
                for method, cell in zip(methods, cells):
                    field_values = {"match": cell["match"]["matched"]}
                    for f in ("OPB", "UPB", "FM", "full_match"):
                        if all(type(s.get(f)) in (bool, int) for s in cells):
                            field_values[f] = cell[f]
                    total.update({f"{method}/{f}": value for f, value in field_values.items()})
    ledger = result["ledger"]
    return {"slices": {"/".join(k): v for k, v in by_slice.items()},
            "statuses": Counter(row["status"] for row in ledger),
            "tokens": sum((row.get("usage") or {}).get("total_tokens") or 0 for row in ledger),
            "unknown_usage": sum((row.get("usage") or {}).get("total_tokens") is None for row in ledger)}


def fixed_route():
    rows = read(HERE / "rpe_memgate_bridge_v1/RESULTS.json")["rows"]
    routes = {r["uid"]: r["old_route"] for r in read(
        HERE.parent / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    totals, missing = defaultdict(Counter), Counter()
    for row in rows:
        uid, labels = row["uid"], row["labels"]
        route = routes[uid]
        if route not in {"REUSE_RP", "REUSE_DRAFT", "REUSE_ORIGINAL_TASK_ONLY_STATE", "NEW_DRAFT"}:
            missing["unknown_route"] += 1
            continue
        old = row["base_score"] or {}
        on = route == "REUSE_RP"
        new = (row["score"] or {}) if on else old
        if not old.get("match") or not new.get("match"):
            missing["missing_on" if on else "missing_off"] += 1
            continue
        if {s["match"]["positions"] for s in (old, new)} != {len(labels)}:
            raise ValueError(f"Wrong strict denominator: {uid}")
        name = "ON" if on else "OFF"
        stratum = "contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"
        base, alternative = old["match"]["matched"], new["match"]["matched"]
        for key in ("all", name, stratum, f"{name}/{stratum}"):
            totals[key].update(n=1, positions=len(labels), base=base, alternative=alternative)
            for f in ("OPB", "UPB", "FM"):
                if all(type(cell.get(f)) is int for cell in (old, new)):
                    totals[key].update({f"base_{f}": old[f], f"alternative_{f}": new[f]})
    return {"slices": totals, "missing": missing}


def persist():
    place = HERE.parent / "memgate_persistbench_v1"
    register = {r["uid"]: r for r in read(place / "FROZEN.json")["cases"]}
    prior = {r["uid"]: r for r in read(place / "RESULTS.json")["rows"]}
    wires = {r["unit"]["root_id"]: r["request"] for r in read(place / "PersistJudge_MANIFEST.json")["units"]}
    totals, visited = defaultdict(Counter), set()
    for stage in ("selected_gepa_expansion_v1", "persist_performance_v1"):
        rows, judge = load(stage)
        for (uid, method), row in rows.items():
            if uid not in register or method not in PB_METHODS:
                continue
            if (uid, method) in visited:
                raise ValueError("Repeated task in selected panels")
            visited.add((uid, method))
            other, category = prior[uid], row["category"]
            case = register[uid]
            if (category, row["group"]) != (case["category"], case["group"]):
                raise ValueError(f"Task identity drift: {uid}")
            cells = [totals[scope, method, part] for scope in (stage, "both_panels")
                     for part in (category, "all")]
            for total in cells:
                total["overlap"] += 1
            if not (row["score"] and other["score"]):
                continue
            if normalized(judge[uid, method], row["answer"]) != normalized(wires[uid], other["answer"]):
                raise ValueError(f"Scoring envelope mismatch: {uid}")
            key = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
            for total in cells:
                total.update(common=1, memgate=not other["score"][key], candidate=not row["score"][key])
    return {"/".join(k): v for k, v in totals.items()}


if __name__ == "__main__":
    print(json.dumps({"persist": persist(), "rpe": rpe(), "exploratory_fixed_route": fixed_route()}, indent=2))
