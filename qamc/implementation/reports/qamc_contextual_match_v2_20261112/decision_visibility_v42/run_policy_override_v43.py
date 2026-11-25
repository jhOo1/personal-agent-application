"""One fixed-Actor policy intervention over the existing V42 development panel."""
from argparse import ArgumentParser
from collections import Counter
import json
import os
from pathlib import Path
from time import sleep

from qamc.common import parse_object, sha

from audit_archived_policy_edits import policy_only_request, source_levels
import run_visibility_v42 as v42
from settle_visibility_v42 import stable_prefix

OUT = v42.OUT.with_name("rp_policy_override_rpeval_v43")
RUN = v42.RUN.with_name(OUT.name)
METHOD = "RP_POLICY_OVERRIDE"
ACTOR, JUDGE = v42.ACTOR, v42.JUDGE
prior, probe, read = v42.prior, v42.PROBE, v42.read
PROTOCOL = Path(__file__).with_name("POLICY_OVERRIDE_V43.md")


def candidate(root, selections):
    scopes = [selections[method]["scope"] for method in ("DIRECT", "SCOPED")]
    if any(scope is None for scope in scopes):
        return {}, "FALLBACK_NO_TWO_POLICIES"
    baseline = {p["memory_id"]: p["policy"] for p in root["archived_policy"]}
    direct, scoped = (source_levels(baseline, scope) for scope in scopes)
    edits = {mid: direct[mid] for mid, level in baseline.items()
             if level == "B" and direct[mid] == scoped[mid] and direct[mid] in {"A", "C"}}
    return edits, "CHANGED" if edits else "IDENTITY_NO_AGREEMENT"


def prepare(expected=None):
    parent = read(v42.OUT / "FROZEN.json")
    if parent != v42.prepare():
        raise ValueError("Parent experiment no longer matches its frozen inputs")
    prefix = stable_prefix(parent)
    planned = sum(map(len, parent["waves"]))
    count = sum(w["roots"] for w in prefix)
    if expected is None:
        state = read(v42.OUT / "RUN_STATE.json")
        if state["state"] != "COMPLETE" or count != planned:
            raise ValueError("Fresh dispatch requires the full V42 terminal panel")
    elif expected != count:
        raise ValueError(f"Expected a {expected}-root preview, found {count}")
    roots = {r["uid"]: r for r in read(prior.OUT / "FROZEN.json")["roots"]}
    proposals = []
    for entry in prefix:
        path = v42.OUT / f"wave_{entry['wave']:02d}" / "COMPLETED.json"
        data = read(path)
        if sha(path.read_bytes()) != entry["sha256"]:
            raise ValueError("Settled parent wave changed")
        if [r["uid"] for r in data["rows"]] != parent["waves"][entry["wave"]]:
            raise ValueError("Parent membership changed")
        for row in data["rows"]:
            uid = row["uid"]
            root = roots[uid]
            edits, disposition = candidate(root, row["selected"])
            fixed = root["archived"][prior.RP]
            wire = policy_only_request(root, edits)
            if not fixed["answer"] or (sha(wire) != fixed["actor_sha256"]) != bool(edits):
                raise ValueError("Archived baseline or policy intervention identity mismatch")
            proposals.append({"uid": uid, "group": root["group"], "parent_wave": entry["wave"],
                              "edits": edits, "disposition": disposition, "actor_sha256": sha(wire)})
    cap = len({r["actor_sha256"] for r in proposals if r["edits"]})
    return {"preview": expected is not None, "input_sources": prefix, "roots": proposals,
            "code_sha256": sha(Path(__file__).read_bytes()),
            "protocol_sha256": sha(PROTOCOL.read_bytes()),
            "policy_compiler_sha256": sha(PROTOCOL.with_name("audit_archived_policy_edits.py").read_bytes()),
            "service_reference_sha256": parent["service_reference_sha256"],
            "caps": {ACTOR: cap, JUDGE: sum(bool(r["edits"]) for r in proposals)},
            "independent_confirmation": False}, roots


def finish(plan, rows, ledger):
    strata = {
        "all": rows, "changed": [r for r in rows if r["trace"]["edits"]],
        "before_review_prefix": [r for r in rows if r["trace"]["parent_wave"] <= 4],
        "after_review_prefix": [r for r in rows if r["trace"]["parent_wave"] > 4],
        "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in rows if set(r["labels"]) != {"A"}],
    }
    counts = Counter(r["unit"]["stage"] for r in ledger)
    if any(counts[stage] > cap for stage, cap in plan["caps"].items()):
        raise ValueError("Frozen physical allowance exceeded")
    return {"roots": len(rows), "dispositions": Counter(r["trace"]["disposition"] for r in rows),
            "calls": counts, "statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
            "metrics": {name: {m: {**v42.paired(items, m, METHOD), "severity": v42.metric_pairs(items, m, METHOD)}
                               for m in (prior.RP, prior.GATE)} for name, items in strata.items()},
            "human_adjudications": 0}


def inherited_receipts(plan):
    cache = {ACTOR: {}, JUDGE: {}}
    for entry in plan["input_sources"]:
        wave = v42.OUT / f"wave_{entry['wave']:02d}"
        if sha((wave / "COMPLETED.json").read_bytes()) != entry["sha256"]:
            raise ValueError("Parent receipt snapshot changed")
        ledger = read(wave / "COMPLETED.json")["ledger"]
        for stage in cache:
            exact = read(wave / f"{stage}_EXACT.json")
            expected = {r["request_sha256"]: r for r in ledger if r["unit"]["stage"] == stage}
            if {fingerprint: value[0] for fingerprint, value in exact.items()} != expected:
                raise ValueError("Parent exact cache does not reconcile with its ledger")
            cache[stage].update(exact)
    return cache


def evaluate(plan, roots, live):
    if live and (plan["preview"] or probe.read_reference()[1] != plan["service_reference_sha256"]):
        raise ValueError("Cannot dispatch a preview or a different gateway")
    cache = inherited_receipts(plan)
    probe.OUT, probe.RUN = OUT, RUN
    original = read(prior.formal.OUT / "PLAN.json")
    cases = prior.author_cases(original)
    archived_wires = {r["archived_actor_sha256"]: r["archived"][prior.RP]["answer"]
                      for r in roots.values() if r["archived"][prior.RP]["answer"]}
    jobs = []
    for entry in plan["roots"]:
        if entry["edits"]:
            wire = policy_only_request(roots[entry["uid"]], entry["edits"])
            if sha(wire) != entry["actor_sha256"]:
                raise ValueError("Actor request hash drift")
            if entry["actor_sha256"] not in archived_wires:
                jobs.append((entry["uid"], METHOD, wire))
    parent_out = v42.OUT
    v42.OUT = OUT
    try:
        received = v42.execute_stage(plan, "main", ACTOR, jobs, cache[ACTOR], live)
        rows, judgments = [], []
        for entry in plan["roots"]:
            uid = entry["uid"]
            root = roots[uid]
            base = root["archived"]
            native = {name: {"fields": saved["fields"], "raw": saved["raw_judge"]}
                      for name, saved in base.items()}
            if not entry["edits"]:
                answer, status = base[prior.RP]["answer"], "REUSED_RP_ACTOR"
            elif entry["actor_sha256"] in archived_wires:
                answer, status = archived_wires[entry["actor_sha256"]], "REUSED_RP_ACTOR"
            else:
                actor_receipt, answer = received[uid, METHOD]
                status = actor_receipt["status"]
            saved = (prior.RP if not entry["edits"] else
                     next((name for name, value in base.items()
                           if value["answer"] == answer and value["raw_judge"] is not None), None))
            native[METHOD] = {"fields": {}, "raw": None}
            if saved:
                native[METHOD] = {**native[saved], "reuse": saved}
            elif answer and entry["edits"]:
                cell = {"uid": uid, "method": prior.GATE, "actor_status": "OK", "answer": answer}
                job, = prior.formal.grading_jobs(original, [cases[uid]], [cell])
                judgments.append((uid, METHOD, job["request"]))
            # Evaluation labels are recorded only after constructing all Actor requests.
            gold = read(prior.formal.ROOT / cases[uid]["evaluation_path"])
            if v42.digest(gold) != cases[uid]["evaluation_hash"]:
                raise ValueError("Native evaluation input changed")
            rows.append({"uid": uid, "group": root["group"], "trace": entry, "native": native,
                         "labels": gold["intent_type"], "positions": len(gold["intent_type"]),
                         "actor_status": status, "answer": answer})
        judged = v42.execute_stage(plan, "main", JUDGE, judgments, cache[JUDGE], live)
    finally:
        v42.OUT = parent_out
    for row in rows:
        receipt = judged.get((row["uid"], METHOD))
        if receipt is None:
            continue
        record, raw = receipt
        cell = row["native"][METHOD]
        cell.update(raw=raw, status=record["status"], judge_sha256=record["request_sha256"])
        if raw is not None:
            try:
                cell["fields"], cell["invalid"] = probe.fields(parse_object(raw), row["positions"], True)
            except (ValueError, TypeError, KeyError) as error:
                cell.update(status="INVALID_JUDGE_OUTPUT", error=str(error))
    ledger = [record for stage in (ACTOR, JUDGE) for record, _ in probe.stage_receipts(stage).values() if record]
    return {"rows": rows, "ledger": ledger, "summary": finish(plan, rows, ledger)}


def wait_for_parent():
    state = OUT / "RUN_STATE.json"
    while True:
        upstream = read(v42.OUT / "RUN_STATE.json")
        if upstream["state"] == "COMPLETE":
            return
        if upstream["state"] != "RUNNING":
            probe.atomic_json(state, {"state": "WAITING_STOPPED_PARENT", "parent": upstream})
            raise RuntimeError("V42 stopped before the frozen panel was complete")
        pid = int((v42.OUT / "WORKER.pid").read_text())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            probe.atomic_json(state, {"state": "WAITING_STOPPED_PARENT", "parent": upstream})
            raise RuntimeError("The V42 worker is absent")
        probe.atomic_json(state, {"state": "QUEUED_AFTER_V42", "parent": upstream})
        sleep(45)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "freeze", "run"))
    parser.add_argument("--expected", type=int, help="Exact settled root count for an offline preview.")
    parser.add_argument("--wait-parent", action="store_true", help="Wait for the active V42 worker before dispatch.")
    args = parser.parse_args()
    if args.wait_parent and args.action != "run":
        parser.error("--wait-parent requires run")
    if args.action == "preview":
        if args.expected is None:
            parser.error("Preview requires an explicit settled root count")
        plan, _ = prepare(args.expected)
        print(json.dumps({"preview_roots": len(plan["roots"]), "caps": plan["caps"],
                          "dispositions": Counter(r["disposition"] for r in plan["roots"]),
                          "new_model_calls": 0}))
    else:
        if args.expected is not None:
            parser.error("--expected is only for preview")
        with probe.runner_lock(RUN / "runner.lock"):
            if args.wait_parent:
                wait_for_parent()
            plan, roots = prepare()
            probe.freeze(OUT / "FROZEN.json", plan)
            if args.action == "run":
                path = OUT / "COMPLETED.json"
                if not path.exists():
                    state = OUT / "RUN_STATE.json"
                    probe.atomic_json(state, {"state": "RUNNING"})
                    try:
                        probe.freeze(path, evaluate(plan, roots, live=True))
                    except (ValueError, RuntimeError, KeyError, TypeError) as error:
                        probe.atomic_json(state, {"state": "STOPPED", "reason": str(error)})
                        raise
                    probe.atomic_json(state, {"state": "COMPLETE"})
                print(json.dumps(read(path)["summary"], ensure_ascii=False, indent=2))
