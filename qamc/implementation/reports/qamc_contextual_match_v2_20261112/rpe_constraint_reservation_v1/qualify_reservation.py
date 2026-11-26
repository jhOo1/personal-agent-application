"""Freeze an inference-only one-slot rule and audit source exposure separately."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from qamc.common import sha
from qamc.pa.core import digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORTS = HERE.parent
FORMAL = REPORTS / "rpeval_formal_multi_coverage_v1"
RUNS = ROOT / "runs" / REPORTS.name
RUN = RUNS / HERE.name


def read(path):
    return json.loads(path.read_text())


def plan_case(records, gate):
    all_ids = [f"M{i}" for i in range(len(records))]
    if [r["memory_id"] for r in records] != all_ids or len(gate["scores"]) != len(records):
        raise ValueError("Original source ordering changed")
    kept = gate["threshold"]
    if len(kept) != len(set(kept)) or not set(kept) <= set(all_ids):
        raise ValueError("Unexpected gate output")
    omitted = [i for i, sid in enumerate(all_ids) if sid not in kept]
    nominated = [i for i in omitted if records[i]["ipe_order"][0] == "C" and records[i]["policy"] == "C"]
    if not kept or not nominated:
        return {"base": kept, "reserved_add": None, "top_add": None}
    scores = gate["scores"]
    reserve = min(nominated, key=lambda i: (records[i]["mle_order"][0] != "C", -scores[i], i))
    top = min(omitted, key=lambda i: (-scores[i], i))
    return {"base": kept, "reserved_add": all_ids[reserve], "top_add": all_ids[top]}


def select():
    path = RUNS / "rpe_memgate_language_wide_v1"
    local = read(path / "RESULTS.json")
    pin = read(path / "FROZEN.json")
    manifest = read(FORMAL / "MANIFEST_300.json")
    cases = {r["uid"]: r for r in manifest}
    raw = {r["uid"]: r for r in read(FORMAL / "RESULT_ROWS.json") if r["method"] == "RPR_PAPER_FULL"}
    rank_rows = read(FORMAL / "RPR_RANK_FUSION_AUDIT_300.json")["rows"]
    rank = {r["uid"]: r["policies"]["PAPER_FUSION"] for r in rank_rows}
    if local.keys() != set(pin["uids"]) or any(r["independent_confirmation"] for r in cases.values()):
        raise ValueError("Unexpected exposure allocation")
    plans = {}
    for uid in pin["uids"]:
        observation = local[uid]
        if observation["status"] != "OK":
            continue
        saved = raw[uid]
        packet = json.loads(saved["actor_request"]["messages"][1]["content"])
        records = saved["aggregation"]
        if (
            saved["actor_status"] != "OK" or not rank[uid]["archived_actor_wire_unchanged"]
            or saved["actor_request_sha256"] != sha(saved["actor_request"])
            or saved["actor_request_sha256"] != rank[uid]["actor_request_sha256"]
            or [{"memory_id": r["memory_id"], "policy": r["policy"]} for r in records]
            != packet["preference_use_policy"]
        ):
            raise ValueError("Frozen generations and rank rows disagree")
        plans[uid] = plan_case(records, observation["modes"]["EN"])
    out = {
        "plans": plans, "pins": {"plan_sha256": sha(plans), "local_results_sha256": sha(local),
                                "source_preference_protocol_sha256": sha(rank),
                                "code_sha256": sha(Path(__file__).read_bytes()),
                                "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes())},
    }
    path = RUN / "SELECTION_PRIVATE.json"
    with path.open("x") as stream:
        json.dump(out, stream, ensure_ascii=False)
    print(json.dumps({"plans": len(plans), "allocated": len(cases), "pins": out["pins"]}, sort_keys=True))


def diagnose():
    result = read(RUN / "SELECTION_PRIVATE.json")
    rows = result["plans"]
    if result["pins"]["plan_sha256"] != sha(rows):
        raise ValueError("Selector output changed before evaluation")
    cases = {r["uid"]: r for r in read(FORMAL / "MANIFEST_300.json")}
    past = read(RUNS / "rpe_memgate_equal_count_answer_v1/FROZEN.json")["rows"]
    summary = defaultdict(Counter)
    group_deltas = defaultdict(Counter)
    for uid, item in rows.items():
        case = cases[uid]
        reference = read(ROOT / case["evaluation_path"])
        labels = reference["intent_type"]
        if digest(reference) != case["evaluation_hash"] or not labels or set(labels) - set("ABC"):
            raise ValueError("Unexpected evaluator reference")
        for subset in ("all", "previous_trial" if uid in past else "other_exposed"):
            stats = summary[subset]
            stats.update(eligible=1, originally_empty=not item["base"], all_a=set(labels) == {"A"})
            chosen, top = item["reserved_add"], item["top_add"]
            if not chosen:
                continue
            left, right = labels[int(chosen[1:])], labels[int(top[1:])]
            stats.update(triggered=1, changed_vs_top=chosen != top,
                         triggered_all_a=set(labels) == {"A"},
                         **{f"reserved_{left}": 1, f"top_{right}": 1})
            if chosen != top:
                for key, score in (("C", lambda v: v == "C"), ("BC", lambda v: v != "A")):
                    group_deltas[subset, key][case["analysis_group_id"]] += int(score(left)) - int(score(right))
    return {"plans": len(rows), "summary": summary,
            "group_comparison_among_different_choices": {
                "/".join(key): {"groups": len(d), "net_reservation_wins": sum(x>0 for x in d.values()),
                               "net_reservation_losses": sum(x<0 for x in d.values())}
                for key, d in group_deltas.items()},
            "selection_sha256": sha(rows), "new_cloud_requests": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("select", "diagnose"))
    if parser.parse_args().action == "select":
        select()
    else:
        print(json.dumps(diagnose(), indent=2, sort_keys=True))
