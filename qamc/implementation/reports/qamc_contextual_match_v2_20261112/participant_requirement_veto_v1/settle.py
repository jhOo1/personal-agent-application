"""Audit the full roster, anchor restorations and matched scores without requests."""
from collections import Counter, defaultdict
import json
import sys

from trial import BASE, METHOD, PRIVATE, RUN, actor_wire, archive, prepare, prior, sha, task_packet

sys.path.insert(0, str(BASE / "transactional_reassembly_v1"))
from summarize_reassembly import aligned, measure, paired

ORDINARY, GUARD = prior["ARMS"]
ARMS = (ORDINARY, GUARD, METHOD)


def rating_table(comparisons):
    result = {}
    for name, rows in comparisons.items():
        observed = Counter()
        for _, _, grades in rows:
            if aligned(grades, (GUARD, METHOD)):
                diff = grades[METHOD]["primary"] - grades[GUARD]["primary"]
                observed["win" if diff > 0 else "loss" if diff < 0 else "tie"] += 1
        result[name] = {"assigned": len(rows), "guard_to_veto": observed,
                        "common": paired(rows, ("BASE", *ARMS))}
    return result


def settlement():
    pin, cards, old_audits, old_rows, baseline, _ = prepare()
    if archive.read(PRIVATE / "FROZEN_HASHES.json") != pin:
        raise ValueError("Frozen study drift")
    result = archive.read(PRIVATE / "RESULTS.json")
    outcomes = {r["uid"]: r for r in result["rows"]}
    if set(outcomes) != cards.keys() or len(outcomes) != len(result["rows"]):
        raise ValueError("Allocated root missing or duplicated")
    ranks = {r["uid"]: r for r in archive.read(
        BASE / "rpeval_formal_multi_coverage_v1" / "RPR_RANK_FUSION_AUDIT_300.json")["rows"]}
    sources = {r["uid"]: r["original_sources"] for r in archive.read(
        archive.v41.OUT / "FROZEN.json")["roots"]}
    comparisons = defaultdict(list)
    metrics, rank_rows = defaultdict(Counter), []
    changes = []
    for uid, card in cards.items():
        old = old_audits[uid]["kept"]
        row = result["audit"][uid]
        outcome = outcomes[uid]
        domain, stratum = card["benchmark"], card["stratum"]
        tally = metrics[domain]
        tally["assigned"] += 1
        tally[row["status"]] += 1
        tally["exact_parent_answers"] += outcome["origin"] == "EXACT_PARENT_ACTOR_AND_SCORE"
        tally["restored_sources"] += len(row["restored"])
        tally["roots_with_restoration"] += bool(row["restored"])
        tally["invalid_witnesses"] += row["invalid_witnesses"]
        incl = set(old[GUARD]) | set(row["restored"])
        digest = sha(actor_wire(card, incl))
        if digest in baseline:
            exact = baseline[digest]
            if any(outcome[k] != exact[k] for k in ("answer", "score", "actor_status")):
                raise ValueError("Reused grade does not match the exact wire")
        elif outcome["actor"]["request_sha256"] != digest:
            raise ValueError("New Actor wire does not match the protection rule")
        scores = {"BASE": measure(domain, stratum, card["base_score"])}
        for arm, raw in ((ORDINARY, old_rows[uid, ORDINARY]), (GUARD, old_rows[uid, GUARD]), (METHOD, outcome)):
            scores[arm] = measure(domain, stratum, raw["score"])
        entry = card, {}, scores
        comparisons[domain].append(entry)
        if domain == "PersistBench":
            comparisons[f"{domain}/{stratum}"].append(entry)
        if row["restored"]:
            changes.append({"uid": uid, "restored": len(row["restored"]), "origin": outcome["origin"],
                            "same_answer_as_relevance": outcome["answer"] == old_rows[uid, ORDINARY]["answer"]})
        if domain != "RPEval":
            continue
        original = task_packet(card)["source_evidence"]
        if sources[uid] != original:
            raise ValueError("RPEval source order drift")
        rank = ranks[uid]
        if len(rank["author_labels"]) != len(original):
            raise ValueError("Author label alignment drift")
        removed = set(old[ORDINARY]) - set(old[GUARD])
        rank_c = {s["memory_id"] for i, s in enumerate(original)
                  if rank["policies"]["PAPER_FUSION"]["policy"][i] == "C" and s["memory_id"] in removed}
        for i, source in enumerate(original):
            mid = source["memory_id"]
            if mid in removed:
                label = rank["author_labels"][i]
                tally[f"removed_author_{label}"] += 1
                tally[f"restored_author_{label}"] += mid in row["restored"]
                tally[f"rank_rescued_author_{label}"] += mid in rank_c
        naive = baseline.get(sha(actor_wire(card, set(old[GUARD]) | rank_c)))
        rank_rows.append((card, {}, {"RP_PREDICTED_C": measure(domain, stratum, naive["score"]) if naive else None,
                                    **scores}))
    ledger = result["ledger"]
    logs = []
    for file in RUN.glob("*/visible/*/record.json"):
        record = archive.read(file)
        if sha(archive.read(file.with_name("request.json"))) != record["request_sha256"]:
            raise ValueError("Physical wire fingerprint disagrees")
        logs.append(record)
    signature = lambda r: (r["unit"]["stage"], r["unit"]["root_id"], r["request_sha256"], r["status"])
    if Counter(map(signature, logs)) != Counter(map(signature, ledger)):
        raise ValueError("Physical record ledger mismatch")
    return {"metrics": metrics, "comparisons": rating_table(comparisons), "restorations": changes,
            "rpe_rank_c_comparator": paired(rank_rows, ("BASE", *ARMS, "RP_PREDICTED_C")),
            "physical": len(ledger), "stages": Counter(r["unit"]["stage"] for r in ledger),
            "statuses": Counter(r["status"] for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
            "automatic_retries": sum(r["automatic_retries"] for r in ledger),
            "new_distinct_actor_roots": result["new_distinct_actor_roots"]}


if __name__ == "__main__":
    print(json.dumps(settlement(), indent=2, sort_keys=True))
