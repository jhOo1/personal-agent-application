"""Census of appropriate non-bold attributes on all paired saved BenchPreS answers."""

import argparse
from collections import Counter, defaultdict
import json

from analyze_reflection import agreement, archive_references
from freeze_reflection import PRIVATE, inventory, token, write_frozen
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.bace.runtime import runner_lock
from qamc.common import canonical, sha
from qamc.transport_helpers import read_reference
from qamc_benchpres_matched_fieldwise_audit import delta_bounds
import run_reflection_gpt41 as sample
from run_reflection_model import PROMPT
from trace_nonbold import BOLD
from trace_misuse import run


ROOT = PRIVATE / "gpt41_nonbold_census"
PROTOCOL = {**sample.PROTOCOL, "namespace": "benchpres_frozen_reflection_v1/gpt41_nonbold_census",
            "concurrency": 1}


def prepare(service):
    draws, summary = inventory()
    idx = defaultdict(dict)
    for item in draws:
        idx[item["uid"], item["draw"]][item["method"]] = item
    prior = {}
    for job in sample.plan_from_source()["units"]:
        row, label = sample.receipt(job)
        if row and row["reference_config_sha256"] == service and label is not None:
            prior[sha(job["request"])] = label
    seed = bytes.fromhex((PRIVATE / "SEED_PRIVATE").read_text())
    refs = archive_references()
    jobs, cached, slots = {}, {}, []
    paired_answer_slots = 0
    for (uid, draw), arms in sorted(idx.items(), key=lambda row: token(seed, "census-order", *row[0])):
        available = all(arms[m]["answer"] is not None for m in run.METHODS)
        for i, (attribute, appropriate) in enumerate(refs[uid]):
            if not appropriate or BOLD.search(attribute):
                continue
            paired_answer_slots += int(available)
            slot = {"pair": token(seed, "census-slot", uid, draw, i)[:24],
                    "was_original_common": all(arms[m]["old_strict_score"] for m in run.METHODS),
                    "available_answers": available, "arms": {}}
            for method in run.METHODS:
                arm = arms[method]
                entry = {"request_sha256": None,
                         "original": arm["attributes"][i]["follow"] if arm["answer"] is not None else None}
                slot["arms"][method] = entry
                if not available:
                    continue
                payload = {"attribute": attribute, "answer": arm["answer"]}
                request = {"model": PROTOCOL["model"], "stream": True,
                           "stream_options": {"include_usage": True}, **PROTOCOL["stages"]["Reflection"],
                           "messages": [{"role": "system", "content": PROMPT},
                                        {"role": "user", "content": canonical(payload)}]}
                fingerprint = sha(request)
                entry["request_sha256"] = fingerprint
                if fingerprint in prior:
                    cached[fingerprint] = prior[fingerprint]
                elif fingerprint not in jobs:
                    unit = {"protocol_sha256": sha(PROTOCOL), "root_id": fingerprint, "method": "reflection",
                            "stage": "Reflection", "replicate": 0}
                    jobs[fingerprint] = {"unit": unit, "request": request}
            slots.append(slot)
    if len({a["pair"] for a in slots}) != len(slots):
        raise ValueError("Frozen non-bold slot IDs are duplicated")
    return {"protocol": PROTOCOL, "units": list(jobs.values()), "cached": cached, "slots": slots,
            "service_sha256": service, "paired_answer_slots": paired_answer_slots,
            "frozen_inventory_sha256": sha(summary)}


def summarize(plan):
    measures = dict(plan["cached"])
    states = Counter()
    tokens = unknown = 0
    for job in plan["units"]:
        row, label = sample.receipt(job, ROOT)
        if row is None:
            continue
        if row["reference_config_sha256"] != plan["service_sha256"]:
            raise ValueError("Different service in census receipt")
        states[row["status"] if row["status"] != "OK" or label else "INVALID_LABEL"] += 1
        usage = (row.get("usage") or {}).get("total_tokens")
        tokens += usage or 0
        unknown += usage is None
        if label is not None:
            measures[sha(job["request"])] = label
    left, right = run.METHODS
    evaluations = defaultdict(list)
    agreement_rows = {m: [] for m in run.METHODS}
    original_common = []
    model_comparable = []
    for slot in plan["slots"]:
        values = {}
        for method, row in slot["arms"].items():
            label = measures.get(row["request_sha256"])
            values[method] = {"yes": 1, "no": 0}.get(label)
            if slot["available_answers"]:
                agreement_rows[method].append((row["original"], values[method]))
        evaluations["all_planned"].append((slot["pair"], values))
        if slot["available_answers"]:
            evaluations["paired_saved_answers"].append((slot["pair"], values))
        if slot["was_original_common"] and all(v is not None for v in values.values()):
            original_common.append({m: slot["arms"][m]["original"] for m in run.METHODS})
            model_comparable.append(values)
    return {"model": PROTOCOL["model"], "frozen_nonbold_allocation": len(plan["slots"]),
            "paired_answer_slots": plan["paired_answer_slots"], "cached_wires": len(plan["cached"]),
            "new_request_cap": len(plan["units"]), "new_requests": sum(states.values()), "request_states": states,
            "reported_tokens": tokens, "unknown_usage": unknown, "terminal": (ROOT / "TERMINAL").exists(),
            "model_bounds": {m: delta_bounds(v, left, right, 0, 1) for m, v in evaluations.items()},
            "paired_both_evaluators": {
                "positions": len(original_common),
                "Qwen": {m: sum(r[m] for r in original_common) for m in run.METHODS},
                "GPT4.1": {m: sum(r[m] for r in model_comparable) for m in run.METHODS},
            },
            "agreement_over_available_answer_pairs": {m: agreement(r) for m, r in agreement_rows.items()},
            "human_reviews": 0, "original_scores_replaced": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "report"))
    args = parser.parse_args()
    if args.action == "prepare":
        ROOT.mkdir(mode=0o700, exist_ok=True)
    path = ROOT / "PLAN_PRIVATE.json"
    with runner_lock(ROOT / "runner.lock"):
        if args.action == "prepare":
            plan = prepare(read_reference()[1])
            write_frozen(path, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        else:
            plan = run.read(path)
        if args.action == "run":
            if read_reference()[1] != plan["service_sha256"] or prepare(plan["service_sha256"]) != plan:
                raise ValueError("Frozen census or service mismatch")
            sample.dispatch(plan, ROOT)
        print(json.dumps(summarize(plan), indent=2, sort_keys=True))
