"""Compare a common condensed profile with and without anchored original evidence."""
from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from backbone_interface import OUT as CROSS, prepare as prior
from joint_context import engine, grading, metrics, probe, read, sha, wire
from qamc.common import parse_object

OUT = CROSS.with_name("profile_evidence_restoration_v1")
PRIVATE = OUT / "private"
DIRECT = "Q/DIRECT/SELECTED"
ARMS = ("PROFILE", "PROFILE_AND_QUOTES")
REFINER = """Refine the historical background into a compact profile for the current task.
Keep only source-supported information that improves this task or protects a relevant
requirement. Retain eligible small preferences, conditions, who is affected, exceptions
and the strength of constraints. Discard irrelevant experiences, unsupported beliefs
and private details not needed for the task. Do not answer the task. A preference is
not a shared requirement or a fact about someone else. Extract at most six brief profile
points, in the language of the task. Each point needs one numbered memory and an exact
continuous quotation supporting it. Include enough of the original quotation to retain
important conditions; do not expand or strengthen its meaning. Return exactly a JSON
object with a single key points: [{"profile":"...", "source_id":"...", "quote":"..."}].
Use an empty list when no point is appropriate."""
ACTOR_NOTE = """The selected historical evidence is an optional task-specific profile,
with exact historical quotations when available. Verify its scope against the current
task. Where profile and quotation disagree, follow the original wording within its
appropriate scope; disregard unsupported assumptions. Do not expose evidence labels."""


def parse_profile(raw, memories):
    result = parse_object(raw)
    if not isinstance(result, dict) or set(result) != {"points"}:
        raise ValueError("Wrong profile reply shape")
    points = result["points"]
    if not isinstance(points, list) or len(points) > 6:
        raise ValueError("Too many profile points")
    original = {record["memory_id"]: record["text"] for record in memories}
    seen = set()
    for point in points:
        if not isinstance(point, dict) or set(point) != {"profile", "source_id", "quote"}:
            raise ValueError("Wrong profile point shape")
        claim, source, quote = (point[k] for k in ("profile", "source_id", "quote"))
        if not all(isinstance(value, str) and value.strip() for value in (claim, source, quote)):
            raise ValueError("Blank profile field")
        if len(quote.strip()) < 8 or len(quote) > 500 or len(claim) > 480:
            raise ValueError("Profile field outside size contract")
        if source not in original or quote not in original[source]:
            raise ValueError("Profile point has no exact source quotation")
        identity = (source, quote)
        if identity in seen:
            raise ValueError("Duplicate profile evidence")
        seen.add(identity)
    return points


def actor_inputs(original, points, arm):
    packet = json.loads(original["messages"][1]["content"])
    prepared = []
    for item in points:
        note = {"memory_id": item["source_id"], "profile": item["profile"]}
        if arm == "PROFILE_AND_QUOTES":
            note["source_quote"] = item["quote"]
        prepared.append(note)
    request = deepcopy(original)
    request["messages"][0]["content"] += "\n\n" + ACTOR_NOTE
    request["messages"][1]["content"] = json.dumps(
        {"task": packet["task"], "source_evidence": prepared}, ensure_ascii=False)
    return request


def prepare():
    source, roster, wires, *_ = prior()
    if source != read(CROSS / "private/FROZEN.json"):
        raise ValueError("Original exposure roster changed")
    archive = {r["uid"]: r for r in read(CROSS / "RESULTS.json")["rows"] if r["method"] == DIRECT}
    cards, requests, refiners = {}, {}, {}
    for row in roster:
        card = row["card"]
        uid = card["uid"]
        request = wires[uid, DIRECT]
        if sha(request) != archive[uid]["actor_request_sha256"] or archive[uid]["actor_status"] != "OK":
            raise ValueError("Original Actor receipt mismatch")
        packet = json.loads(request["messages"][1]["content"])
        if set(packet) != {"task", "source_evidence"}:
            raise ValueError("Unexpected original Actor envelope")
        if len({r["memory_id"] for r in packet["source_evidence"]}) != len(packet["source_evidence"]):
            raise ValueError("Ambiguous archived source IDs")
        cards[uid] = card
        requests[uid] = request
        if packet["source_evidence"]:
            refiners[uid, "PROFILE"] = wire(REFINER, packet, 8192)
    if len(cards) != 18:
        raise ValueError("Unexpected assigned size")
    pin = {"code_sha256": sha(Path(__file__).read_bytes()),
           "service_reference_sha256": source["service_reference_sha256"],
           "basis_sha256": sha(source),
           "actor_schedule": [[uid, sha(req)] for uid, req in requests.items()],
           "refine_schedule": [[uid, sha(req)] for (uid, _), req in refiners.items()],
           "refs_sha256": sha([[uid, archive[uid]["score"], c["base_score"]] for uid, c in cards.items()])}
    return pin, cards, requests, refiners, archive


def summarize(cards, archive, rows, ledger):
    index = {(r["uid"], r["method"]): r for r in rows}
    group = {}
    for uid, card in cards.items():
        category = card["domain"] + "/" + card["stratum"]
        result = group.setdefault(category, {"assigned": 0, "common": 0, "methods": {}, "wins": 0, "losses": 0})
        result["assigned"] += 1
        values = {m: metrics(card, index[uid, m]["score"]) for m in ARMS}
        values["ARCHIVED_DIRECT"] = metrics(card, archive[uid]["score"])
        values["SPECIALIST"] = metrics(card, card["base_score"])
        if any(x is None for x in values.values()):
            continue
        for key in ("positions", "MR_denominator", "nonbold_denominator"):
            if len({x.get(key) for x in values.values()}) != 1:
                raise ValueError("Incompatible metric positions")
        result["common"] += 1
        for m, score in values.items():
            result["methods"].setdefault(m, Counter()).update(score)
        result["wins"] += values[ARMS[1]]["primary"] > values[ARMS[0]]["primary"]
        result["losses"] += values[ARMS[1]]["primary"] < values[ARMS[0]]["primary"]
    return {"paired": group,
            "preparation": Counter(r["profile_status"] for r in rows if r["method"] == ARMS[0]),
            "quote_activated": sum(bool(r["point_count"]) for r in rows if r["method"] == ARMS[1]),
            "physical": Counter(r["unit"]["stage"] for r in ledger),
            "status": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger)}


def run(pin, cards, requests, refiners, archive):
    engine.CAP = {"RefinedProfile": 18, "ProfileActor": 36, engine.RPE: 16, "BenchAttrs": 48, "PersistNative": 12}
    probe.RUN, probe.OUT, engine.OUT = OUT, PRIVATE, PRIVATE
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service_reference_sha256"]}
    if probe.read_reference()[1] != identity["service_reference_sha256"]:
        raise ValueError("Reference API changed")
    ledger = []
    with probe.runner_lock(OUT / "runner.lock"):
        def stage(name, jobs, cache=None):
            return engine.stage(name, jobs, identity, True, ledger, cache) if jobs else {}

        refinements = stage("RefinedProfile", refiners)
        jobs, status, profiles = {}, {}, {}
        for uid, original in requests.items():
            receipt = refinements.get((uid, "PROFILE"))
            if receipt is None:
                status[uid] = "EMPTY_INPUT_EXACT_ARCHIVE"
                continue
            status[uid] = receipt["status"]
            if receipt["status"] != "OK":
                continue
            try:
                memories = json.loads(original["messages"][1]["content"])["source_evidence"]
                profiles[uid] = parse_profile(receipt["answer"], memories)
            except (ValueError, TypeError, KeyError):
                status[uid] = "INVALID_PROFILE_CONTRACT"
                continue
            for arm in sorted(ARMS, key=lambda name: sha([uid, name])):
                jobs[uid, arm] = actor_inputs(original, profiles[uid], arm)
        actors = stage("ProfileActor", jobs)
        rows = []
        for uid, card in cards.items():
            for arm in ARMS:
                returned = actors.get((uid, arm), {})
                if status[uid] == "EMPTY_INPUT_EXACT_ARCHIVE":
                    returned = {"status": archive[uid]["actor_status"], "answer": archive[uid]["answer"],
                                "request_sha256": archive[uid]["actor_request_sha256"]}
                row = {"uid": uid, "method": arm, "benchmark": card["domain"], "stratum": card["stratum"],
                       "sources": card["payload"]["source_evidence"], "profile_status": status[uid],
                       "point_count": len(profiles[uid]) if uid in profiles else None,
                       "actor_status": returned.get("status", "PROFILE_UNAVAILABLE"),
                       "actor_request_sha256": returned.get("request_sha256"),
                       "answer": returned.get("answer"), "score": None, "score_flags": None}
                if row["actor_status"] == "OK" and row["answer"] == archive[uid]["answer"]:
                    row.update(score=archive[uid]["score"], score_flags=archive[uid].get("score_flags"))
                rows.append(row)
        grading(rows, stage)
        outcome = {"rows": rows, "ledger": ledger}
        probe.freeze(PRIVATE / "RESULTS.json", outcome)
    return outcome


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "run", "report"))
    args = cli.parse_args()
    pin, cards, requests, refiners, archive = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = PRIVATE / "FROZEN.json"
    if args.action == "freeze":
        probe.freeze(path, pin)
        print(json.dumps({"roots": Counter(c["domain"] for c in cards.values()),
                          "rewrites": len(refiners)}))
        return
    if read(path) != pin:
        raise ValueError("Frozen input schedule changed")
    if args.action == "run":
        if (PRIVATE / "RESULTS.json").exists():
            raise ValueError("Experiment already settled")
        outcome = run(pin, cards, requests, refiners, archive)
    else:
        outcome = read(PRIVATE / "RESULTS.json")
    print(json.dumps(summarize(cards, archive, **outcome), indent=2))


if __name__ == "__main__":
    main()
