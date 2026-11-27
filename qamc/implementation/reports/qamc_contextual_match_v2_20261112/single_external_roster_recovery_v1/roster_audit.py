"""Inventory development-only external answers by release path, track and original row."""
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
LEGACY = HERE.parents[3] / "qamc" / "reports"
PREP = BASE / "independent_test_set_preparation_v1"


def read(path):
    return json.loads(path.read_bytes())


def key(row):
    return row["source_file"], row["track"], row["row_index"]


def roster():
    census = [r for r in read(PREP / "CENSUS.json")["catalog"] if r["benchmark"] == "rpeval"]
    by_id = {r["source_id"]: r for r in census}
    blocked = {r["audit_group_id"] for r in read(PREP / "RESERVED_IDENTITIES.json")["native_cases"]
               if r["benchmark"] == "rpeval"}
    blocked.update(r["audit_group_id"] for r in census if r["group_has_historical_reservation"])
    blocked.update(g for rnd in read(PREP / "NEAR_SCREEN.json")["rounds"]
                   if rnd["benchmark"] == "rpeval" for g in rnd["newly_blocked_groups"])
    blocked.update(r["census_group_id"] for r in read(BASE / "rpeval_formal_multi_coverage_v1/PLAN.json")["cases"])
    blocked.update(by_id[r["source_id"]]["audit_group_id"]
                   for r in read(BASE / "paper_baseline_validation_156_v1/PLAN.json")["cases"]
                   if r.get("source_id") in by_id)
    rows = [r for r in census if r["population"] == "official" and r["track"].endswith("/single")
            and r["recorded_exact_group_exposure"] and r["group_has_declared_allocation"]
            and r["audit_group_id"] not in blocked]
    direct = {key(r): r for r in rows if r["declared_allocation_files"]}
    assert len(direct) == sum(bool(r["declared_allocation_files"]) for r in rows)
    counts = Counter()
    verified = {}
    for folder in ("qamc_rpreasoner_paper", "qamc_bounded_external_20261109"):
        cases = read(LEGACY / folder / "PLAN.json")["cases"]
        selected = [c for c in cases if c["benchmark"] == "rpeval" and key(c) in direct]
        counts[folder + "_exact_row"] = len(selected)
        counts[folder + "_explicit_development"] = sum(c["independent_confirmation"] is False and
            "DEVELOPMENT" in c["allocation_cohort"] for c in selected)
        for c in selected:
            if c["independent_confirmation"] is False and "DEVELOPMENT" in c["allocation_cohort"]:
                source = LEGACY.parent / c["source_file"]
                assert sha256(source.read_bytes()).hexdigest() == c["source_sha256"]
                verified[key(c)] = c
    return rows, direct, counts, verified


def inventory():
    rows, direct, counts, verified = roster()
    details = read(LEGACY / "qamc_des2gen/ALL_NINE_CASE_DETAILS.json")
    matched = Counter()
    for row in details:
        c = row["case"]
        if c["benchmark"] != "rpeval" or key(c) not in verified or c["independent_confirmation"] is not False:
            continue
        assert all(c[k] == verified[key(c)][k] for k in ("uid", "source_sha256", "public_hash", "evaluation_hash"))
        methods = ("RPR_PAPER_XBENCH", "D2G_PAPER_ADAPT")
        arms = [row["methods"][m] for m in methods]
        if all(a["strict"] is True and a["answer"] and a["score"].get("total") == 1 for a in arms):
            matched["common_strict_single_cases"] += 1
            for m, a in zip(methods, arms):
                matched[m] += a["score"]["matched"]
        counts["nine_method_archive_exact_rows"] += 1
        for m in ("RPR_PAPER_XBENCH", "D2G_PAPER_ADAPT", "MEMADAPTER_FULL"):
            record = row["methods"].get(m, {})
            counts[m + "_nonempty_answer"] += int(bool(record.get("answer")))
    return {"allocated_exposed_rows": len(rows), "direct_allocation_rows": len(direct),
            "direct_groups": len({r["audit_group_id"] for r in direct.values()}),
            "inspected_archives": dict(counts), "legacy_paired_scores": dict(matched)}


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, sort_keys=True))
