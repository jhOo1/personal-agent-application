"""Join exact author source labels after inference; do not generate or change a grade."""
import argparse
from collections import Counter, defaultdict
import json

from qamc.pa.core import digest
from trial import BASE, PRIVATE, archive, prepare, sha, task_packet


def source_labels(cards):
    formal = BASE / "rpeval_formal_multi_coverage_v1"
    rpe = {row["uid"]: row for row in archive.read(formal / "RPR_RANK_FUSION_AUDIT_300.json")["rows"]}
    original = {}
    for row in archive.read(formal / "RESULT_ROWS.json"):
        uid = row["uid"]
        if uid not in cards or row["method"] != archive.v41.RP:
            continue
        wire = row["actor_request"]
        fused = rpe[uid]["policies"]["PAPER_FUSION"]["actor_request_sha256"]
        if sha(wire) != row["actor_request_sha256"] or sha(wire) != fused:
            raise ValueError("RPEval history request does not match the archived rank")
        original[uid] = json.loads(wire["messages"][1]["content"])["source_evidence"]
    bench, _, _ = archive.transfer.context("BenchPreS")
    results = {}
    for uid, card in cards.items():
        sources = task_packet(card)["source_evidence"]
        benchmark = card["benchmark"]
        if benchmark == "RPEval":
            if sources != original[uid] or len(sources) != len(rpe[uid]["author_labels"]):
                raise ValueError("RPEval exact source units or order do not match")
            aligned = dict(zip((s["memory_id"] for s in sources), rpe[uid]["author_labels"], strict=True))
        elif benchmark == "BenchPreS":
            case = bench[uid]
            attributes = archive.read(archive.transfer.bench.ROOT / case["evaluation_path"])
            if digest(attributes) != case["evaluation_hash"]:
                raise ValueError("BenchPreS evaluator input hash mismatch")
            by_text = dict(zip(attributes["preference_attribute"], attributes["preference_label"], strict=True))
            aligned = {s["memory_id"]: str(by_text[s["text"]]) for s in sources if s["text"] in by_text}
        else:
            aligned = {}
        results[uid] = aligned
    return results


def audit(preflight=False):
    pin, cards, _, _ = prepare()
    if archive.read(PRIVATE / "FROZEN.json") != pin:
        raise ValueError("Frozen roster drift")
    labels = source_labels(cards)
    outcome = {} if preflight else archive.read(PRIVATE / "RESULTS.json")["audits"]
    counts = defaultdict(Counter)
    restorations = Counter()
    for uid, card in cards.items():
        benchmark = card["benchmark"]
        by_id = labels[uid]
        summary = counts[benchmark]
        summary["roots"] += 1
        summary["labelled_records"] += len(by_id)
        summary["unknown_label_records"] += len(task_packet(card)["source_evidence"]) - len(by_id)
        audit_row = outcome.get(uid, {})
        removed = set(audit_row.get("removed", []))
        restored = set(audit_row.get("restored", []))
        if restored - removed:
            raise ValueError("A record outside the guard removals was restored")
        if audit_row and "retain" not in audit_row:
            summary["unusable_relevance_reviews"] += 1
        if "retain" in audit_row:
            ids = {s["memory_id"] for s in task_packet(card)["source_evidence"]}
            retained = set(audit_row["retain"])
            compiled = set(audit_row["guard"]) | restored
            if not compiled <= retained <= ids or set(audit_row["guard"]) != retained - removed:
                raise ValueError("Recorded evidence policies are inconsistent")
            transitions = (("original_candidates", ids), ("outside_relevance", ids - retained),
                           ("retained_relevance", retained), ("removed", removed),
                           ("restored", restored), ("still_removed", removed - restored),
                           ("visible_after_veto", compiled))
            for key, members in transitions:
                for mid in members:
                    summary[f"{key}/{by_id.get(mid, 'UNKNOWN')}"] += 1
        if restored:
            restorations[benchmark] += 1
    return {"preflight_only": preflight, "counts": counts, "restoration_roots": restorations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.preflight), indent=2, sort_keys=True))
