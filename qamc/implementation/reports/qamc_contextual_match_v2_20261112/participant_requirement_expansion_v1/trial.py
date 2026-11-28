"""Run the frozen relevance, open-choice and participant-veto policies on separate source groups."""
import argparse
from collections import Counter
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
veto = run_path(str(BASE / "participant_requirement_veto_v1" / "trial.py"))
prior, archive, body, engine, grading, probe, sha, task_packet = (
    veto[k] for k in ("prior", "archive", "body", "engine", "grading", "probe", "sha", "task_packet")
)
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
REVIEW, REQUIREMENT, ACTOR = "ExpansionRelevance", "ExpansionRequirement", "ExpansionActor"
CAP = {REVIEW: 21, REQUIREMENT: 21, ACTOR: 63, engine.RPE: 33, "BenchAttrs": 72, "PersistNative": 18}
ARMS = (*prior["ARMS"], veto["METHOD"])
COUNTS = {
    ("RPEval", "all_A"): 3, ("RPEval", "B_only"): 4, ("RPEval", "contains_C"): 4,
    ("PersistBench", "sycophancy"): 2, ("PersistBench", "cross_domain"): 2,
    ("PersistBench", "beneficial_memory_usage"): 2, ("BenchPreS", "communication"): 4,
}


def prepare():
    _, preceding, _ = prior["freeze"]()
    seen = {(r["benchmark"], r["group"]) for r in preceding.values()}
    parent = archive.read(prior["PARENT"])
    if parent["exposed_development_only"] is not True:
        raise ValueError("Require the known exposed cohort")
    rows = sorted(parent["rows"], key=lambda r: sha(["participant expansion 1", r["uid"]]))
    count, cards = Counter(), {}
    for card in rows:
        stratum = card["benchmark"], card["stratum"]
        group = card["benchmark"], card["group"]
        if group in seen or stratum not in COUNTS or count[stratum] >= COUNTS[stratum]:
            continue
        if not card["base_score"] or sha(card["base_answer"].strip()) != card["baseline_answer_sha256"]:
            raise ValueError("Frozen specialist baseline missing or changed")
        cards[card["uid"]] = card
        seen.add(group)
        count[stratum] += 1
    if count != COUNTS:
        raise ValueError(f"Insufficient assigned source groups: {count}")
    jobs = {(uid, "SHARED"): body(prior["AUDIT"], task_packet(card)) for uid, card in cards.items()}
    requirement = {(uid, "INDEPENDENT"): body(veto["AUDIT"], task_packet(card)) for uid, card in cards.items()}
    pin = {"cases": [{"uid": u, "benchmark": c["benchmark"], "group": c["group"],
                     "baseline_sha256": c["baseline_answer_sha256"],
                     "task_sha256": sha(task_packet(c))} for u, c in cards.items()],
           "review_hash": {u: [sha(jobs[u, "SHARED"]), sha(requirement[u, "INDEPENDENT"])] for u in cards},
           "caps": CAP, "parent": sha(prior["PARENT"].read_bytes()),
           "service_reference_sha256": probe.read_reference()[1],
           "code": {file.name: sha(file.read_bytes()) for file in (Path(__file__), HERE / "PROTOCOL.md",
                    prior["HERE"] / "trial.py", veto["HERE"] / "trial.py")}}
    return pin, cards, jobs, requirement


def execute(info, cards, jobs, required, live):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = CAP
    identity = {"experiment_sha256": sha(info), "service_reference_sha256": info["service_reference_sha256"]}
    journal, audits, pending, rows, archive_counts = [], {}, {}, [], {}

    def stage(name, wires, cache=None):
        if not wires:
            return {}
        by_hash = {}
        for key, wire in wires.items():
            by_hash.setdefault(sha(wire), key)
        active = {key: wires[key] for key in by_hash.values()}
        checkpoint = PRIVATE / f"{name}_archive.json"
        if live and not checkpoint.exists():
            old, _ = prior["find_archived"](active, BASE.parents[1])
            frozen = []
            for (uid, arm), record in old.items():
                journal_file = BASE.parents[1] / record["archive"]
                metadata_path = journal_file.parent / "visible" / record["archive_unit"] / "record.json"
                reference = archive.read(metadata_path).get("reference_config_sha256") if metadata_path.is_file() else None
                if record["status"] == "OK" and reference != info["service_reference_sha256"]:
                    record = {**record, "status": "ARCHIVED_PROTOCOL_UNVERIFIED", "answer": None}
                frozen.append([uid, arm, record])
            probe.freeze(checkpoint, frozen)
        saved = {}
        for uid, arm, record in archive.read(checkpoint):
            key = (uid, arm)
            if record["request_sha256"] != sha(active.pop(key)):
                raise ValueError("Inconsistent archive")
            saved[key] = record
        archive_counts[name] = dict(Counter(r["status"] for r in saved.values()))
        fresh = engine.stage(name, active, identity, live, journal, cache) if active else {}
        received = saved | fresh
        return {key: received[by_hash[sha(wire)]] for key, wire in wires.items()}

    with probe.runner_lock(RUN / "runner.lock"):
        reviews = stage(REVIEW, jobs)
        removals = {}
        for uid, card in cards.items():
            review = reviews[uid, "SHARED"]
            record = audits.setdefault(uid, {"relevance_status": review["status"]})
            if review["status"] != "OK":
                continue
            try:
                selection, invalid = prior["interpret"](review["answer"], task_packet(card))
            except (TypeError, ValueError, AttributeError):
                record["relevance_status"] = "INVALID_REVIEW"
                continue
            ordinary, pruned = (selection[a] for a in prior["ARMS"])
            removals[uid] = ordinary - pruned
            record.update(removed=sorted(removals[uid]), rejected=invalid,
                          retain=sorted(ordinary), guard=sorted(pruned))
        protections = stage(REQUIREMENT, {key: wire for key, wire in required.items() if removals.get(key[0])})
        for uid, removed in removals.items():
            report = audits[uid]
            protected, invalid = set(), 0
            status = "NOT_NEEDED"
            if removed:
                reply = protections[uid, "INDEPENDENT"]
                status = reply["status"]
                if status == "OK":
                    try:
                        protected, invalid = veto["protections"](reply["answer"], task_packet(cards[uid]))
                    except (TypeError, ValueError, AttributeError):
                        status = "INVALID_REVIEW"
            restored = removed & protected
            report.update(requirement_status=status, restored=sorted(restored), invalid_proofs=invalid)
            ids = (set(report["retain"]), set(report["guard"]), set(report["guard"]) | restored)
            for arm, keep in zip(ARMS, ids, strict=True):
                pending[uid, arm] = veto["actor_wire"](cards[uid], keep)
        for (uid, arm), response in stage(ACTOR, pending).items():
            card = cards[uid]
            rows.append({**{k: card[k] for k in ("uid", "benchmark", "stratum", "group")},
                         "method": arm, "sources": card["packet"]["source_evidence"],
                         "actor_status": response["status"], "answer": response.get("answer"),
                         "score": None, "actor": response})
        if rows:
            grading(rows, stage)
        output = {"audits": audits, "rows": rows, "ledger": journal, "exact_reuse": archive_counts}
        if live:
            probe.freeze(PRIVATE / "RESULTS.json", output)
        elif archive.read(PRIVATE / "RESULTS.json") != output:
            raise ValueError("Replay differs from the stored settlement")
        print({"roots": len(cards), "physical": len(journal),
               "statuses": dict(Counter(r["status"] for r in journal))}, flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "check", "run", "replay"))
    action = cli.parse_args().action
    prepared = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = PRIVATE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, prepared[0])
    elif archive.read(path) != prepared[0]:
        raise ValueError("Frozen experiment drift")
    if action in ("run", "replay"):
        execute(*prepared, live=action == "run")
    else:
        print("Frozen", len(prepared[1]), "exposed source groups")
