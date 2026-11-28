"""One frozen same-wire intervention on separable background facts."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from backbone_interface import OUT as CROSSED, engine, grading, probe, read, sha

OUT = CROSSED.with_name("auxiliary_fact_exposure_v1")
PRIVATE = OUT / "private"
ARM = "WITHHOLD_SCHEDULE"
BASE = "D/DIRECT/SELECTED"


def prepare():
    roster = [x for x in read(CROSSED / "RESULTS.json")["rows"]
              if x["benchmark"] == "BenchPreS" and x["method"] == BASE]
    manifest = read(CROSSED / "private" / "DActor_MANIFEST.json")["units"]
    registered = {item["unit"]["root_id"]: item["request"] for item in manifest
                  if item["unit"]["method"] == BASE}
    eligible = []
    for row in roster:
        wire = registered.get(row["uid"])
        if wire is None:
            continue
        packet = json.loads(wire["messages"][1]["content"])
        if "Request hearing accommodation." in packet["task"]["query"]:
            eligible.append((row, wire, packet))
    if len(eligible) != 1:
        raise ValueError("Require exactly one registered hearing request")
    baseline, original, packet = eligible[0]
    if baseline["actor_status"] != "OK" or not baseline["score"]:
        raise ValueError("Require completed original control")
    if sha(original) != baseline["actor_request_sha256"]:
        raise ValueError("Actor wire mismatch")
    return baseline, original, packet


def compile_edit(original, packet, indices):
    if len(indices) != 2 or len(set(indices)) != 2:
        raise ValueError("Register exactly two reviewed background occurrences")
    facts = packet["task"]["facts"]
    withheld = [facts[i] for i in indices]
    if any(not isinstance(v, str) or not v.strip() for v in withheld):
        raise ValueError("Invalid excluded Fact")
    if any(facts.count(v) != 1 for v in withheld):
        raise ValueError("Ambiguous original Fact occurrence")
    modified = deepcopy(packet)
    modified["task"]["facts"] = [v for i, v in enumerate(facts) if i not in indices]
    content = json.dumps(modified, ensure_ascii=False)
    if any(v.casefold() in content.casefold() for v in withheld):
        raise ValueError("Withheld Fact text survives in another field")
    # Recover the original encoder without supposing whitespace changes are harmless.
    encoded = original["messages"][1]["content"]
    clean = deepcopy(original)
    for value in withheld:
        encoded_value = json.dumps(value, ensure_ascii=False)
        if encoded.count(encoded_value) != 1:
            raise ValueError("Expected one exact JSON list occurrence")
        offset = encoded.index(encoded_value) + len(encoded_value)
        suffix = encoded[offset:]
        if not suffix.lstrip().startswith(","):
            raise ValueError("Expected a non-final list entry for this fixed case")
        end = offset + suffix.index(",") + 1
        while end < len(encoded) and encoded[end].isspace():
            end += 1
        encoded = encoded[:offset - len(encoded_value)] + encoded[end:]
    if json.loads(encoded) != modified:
        raise ValueError("Unexpected request mutation")
    clean["messages"][1]["content"] = encoded
    return clean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--at", type=int, nargs=2)
    args = parser.parse_args()
    base, raw, packet = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    frozen = PRIVATE / "FROZEN.json"
    if args.action == "freeze" and args.at is None:
        parser.error("Freeze requires the reviewed Fact offsets")
    indices = sorted(args.at) if args.action == "freeze" else read(frozen)["background_indices"]
    new = compile_edit(raw, packet, indices)
    service = read(CROSSED / "private" / "FROZEN.json")["service_reference_sha256"]
    if probe.read_reference()[1] != service:
        raise ValueError("Reference service changed")
    pin = {"background_indices": indices, "input_sha256": sha(raw), "edited_sha256": sha(new),
           "code_sha256": sha(Path(__file__).read_bytes()), "service_reference_sha256": service}
    if args.action == "freeze":
        probe.freeze(frozen, pin)
        print(json.dumps({"roots": 1, "removed_facts": 2, "new_actor_cap": 1, "new_judge_cap": 6}))
        return
    if read(frozen) != pin:
        raise ValueError("The registered diagnostic changed")
    if (PRIVATE / "RESULTS.json").exists():
        raise ValueError("Diagnostic is already settled")
    probe.RUN, probe.OUT, engine.OUT = OUT, PRIVATE, PRIVATE
    engine.CAP = {"AuxActor": 1, engine.RPE: 0, "BenchAttrs": 6, "PersistNative": 0}
    ledger = []
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": service}
    uid = base["uid"]
    with probe.runner_lock(OUT / "runner.lock"):
        def stage(name, jobs, cache=None):
            return engine.stage(name, jobs, identity, True, ledger, cache) if jobs else {}
        receipt = stage("AuxActor", {(uid, ARM): new})[uid, ARM]
        row = {**base, "method": ARM, "actor_request_sha256": sha(new),
               "actor_status": receipt["status"], "answer": receipt.get("answer"),
               "score": None, "score_flags": None}
        if row["actor_status"] == "OK":
            if row["answer"] == base["answer"]:
                row.update(score=base["score"], score_flags=base["score_flags"])
            else:
                grading([row], stage)
        probe.freeze(PRIVATE / "RESULTS.json", {"base": base, "edited": row, "ledger": ledger})
    print(json.dumps({"actor": row["actor_status"], "gradable": bool(row["score"]),
                      "requests": len(ledger), "statuses": Counter(x["status"] for x in ledger),
                      "reported_tokens": sum((x.get("usage") or {}).get("total_tokens") or 0 for x in ledger)}, indent=2))


if __name__ == "__main__":
    main()
