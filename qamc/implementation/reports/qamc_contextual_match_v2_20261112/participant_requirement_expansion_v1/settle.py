"""Reconcile the separate-source expansion and report complete and changed comparisons."""
from collections import Counter, defaultdict
import json
import sys

from trial import ARMS, BASE, PRIVATE, RUN, archive, prepare, sha, veto

sys.path.insert(0, str(BASE / "transactional_reassembly_v1"))
from summarize_reassembly import aligned, bounds, measure, paired


def settle():
    pin, cards, _, _ = prepare()
    if archive.read(PRIVATE / "FROZEN.json") != pin:
        raise ValueError("Frozen footprint drift")
    output = archive.read(PRIVATE / "RESULTS.json")
    rows = {(r["uid"], r["method"]): r for r in output["rows"]}
    if len(rows) != len(output["rows"]) or set(output["audits"]) != cards.keys():
        raise ValueError("Duplicate output or unassigned root")
    summary, groups = defaultdict(Counter), defaultdict(list)
    for uid, card in cards.items():
        benchmark, stratum = card["benchmark"], card["stratum"]
        audit = output["audits"][uid]
        tally = summary[benchmark]
        tally["assigned"] += 1
        tally["first_review_" + audit["relevance_status"]] += 1
        root_rows = {arm: rows.get((uid, arm), {}) for arm in ARMS}
        if "retain" in audit:
            kept = (set(audit["retain"]), set(audit["guard"]), set(audit["guard"]) | set(audit["restored"]))
            tally["roots_with_removal"] += bool(audit["removed"])
            tally["roots_with_restoration"] += bool(audit["restored"])
            tally["removed_sources"] += len(audit["removed"])
            tally["restored_sources"] += len(audit["restored"])
            tally["invalid_participant_quotes"] += audit["invalid_proofs"]
            tally["requirements_" + audit["requirement_status"]] += 1
            for arm, selected in zip(ARMS, kept, strict=True):
                if root_rows[arm]["actor"]["request_sha256"] != sha(veto["actor_wire"](card, selected)):
                    raise ValueError("Actor wire is inconsistent with the frozen evidence comparison")
        measured = {"BASE": measure(benchmark, stratum, card["base_score"])}
        for arm, r in root_rows.items():
            measured[arm] = measure(benchmark, stratum, r.get("score"))
            tally[arm + ".answers"] += bool(r.get("answer"))
            tally[arm + ".valid_scores"] += measured[arm] is not None
        item = card, root_rows, measured
        groups[benchmark].append(item)
        groups[f"{benchmark}/{stratum}"].append(item)
        if audit.get("removed"):
            groups[f"{benchmark}/removed"].append(item)
        if audit.get("restored"):
            groups[f"{benchmark}/restored"].append(item)
        if not any(r.get("score_flags") for r in root_rows.values()):
            groups[f"{benchmark}/no_known_flags"].append(item)
    tables = {}
    for name, items in groups.items():
        direction = Counter()
        for _, _, scores in items:
            if aligned(scores, ARMS):
                delta = scores[ARMS[-1]]["primary"] - scores[ARMS[0]]["primary"]
                direction["win" if delta > 0 else "loss" if delta < 0 else "tie"] += 1
        tables[name] = {"assigned": len(items), "common": paired(items, ("BASE", *ARMS)),
                        "veto_vs_relevance": direction,
                        "all_allocated_primary_delta_bound": bounds(items, ARMS[-1], ARMS[0])}
    receipts = []
    for file in RUN.glob("*/visible/*/record.json"):
        record = archive.read(file)
        if sha(archive.read(file.with_name("request.json"))) != record["request_sha256"]:
            raise ValueError("Physical wire mismatch")
        receipts.append(record)
    ledger = output["ledger"]
    key = lambda r: (r["unit"]["stage"], r["unit"]["root_id"], r["request_sha256"], r["status"])
    if Counter(map(key, receipts)) != Counter(map(key, ledger)):
        raise ValueError("Physical ledger mismatch")
    return {"cohorts": summary, "comparisons": tables, "exact_reuse": output["exact_reuse"],
            "physical": len(ledger), "stages": Counter(r["unit"]["stage"] for r in ledger),
            "statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "automatic_retries": sum(r["automatic_retries"] for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(settle(), indent=2, sort_keys=True))
