"""Independently verify applicable participant requirements before pruning whole records."""
import argparse
from collections import Counter
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
prior = run_path(str(BASE / "open_shared_choice_guard_v1" / "trial.py"))
archive, body, engine, grading, parse, probe, sha, task_packet = (
    prior[key] for key in ("archive", "body", "engine", "grading", "parse", "probe", "sha", "task_packet")
)
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
OLD = prior["PRIVATE"]
REVIEW, ACTOR, METHOD = "RequirementReview", "ParticipantActor", "PARTICIPANT_VETO"
CAP = {REVIEW: 10, ACTOR: 10, engine.RPE: 4, "BenchAttrs": 12, "PersistNative": 4}
AUDIT = """Read the current task and original memory only. Independently identify any explicit hard
requirement applicable to the current answer that must be preserved for a real participant or the
required deliverable. A clear exclusion, allergy, binding instruction, or expressly stated hard
constraint can qualify. Strong wording alone is insufficient if it describes somebody else's event,
a past project, a general belief about the world, a private theory about what others should do, or
an older condition contradicted by the current task. A relevant soft preference is not a hard
requirement. A requirement held by a participant only needs to protect that person's real involvement;
do not assert that other participants have the same requirement. Do not propose a decision or draft.
For every qualifying original record, cite its shortest exact contiguous requirement text, an exact
contiguous task phrase identifying the affected requested decision, and an exact contiguous quote
establishing participation. For REQUESTER, the participation quote must be from QUERY and indicate
that the user will take part or directly use the deliverable. For NAMED_PARTICIPANT, the holder must
be a name copied exactly from both the rule quote and the participation quote. The participation
quote may be in QUERY or a separate original source that explicitly identifies the current group.
Otherwise report no requirement. Return only
{"requirements":[{"source":"existing memory ID","rule":"verbatim quote",
"decision":"verbatim QUERY quote","kind":"REQUESTER or NAMED_PARTICIPANT",
"holder":"USER or exact name","participation_source":"QUERY or existing memory ID",
"participation":"verbatim quote"}]}.
An empty list is valid. Do not include external knowledge, answer text, or reasoning fields."""


def protections(raw, packet):
    response = parse(raw)
    if not isinstance(response, dict) or set(response) != {"requirements"} or not isinstance(response["requirements"], list):
        raise ValueError("Invalid protection schema")
    sources = {s["memory_id"]: s["text"] for s in packet["source_evidence"]}
    if len(sources) != len(packet["source_evidence"]):
        raise ValueError("Duplicate memory ID")
    query = packet["task"]["query"]
    protected, rejected = set(), 0
    for item in response["requirements"]:
        if (not isinstance(item, dict)
                or set(item) != {"source", "rule", "decision", "kind", "holder", "participation_source", "participation"}
                or any(not isinstance(v, str) or not v.strip() for v in item.values())):
            rejected += 1
            continue
        if (item["rule"] not in sources.get(item["source"], "") or item["decision"] not in query
                or item["participation"] not in ({**sources, "QUERY": query}.get(item["participation_source"], ""))):
            rejected += 1
            continue
        if item["kind"] == "REQUESTER":
            role_verified = item["holder"] == "USER" and item["participation_source"] == "QUERY"
        elif item["kind"] == "NAMED_PARTICIPANT":
            role_verified = (item["participation_source"] != item["source"]
                             and item["holder"] in item["rule"] and item["holder"] in item["participation"])
        else:
            role_verified = False
        if role_verified:
            protected.add(item["source"])
        else:
            rejected += 1
    return protected, rejected


def actor_wire(card, ids):
    packet = task_packet(card)
    selected = [s for s in packet["source_evidence"] if s["memory_id"] in ids]
    return body(prior["ACTOR"], {**packet, "source_evidence": selected})


def prepare():
    old_pin, cards, _ = prior["freeze"]()
    if archive.read(OLD / "FROZEN_HASHES.json") != old_pin:
        raise ValueError("Prior study drift")
    result = archive.read(OLD / "RESULTS.json")
    rows = {(r["uid"], r["method"]): r for r in result["rows"]}
    changed = set(result["changed_requests"])
    if len(changed) != CAP[REVIEW] or len(rows) != 2 * len(cards):
        raise ValueError("Expected prior exposed comparison to be complete")
    old_manifest = archive.read(OLD / "OpenChoiceActor_MANIFEST.json")
    physical = {(unit["unit"]["root_id"], unit["unit"]["method"]): sha(unit["request"])
                for unit in old_manifest["units"]}
    archived_actors = {(uid, arm): r["request_sha256"]
                       for uid, arm, r in archive.read(OLD / "OpenChoiceActor_archive.json")}
    admitted = physical | archived_actors
    baseline = {}
    for uid, card in cards.items():
        for arm in prior["ARMS"]:
            key = uid, arm
            wire = actor_wire(card, result["audits"][uid]["kept"][arm])
            if (rows[key]["actor_status"] != "OK" or not rows[key]["answer"] or not rows[key]["score"]
                    or sha(wire) not in admitted.values()):
                raise ValueError("Prior Actor cannot be reconstructed")
            baseline.setdefault(sha(wire), rows[key])
        if ((sha(actor_wire(card, result["audits"][uid]["kept"][prior["ARMS"][0]]))
             != sha(actor_wire(card, result["audits"][uid]["kept"][prior["ARMS"][1]]))) != (uid in changed)):
            raise ValueError("Prior changed-input comparison drift")
    jobs = {(uid, "INDEPENDENT"): body(AUDIT, task_packet(card))
            for uid, card in cards.items() if uid in changed}
    pin = {"parent": sha((OLD / "RESULTS.json").read_bytes()),
           "sources": {uid: sha(task_packet(card)) for uid, card in cards.items()},
           "review_wires": {uid: sha(wire) for (uid, _), wire in jobs.items()},
           "caps": CAP, "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "service_reference_sha256": old_pin["service_reference_sha256"]}
    return pin, cards, result["audits"], rows, baseline, jobs


def execute(prepared, live):
    pin, cards, old_audits, old_rows, baseline, jobs = prepared
    if probe.read_reference()[1] != pin["service_reference_sha256"]:
        raise ValueError("Service configuration changed")
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = CAP
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service_reference_sha256"]}
    ledger, outcomes, audit, candidates = [], [], {}, {}
    with probe.runner_lock(RUN / "runner.lock"):
        def stage(name, wires, cache=None):
            if not wires:
                return {}
            canonical = {}
            for key, wire in wires.items():
                canonical.setdefault(sha(wire), key)
            unique = {key: wires[key] for key in canonical.values()}
            active = dict(unique)
            reused = {}
            checkpoint = PRIVATE / f"{name}_archive.json"
            if live and not checkpoint.exists():
                hits, _ = prior["find_archived"](active, BASE.parents[1])
                saved = []
                for (uid, arm), hit in hits.items():
                    old = BASE.parents[1] / hit["archive"]
                    record = old.parent / "visible" / hit["archive_unit"] / "record.json"
                    meta = archive.read(record).get("reference_config_sha256") if record.is_file() else None
                    if hit["status"] == "OK" and meta != pin["service_reference_sha256"]:
                        hit = {**hit, "answer": None, "status": "ARCHIVED_PROTOCOL_UNVERIFIED"}
                    saved.append([uid, arm, hit])
                probe.freeze(checkpoint, saved)
            for uid, method, hit in archive.read(checkpoint):
                key = uid, method
                if hit["request_sha256"] != sha(active.pop(key)):
                    raise ValueError("Archived stage request drift")
                reused[key] = hit
            received = engine.stage(name, active, identity, live, ledger, cache) if active else {}
            all_keys = reused | received
            return {key: all_keys[canonical[sha(wire)]] for key, wire in wires.items()}

        reviews = stage(REVIEW, jobs)
        for uid, card in cards.items():
            old = old_audits[uid]["kept"]
            ordinary, guard = (set(old[arm]) for arm in prior["ARMS"])
            removed = ordinary - guard
            protected, invalid = set(), 0
            status = "REUSE_IDENTICAL_POLICY"
            if removed:
                reply = reviews[uid, "INDEPENDENT"]
                status = reply["status"]
                if status == "OK":
                    try:
                        protected, invalid = protections(reply["answer"], task_packet(card))
                    except (ValueError, TypeError, AttributeError):
                        status = "INVALID_REVIEW"
            restored = protected & removed
            audit[uid] = {"status": status, "invalid_witnesses": invalid,
                          "restored": sorted(restored), "confirmed_requirements": sorted(protected)}
            wire = actor_wire(card, guard | restored)
            key = uid, METHOD
            if sha(wire) in baseline:
                outcomes.append({**baseline[sha(wire)], "method": METHOD, "origin": "EXACT_PARENT_ACTOR_AND_SCORE"})
            else:
                candidates[key] = wire
        for (uid, _), receipt in stage(ACTOR, candidates).items():
            card = cards[uid]
            outcomes.append({**{key: card[key] for key in ("uid", "benchmark", "stratum", "group")},
                             "method": METHOD, "sources": card["packet"]["source_evidence"], "score": None,
                             "actor_status": receipt["status"], "answer": receipt.get("answer"),
                             "origin": "ADDITIONAL_ACTOR_WIRE", "actor": receipt})
        grading([r for r in outcomes if r["origin"] == "ADDITIONAL_ACTOR_WIRE"], stage) if candidates else None
        result = {"audit": audit, "rows": outcomes, "ledger": ledger,
                  "new_distinct_actor_roots": len(candidates)}
        if live:
            probe.freeze(PRIVATE / "RESULTS.json", result)
        elif archive.read(PRIVATE / "RESULTS.json") != result:
            raise ValueError("Zero-call replay disagrees with settled receipts")
        print({"physical_requests": len(ledger), "statuses": dict(Counter(r["status"] for r in ledger)),
               "restored_sources": sum(len(r["restored"]) for r in audit.values()),
               "new_distinct_actor_roots": len(candidates)}, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "check", "run", "replay"))
    mode = parser.parse_args().mode
    prepared = prepare()
    pin = prepared[0]
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    frozen = PRIVATE / "FROZEN_HASHES.json"
    if mode == "freeze":
        probe.freeze(frozen, pin)
    elif archive.read(frozen) != pin:
        raise ValueError("Experiment freeze drift")
    if mode in ("run", "replay"):
        execute(prepared, mode == "run")
    else:
        print("Exposed roots", len(prepared[1]), "independent review wires", len(prepared[-1]))


if __name__ == "__main__":
    main()
