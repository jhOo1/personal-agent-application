"""Inventory exact historical wires for released MemGate with the frozen RP Actor."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import torch

from audit_memgate import load_gate
from extend import archived
from qamc.common import sha
from qamc.pa.core import digest

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = HERE.parents[2]
FORMAL = BASE / "rpeval_formal_multi_coverage_v1"
ENDPOINTS = BASE / "ipe_c_two_endpoint_completion_v1"
RP = "RPR_PAPER_FULL"


def read(path):
    return json.loads(path.read_text())


def cutoff(gate, query, texts):
    scores = gate.score_candidates(query, texts)
    if len(scores) != len(texts):
        raise ValueError("Published scorer lost position alignment")
    return [i for i, score in enumerate(scores) if score > gate.threshold]


def narrow(wire, selected_ids):
    masked = deepcopy(wire)
    packet = json.loads(wire["messages"][1]["content"])
    for field in ("source_evidence", "preference_use_policy"):
        packet[field] = [item for item in packet[field] if item["memory_id"] in selected_ids]
    masked["messages"][1]["content"] = json.dumps(packet, ensure_ascii=False)
    return masked


def inputs():
    plan = read(FORMAL / "PLAN.json")
    manifest = read(FORMAL / "MANIFEST_300.json")
    if (not plan["not_confirmation"] or len(manifest) != 300 or plan["cases"] != manifest
            or any(c["independent_confirmation"] for c in manifest)):
        raise ValueError("Expected the frozen exposed 300-item development allocation")
    tasks = read(FORMAL / "PUBLIC_TASKS.json")
    rp = {r["uid"]: r for r in read(FORMAL / "RESULT_ROWS.json") if r["method"] == RP}
    ranks = {r["uid"]: r for r in read(FORMAL / "RPR_RANK_FUSION_AUDIT_300.json")["rows"]}
    endpoints = {r["uid"]: r for r in read(ENDPOINTS / "RESULTS.json")["rows"]}
    uids = {r["uid"] for r in manifest}
    if len(uids) != 300 or any(uids != data.keys() for data in (tasks, rp, endpoints)):
        raise ValueError("Input identity drift")
    return manifest, tasks, rp, ranks, endpoints


def contract(task, rp, fused):
    wire = rp["actor_request"]
    packet = json.loads(wire["messages"][1]["content"])
    originals = [{"memory_id": m["memory_id"], "text": m["text"]} for m in task["memories"]]
    ids = [m["memory_id"] for m in originals]
    policies = packet["preference_use_policy"]
    if (
        not fused["archived_actor_wire_unchanged"]
        or sha(wire) != fused["actor_request_sha256"]
        or rp["actor_request_sha256"] != fused["actor_request_sha256"]
        or packet["source_evidence"] != originals
        or [p["memory_id"] for p in policies] != ids or len(ids) != len(set(ids))
        or "".join(p["policy"] for p in policies) != fused["policy"]
        or packet["query"] != task["query"]
        or packet["current_context"] != task["current_context"]
        or packet["facts"] != task["fixed_facts"]
        or narrow(wire, set(ids)) != wire
    ):
        raise ValueError("Original RP Actor contract did not verify")
    return wire, ids, originals


def prepare(assets, embedding):
    manifest, tasks, rp, ranks, endpoints = inputs()
    torch.set_num_threads(2)
    gate, asset_hashes = load_gate(assets, embedding)
    requests, selection, missing = {}, {}, {}
    with torch.no_grad():
        for case in manifest:
            uid = case["uid"]
            task, old = tasks[uid], rp[uid]
            if uid not in ranks or old["actor_status"] != "OK":
                missing[uid] = "MISSING_VERIFIED_RP_ACTOR_OR_STRATEGY"
                continue
            wire, ids, originals = contract(task, old, ranks[uid]["policies"]["PAPER_FUSION"])
            texts = [m["text"] for m in originals]
            positions = cutoff(gate, task["query"], texts)
            selected_ids = [ids[i] for i in positions]
            if not requests:
                author, _, _ = gate(task["query"], texts, preserve_order=True)
                if author != [texts[i] for i in positions]:
                    raise ValueError("Author forward and explicit threshold differ")
            filtered = narrow(wire, set(selected_ids))
            shape = "EMPTY" if not positions else "FULL" if len(ids) == len(positions) else "SUBSET"
            if shape == "EMPTY":
                previous = endpoints[uid]
                for key in ("task_wire_sha256",):
                    if previous.get(key) and sha(filtered) != previous[key]:
                        raise ValueError("Empty selection differs from the exact task-only wire")
            dhash = sha(filtered)
            if requests.setdefault(dhash, filtered) != filtered:
                raise ValueError("Unexpected request digest collision")
            selection[uid] = {"request_sha256": dhash, "shape": shape, "kept": selected_ids, "available": len(ids)}
    return manifest, rp, endpoints, requests, selection, missing, asset_hashes


def inventory(rp, endpoints, requests, selection):
    preferred = {}
    for uid, entry in selection.items():
        key = entry["request_sha256"]
        if entry["shape"] == "FULL":
            answer = rp[uid]["answer"]
        elif entry["shape"] == "EMPTY":
            previous = endpoints[uid]
            answer = previous["no_history_state"].get("answer")
            if answer and sha(answer) != previous["scores"]["TASK_ONLY"]["answer_sha256"]:
                raise ValueError("Task-only endpoint answer changed")
        else:
            continue
        if answer:
            preferred[uid] = {"status": "OK", "answer": answer, "request_sha256": key,
                              "origin": "FIXED_" + entry["shape"]}
    needs_archive = {entry["request_sha256"] for uid, entry in selection.items() if uid not in preferred}
    cache, journals = archived({k: requests[k] for k in sorted(needs_archive)}, ROOT)
    return preferred, cache, journals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("embedding", type=Path)
    parser.add_argument("--private-plan", type=Path)
    args = parser.parse_args()
    manifest, rp, endpoints, requests, selection, missing, hashes = prepare(args.assets, args.embedding)
    preferred, cache, journals = inventory(rp, endpoints, requests, selection)
    unresolved = [entry["request_sha256"] for uid, entry in selection.items()
                  if uid not in preferred and entry["request_sha256"] not in cache]
    pins = {
        "manifest_sha256": digest(manifest), "wires_sha256": sha(requests),
        "selection_sha256": sha(selection), "endpoint_receipts_sha256": sha(preferred),
        "journal_receipts_sha256": sha(cache), "released_artifacts": hashes,
        "source_sha256": sha(Path(__file__).read_bytes()), "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
    }
    if args.private_plan:
        with args.private_plan.open("x") as handle:
            json.dump({"pins": pins, "requests": requests, "selection": selection, "missing": missing,
                       "preferred": preferred, "cache": cache}, handle, ensure_ascii=False)
    print(json.dumps({
        "planned": len(manifest), "verified": len(selection), "missing_contract": len(missing),
        "selected_shape": Counter(r["shape"] for r in selection.values()),
        "known_endpoint_outcome": Counter(r["origin"] for r in preferred.values()),
        "archive_hits_by_status": Counter(r["status"] for r in cache.values()),
        "development_journals": journals, "unmatched_allocations": len(unresolved),
        "distinct_unmatched_actor_wires": len(set(unresolved)), "cloud_requests": 0, "pins": pins,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
