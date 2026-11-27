"""Replay which proposed uses reached the Actor and where the pilot lost coverage."""
from collections import Counter, defaultdict
import json

from controller import opportunity
from qamc.common import sha
from run_car import RUN, archive, check_wire, donor_wire, preflight, probe, source


def root_counts(results, cards, opportunity_units, opportunity_receipts, donor_units, final_units, bridge,
                rpe_labels):
    """Use task metadata and scores only after execution."""
    counts = defaultdict(Counter)
    stages = {}
    for name, entries in (("opportunity", opportunity_units), ("donor", donor_units), ("final", final_units)):
        stage = {}
        for row in entries:
            unit = row["unit"]
            key = (unit["root_id"], unit["method"])
            if key in stage:
                raise ValueError(f"Duplicate registered {name} job")
            stage[key] = row["request"]
        stages[name] = stage

    results_by_root = defaultdict(list)
    for r in results["rows"]:
        results_by_root[r["uid"]].append(r)
    for card in cards:
        uid, b = card["root"]["uid"], card["benchmark"]
        count = counts[b]
        count["assigned"] += 1
        if (uid, "SHARED") not in stages["opportunity"]:
            count["absent_opportunity_request"] += 1
            continue
        job = stages["opportunity"][uid, "SHARED"]
        receipt, raw = opportunity_receipts[uid, "SHARED"]
        if receipt is None or receipt["request_sha256"] != sha(job):
            raise ValueError("Opportunity absent from settled journal")
        if receipt["status"] != "OK":
            count["opportunity_delivery_failed"] += 1
            continue
        sources = {s["memory_id"]: s["text"] for s in card["root"]["original_sources"]}
        try:
            proposed = opportunity(raw, sources)
        except (ValueError, TypeError):
            count["proposal_contract_failed"] += 1
            continue
        if proposed is None:
            count["no_intervention"] += 1
        else:
            quoted = {r["id"] for r in proposed["evidence"]}
            count["proposed_action"] += 1
            count["actions_with_source_support"] += bool(quoted)
            count["cited_source_positions"] += len(quoted)
            if b == "RPEval":
                labels = rpe_labels[uid]
                if len(labels) != len(sources):
                    raise ValueError("Author labels do not align with original source order")
                for s, label in zip(sources, labels, strict=True):
                    count[f"available_label_{label}"] += 1
                    count[f"cited_label_{label}"] += s in quoted
            try:
                wire = check_wire(donor_wire(card, proposed, bridge))
            except (ValueError, TypeError):
                count["donor_projection_failed"] += 1
                continue
            if wire == card["T"]:
                count["donor_wire_is_empty_endpoint"] += 1
            elif wire == card["H"]:
                count["donor_wire_is_full_endpoint"] += 1
            else:
                count["donor_wire_differs_from_both_endpoints"] += 1
            saved = stages["donor"].get((uid, "D"))
            if saved and saved != wire:
                raise ValueError("Registered donor request does not match the proposal")
            if saved:
                count["registered_distinct_donor"] += 1
        final = stages["final"].get((uid, "WHOLE"))
        if final is None:
            count["valid_proposal_but_no_control_packet"] += 1
            continue
        count["reached_matched_control_packet"] += 1
        u = json.loads(final["messages"][1]["content"])
        if u["opportunity"] != proposed:
            raise ValueError("Proposal changed between raw response and final payload")
        donor = "".join(u["candidates"].get("D", []))
        count["unique_donor_answer_available"] += bool(donor) and all(
            donor != "".join(u["candidates"][k]) for k in ("F", "T", "H"))
        car, = [row for row in results_by_root[uid] if row["method"] == "COMMIT"]
        if car.get("outcome") == "COMMITTED":
            count["copy_commits"] += 1
            count[f"copy_from_{car['donor']}"] += 1
    return counts


def read_jobs(stage):
    p = RUN / (stage + "_MANIFEST.json")
    return probe.read(p)["units"] if p.exists() else []


if __name__ == "__main__":
    plan, cards = preflight()
    if probe.read(RUN / "FROZEN.json") != plan:
        raise ValueError("Cannot trace an unfrozen or changed pilot")
    results = probe.read(RUN / "RESULTS.json")
    probe.RUN = probe.OUT = RUN
    labels = {r["uid"]: r["labels"] for r in archive.read(
        archive.BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    bridge = source.PersistAuthorBridge(source.previous.parent.AUTHOR)
    print(json.dumps(root_counts(results, cards, read_jobs("Opportunity"), probe.stage_receipts("Opportunity"),
                                 read_jobs("Donor"), read_jobs("Final"), bridge, labels),
                     indent=2, sort_keys=True))
