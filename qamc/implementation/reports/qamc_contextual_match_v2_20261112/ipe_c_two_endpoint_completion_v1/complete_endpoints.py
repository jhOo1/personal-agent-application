"""Fill the unissued Always-Task endpoint on exposed full-panel history routes."""
import argparse
from collections import Counter
import json
from pathlib import Path

import replay_panel as prior
from qamc.common import parse_object, sha
from qamc_rpeval_terminal_judge_sensitivity import inspect

HERE = Path(__file__).resolve().parent
probe, engine, v41 = prior.probe, prior.engine, prior.v41
ZERO, RP, METHOD = prior.ZERO, prior.RP, "IPE_C"
DRAFT = "EndpointDraft"


def prepare():
    data = prior.prepare()
    panel, cases, original, archived, rank, old_zero, snapshots, old_inputs = data
    old_path = prior.HERE / "RESULTS.json"
    old = prior.read(old_path)
    if panel != prior.read(prior.HERE / "FROZEN.json") or len(old["rows"]) != 300:
        raise ValueError("Require verified IPE-C full-panel baseline")
    known = {uid: {**r["task_only"], "answer": snapshots.get(
        old_inputs.get(uid, {}).get("task_wire_sha256"), {}).get("answer")}
        for uid, r in old_zero.items()}
    # Preserve the status of every previously assigned no-history endpoint.
    for row in old["rows"]:
        if row["scope"] != "additional_67" or row["disposition"] == "REUSE_RP":
            continue
        uid = row["uid"]
        known[uid] = {"status": row.get("new_generation_status", row["disposition"]),
                      "answer": row["answer"], "fields": row["ipe_c"]["grade"],
                      "raw": (row.get("judge") or {}).get("answer"),
                      "flags": row["ipe_c"]["flags"]}
    wire_cache = {digest: r["answer"] for digest, r in snapshots.items()}
    for row in old["rows"]:
        uid, mode = row["uid"], row["disposition"]
        if row["scope"] == "additional_67" and mode in ("NEW_DRAFT", "REUSE_DRAFT"):
            digest = row["task_only_request_sha256"]
            val = known[uid]["answer"]
            if wire_cache.setdefault(digest,val) != val:
                raise ValueError("Exact task-only answer differs")
    unseen, grading_cache, new_requests = {}, {}, {}
    for row in old["rows"]:
        uid = row["uid"]
        if uid in known or row["disposition"] != "REUSE_RP":
            continue
        req = v41.task_only_request(prior.source_root(archived[uid, RP], rank[uid]))
        digest = sha(req)
        if digest != row["task_only_request_sha256"] or row["scope"] != "additional_67":
            raise ValueError("New branch outside the unissued scope")
        unseen[uid] = digest
        if digest not in wire_cache:
            new_requests.setdefault(digest, (uid, req))
    for uid, cell in known.items():
        if not cell["raw"] or not cell["answer"]:
            continue
        wire = engine.rpe_wire(original, cases[uid], {"uid": uid, "answer": cell["answer"], "actor_status": "OK"})
        digest = sha(wire)
        if grading_cache.setdefault(digest, cell["raw"]) != cell["raw"]:
            raise ValueError("Exact archived grade collision")
    pin = {"previous_panel_sha256": sha(old_path.read_bytes()), "task_request_by_uid": unseen,
           "generation_jobs": [[uid,wire] for uid,wire in new_requests.values()],
           "cached_answers": sum(key in wire_cache and wire_cache[key] is not None for key in unseen.values()),
           "code_sha256": sha(Path(__file__).read_bytes()), "judge_cap": len(unseen)}
    return pin, old, known, wire_cache, grading_cache, cases, original


def collect(action, prepared):
    pin, old, nohist, cache, grade_cache, cases, original = prepared
    probe.OUT = engine.OUT = HERE
    probe.RUN = engine.RUN.with_name(HERE.name)
    engine.CAP = {DRAFT: len(pin["generation_jobs"]), engine.RPE: pin["judge_cap"]}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    ledger, live = [], action == "run"

    def stage(name, jobs, archive=None):
        return engine.stage(name, jobs, identity, live, ledger, archive) if jobs else {}

    with probe.runner_lock(probe.RUN / "runner.lock"):
        probe.freeze(HERE / "EXECUTION.json", identity)
        received = stage(DRAFT, {(uid, ZERO): wire for uid,wire in pin["generation_jobs"]})
        for entry in received.values():
            cache[entry["request_sha256"]] = entry["answer"]
        judges, source_map = {}, {}
        for uid, digest in pin["task_request_by_uid"].items():
            answer = cache[digest]
            cell = {"status": "MISSING_TASK_ANSWER", "answer": answer, "raw": None, "fields": {}}
            source_map[uid] = digest
            nohist[uid] = cell
            if answer:
                judges[uid, ZERO] = engine.rpe_wire(original, cases[uid],
                    {"uid": uid, "answer": answer, "actor_status": "OK"})
        rescored = stage(engine.RPE, judges, grade_cache)
        rows = []
        for old_row in old["rows"]:
            uid = old_row["uid"]
            cell = nohist.get(uid, {"status": "NOT_AVAILABLE", "answer": None, "raw": None, "fields": {}})
            receipt = rescored.get((uid, ZERO))
            labels = old_row["labels"]
            if receipt:
                cell.update(status=receipt["status"], raw=receipt.get("answer"), judge_receipt=receipt)
                if receipt["status"] == "OK":
                    try:
                        cell["fields"], cell["invalid"] = probe.fields(parse_object(cell["raw"]), len(labels), True)
                    except (TypeError, KeyError, ValueError) as exc:
                        cell["invalid"] = str(exc)
            score = prior.entry(old_row, cell["answer"], cell["fields"], cell["raw"], labels)
            if "flags" in cell:
                score["flags"] = cell["flags"]
            control = old_row["controls"][RP]
            ipe = old_row["ipe_c"]
            rows.append({"uid": uid, "source_group": old_row["source_group"], "scope": old_row["scope"],
                         "labels": labels, "old_route": old_row["disposition"],
                         "scores": {METHOD: ipe, ZERO: score, RP: control},
                         "controls": {ZERO: score, RP: control}, "ipe_c": ipe,
                         "no_history_state": cell, "task_wire_sha256": source_map.get(uid)})
        result = {"rows": rows, "summary": summarize(rows),
                  "calls": Counter(r["unit"]["stage"] for r in ledger), "ledger": ledger,
                  "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        path = HERE/"RESULTS.json"
        if live:
            probe.freeze(path,result)
        elif prior.read(path) != result:
            raise ValueError("Endpoint completion replay drift")
        print({k:result[k] for k in ("calls","tokens","usage_unknown")})


def summarize(rows):
    shelves = {"all": rows, "additional_67": [r for r in rows if r["scope"]=="additional_67"]}
    for name, check in (("all_A", lambda v:set(v)=={"A"}),
                        ("only_B", lambda v:"B" in v and "C" not in v),
                        ("contains_C", lambda v:"C" in v)):
        shelves[name] = [r for r in rows if r["labels"] and check(r["labels"])]
    result = {}
    for name, shelf in shelves.items():
        usable = [r for r in shelf if all(v["grade"].get("match") for v in r["scores"].values())]
        clean = [r for r in usable if all(v["flags"]==[] for v in r["scores"].values())]
        result[name] = {"assigned": len(shelf)}
        for mode, subset in (("paired",usable),("flag_excluded",clean)):
            measured = {"uids": len(subset), "positions": sum(len(r["labels"]) for r in subset)}
            for m in ("match", "OPB", "UPB", "FM"):
                valid = [r for r in subset if all(m in x["grade"] for x in r["scores"].values())]
                values = {}
                for arm in (METHOD,ZERO,RP):
                    parts = [r["scores"][arm]["grade"][m] for r in valid]
                    values[arm] = sum(v["matched"] for v in parts) if m=="match" else sum(parts)
                measured[m] = {"values":values,"uids":len(valid)}
            result[name][mode] = measured
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze","check","run","replay"))
    args = parser.parse_args()
    prepared = prepare()
    pin = prepared[0]
    config = HERE/"FROZEN.json"
    if args.action == "freeze":
        probe.freeze(config, pin)
    elif pin != prior.read(config):
        raise SystemExit("Frozen endpoint panel differs")
    elif args.action != "check":
        collect(args.action, prepared)
    print({"new_task_endpoints": len(pin["task_request_by_uid"]), "cached_answers": pin["cached_answers"],
           "new_generation_cap": len(pin["generation_jobs"]), "judge_cap": pin["judge_cap"]})
