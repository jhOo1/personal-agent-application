"""Measure the incremental effect of the literal check on the same proposals."""
from collections import Counter
import json
from pathlib import Path
import sqlite3

from qamc.common import parse_object, sha

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent.parent.name
RUN = ROOT / "runs" / BASE / "rpe_constraint_veto_v1"
PARENT = RUN.with_name("rpe_heterogeneous_reward_v1")
MAP = {"RPR_PAPER_FULL": "RP", "DES2GEN_FULL": "Des2Gen", "MEMADAPTER_FULL": "MemAdapter"}


def read(path):
    return json.loads(path.read_text())


def replay():
    packet = read(PARENT / "BLIND_PACKETS.json")
    bindings = read(PARENT / "BINDING.json")
    locked = read(RUN / "LOCKED_CHOICES.json")
    grades = read(RUN / "SCORED_ROWS.json")
    db = RUN / "ConstraintVeto" / "samples.sqlite"
    with sqlite3.connect(f"{db.absolute().as_uri()}?mode=ro", uri=True) as source:
        records = source.execute("SELECT unit_json, request_sha, status, response_json FROM samples").fetchall()
    if len(records) != len(bindings):
        raise ValueError("Incomplete single-run sample inventory")
    private, counts = {}, Counter()
    totals = Counter()
    changed = Counter()
    for unit, digest, state, raw in records:
        key = json.loads(unit)["root_id"]
        if digest != locked[key]["request_sha256"]:
            raise ValueError("Sample does not bind to frozen choice")
        choices = bindings[key]["order"]
        default, = (cid for cid, peer in choices.items() if MAP[peer] == "RP")
        proposal, candidate = None, default
        if state == "COMPLETE":
            try:
                proposal = parse_object(json.loads(raw)["answer"])
                other = proposal.get("alternative_id")
                if isinstance(other, str) and other in packet[key]["candidates"]:
                    candidate = other
            except (ValueError, TypeError, KeyError, AttributeError):
                counts["unreadable_response"] += 1
        program_choice = locked[key]["choice"] or default
        counts["program_switches"] += program_choice != default
        counts["proposed_switches"] += candidate != default
        counts["changed_by_program"] += program_choice != candidate
        uid = bindings[key]["uid"]
        score = grades[uid]
        private[uid] = {"unchecked": MAP[choices[candidate]], "checked": MAP[choices[program_choice]],
                        "status": locked[key]["status"], "proposal": proposal}
        if not score["historical_overlap"]:
            continue
        original = score["scores"][MAP[choices[candidate]]]
        verified = score["scores"]["Veto"]
        for name, grade in (("unchecked", original), ("checked", verified)):
            totals[f"{name}_match"] += grade["matched"]
            totals[f"{name}_total"] += grade["total"]
            for metric in ("OPB", "UPB", "FM"):
                totals[f"{name}_{metric}"] += grade["severity"][metric]
        if candidate != program_choice:
            changed[score["label"]] += 1
    return ({"assignments": len(private), "actions": dict(counts), "affected_labels": dict(changed),
             "historical_overlap": dict(totals), "model_calls": 0}, private)


if __name__ == "__main__":
    summary, details = replay()
    text = json.dumps(details, ensure_ascii=False, indent=2) + "\n"
    private = RUN / "UNCHECKED_PROPOSALS_PRIVATE.json"
    if private.exists():
        if private.read_text() != text:
            raise ValueError("Private proposal replay changed")
    else:
        with private.open("x") as stream:
            stream.write(text)
    print(json.dumps(summary, indent=2))
