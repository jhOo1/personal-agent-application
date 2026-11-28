"""Transfer completed development pruning decisions to the exact archived RPEval Actor request."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
support = run_path(str(BASE / "participant_requirement_expansion_v1" / "trial.py"))
archive, engine, grading, probe, sha = (support[k] for k in ("archive", "engine", "grading", "probe", "sha"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
ACTOR = "StrongWirePrunedActor"
CAPS = {ACTOR: 7, engine.RPE: 7}
METHOD = "STRONG_WIRE_PRUNED"
ORIGINAL_CODE = "7d0f8f21d7d3f0f8ed63189f69e802f05e86d275218a8ed5142df7268b1991de"


def prune(wire, removed):
    edited = deepcopy(wire)
    message = edited["messages"][1]
    packet = json.loads(message["content"])
    if packet.keys() != {"query", "current_context", "facts", "source_evidence", "preference_use_policy"}:
        raise ValueError("Unexpected archived Actor packet")
    fields = ("source_evidence", "preference_use_policy")
    ids = {field: [entry["memory_id"] for entry in packet[field]] for field in fields}
    if any(len(v) != len(set(v)) for v in ids.values()) or set(ids[fields[0]]) != set(ids[fields[1]]):
        raise ValueError("Archived source and policy IDs must each be unique and aligned")
    overlap = set(ids["source_evidence"]) & removed
    for field in fields:
        packet[field] = [e for e in packet[field] if e["memory_id"] not in overlap]
    original = message["content"]
    options = [{"indent": 2}, {}, {"indent": 2, "sort_keys": True}, {"separators": (",", ":")}]
    before = json.loads(original)
    for settings in options:
        for ascii_only in (False, True):
            if json.dumps(before, ensure_ascii=ascii_only, **settings) == original:
                message["content"] = json.dumps(packet, ensure_ascii=ascii_only, **settings)
                return edited, overlap
    raise ValueError("Archived packet serialization is not recognized")


def prepare():
    prior, veto = support["prior"], support["veto"]
    old = archive.read(prior["PRIVATE"] / "RESULTS.json")["audits"]
    protection = archive.read(veto["PRIVATE"] / "RESULTS.json")["audit"]
    expansion = archive.read(support["PRIVATE"] / "RESULTS.json")["audits"]
    cards = {r["uid"]: r for r in archive.read(prior["PARENT"])["rows"] if r["benchmark"] == "RPEval"}
    old_removals = {u: set(a["kept"]["RELEVANCE"]) - set(a["kept"]["OPEN_CHOICE_GUARD"])
                    for u, a in old.items() if u in cards}
    new_removals = {u: set(a.get("removed", ())) for u, a in expansion.items() if u in cards}
    if old_removals.keys() & new_removals.keys():
        raise ValueError("Guard panels overlap")
    removed = old_removals | new_removals
    routes = {r["uid"]: r["old_route"] for r in archive.read(BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    bank = {r["uid"]: r for r in archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json")
            if r["method"] == engine.RP and r["actor_status"] == "OK" and r["uid"] in removed}
    jobs, roster, admitted = {}, [], {}
    for uid, ids in sorted(removed.items()):
        if not ids:
            continue
        audit = protection.get(uid, expansion.get(uid, {}))
        protection_status = audit.get("status", audit.get("requirement_status"))
        approved = ids - set(audit.get("restored", ()))
        card = cards[uid]
        row = bank.get(uid)
        status, overlap = "NO_ARCHIVED_HISTORY", set()
        if not approved or protection_status != "OK":
            status = "NO_VERIFIED_UNPROTECTED_REMOVAL"
        elif routes[uid] == "REUSE_RP" and row:
            wire = row["actor_request"]
            if sha(wire) != row["actor_request_sha256"] or sha(row["answer"]) != card["baseline_answer_sha256"]:
                raise ValueError("Original Actor request or answer does not match frozen specialist")
            edited, overlap = prune(wire, approved)
            if overlap:
                status = "ELIGIBLE"
                admitted[uid] = card
                jobs[uid, METHOD] = edited
            else:
                status = "NO_ID_OVERLAP"
        roster.append({"uid": uid, "group": card["group"], "status": status, "removed": sorted(overlap),
                       "request_sha256": sha(jobs[uid, METHOD]) if status == "ELIGIBLE" else None,
                       "baseline_sha256": card["baseline_answer_sha256"]})
    if not jobs or len({r["group"] for r in admitted.values()}) != len(admitted):
        raise ValueError("Need eligible tasks from distinct development groups")
    return {"cases": roster, "caps": CAPS, "code": sha(Path(__file__).read_bytes()),
            "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
            "service_reference_sha256": probe.read_reference()[1]}, admitted, jobs


def execute(pin, cards, jobs, live):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = CAPS
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service_reference_sha256"]}
    ledger, reuse = [], {}
    root = BASE.parents[1]

    def stage(name, wires, cache=None):
        checkpoint = PRIVATE / f"{name}_archive.json"
        if live and not checkpoint.exists():
            saved, _ = support["prior"]["find_archived"](wires, root)
            records = []
            for (uid, arm), record in saved.items():
                metadata = (root / record["archive"]).parent / "visible" / record["archive_unit"] / "record.json"
                reference = archive.read(metadata).get("reference_config_sha256") if metadata.exists() else None
                if record["status"] == "OK" and reference != pin["service_reference_sha256"]:
                    record = dict(record, status="ARCHIVED_PROTOCOL_UNVERIFIED", answer=None)
                records.append([uid, arm, record])
            probe.freeze(checkpoint, records)
        known = {(uid, arm): record for uid, arm, record in archive.read(checkpoint)}
        if any(record["request_sha256"] != sha(wires[key]) for key, record in known.items()):
            raise ValueError("Archived request drift")
        reuse[name] = dict(Counter(r["status"] for r in known.values()))
        pending = {key: wire for key, wire in wires.items() if key not in known}
        fresh = {}
        if pending:
            active = live
            if live and (PRIVATE / f"{name}_MANIFEST.json").is_file():
                receipts = probe.stage_receipts(name)
                if all(key in receipts and receipts[key][0]
                       and receipts[key][0]["status"] != "PENDING_DELIVERY_UNKNOWN" for key in pending):
                    active = False
            fresh = engine.stage(name, pending, identity, active, ledger, cache)
        return known | fresh

    with probe.runner_lock(RUN / "runner.lock"):
        rows = []
        for (uid, arm), actor in stage(ACTOR, jobs).items():
            card = cards[uid]
            rows.append({**{key: card[key] for key in ("uid", "benchmark", "stratum", "group")},
                         "method": arm, "sources": card["packet"]["source_evidence"],
                         "actor_status": actor["status"], "answer": actor["answer"],
                         "baseline_score": card["base_score"], "score": None})
        grading(rows, stage)
        result = {"rows": rows, "ledger": ledger, "exact_reuse": reuse}
        target = PRIVATE / "RESULTS.json"
        if live:
            probe.freeze(target, result)
        elif archive.read(target) != result:
            raise ValueError("Settlement replay mismatch")
        print({"roots": len(rows), "physical": len(ledger), "reuse": reuse})


def verify_frozen(pin, frozen):
    if pin != frozen and (frozen.get("code") != ORIGINAL_CODE
                          or {**pin, "code": ORIGINAL_CODE} != frozen):
        raise ValueError("Frozen comparison changed")
    return frozen


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "check", "run", "replay"))
    action = parser.parse_args().action
    data = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    pin_path = PRIVATE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(pin_path, data[0])
    else:
        data = (verify_frozen(data[0], archive.read(pin_path)), *data[1:])
    if action in ("run", "replay"):
        execute(*data, live=action == "run")
    else:
        print([(r["uid"].split("/")[-2:], r["status"], len(r["removed"])) for r in data[0]["cases"]])
