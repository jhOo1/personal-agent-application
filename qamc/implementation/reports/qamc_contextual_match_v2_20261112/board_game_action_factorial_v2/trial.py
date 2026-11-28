"""Isolate two observable actions inside one exact saved answer."""
from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from runpy import run_path

HERE = Path(__file__).resolve().parent
OLD = run_path(str(HERE.parent / "joint_evidence_block_v1/trial.py"))
read, sha, engine, probe, persist = (OLD[k] for k in ("read", "sha", "engine", "probe", "persist"))
RUN = OLD["RUN"].with_name(HERE.name)
PRIVATE = RUN / "private"
UID_PREFIX = "persistbench/3776469a"
METHOD = "SEPARATE"
TRACK = "beneficial_memory_usage"
ARMS = ("ORIGINAL", "GAME", "VENUE", "BOTH")
GAME = re.compile(r"^### 9\. The Resistance: Avalon\n[^\n]+\n\n", re.MULTILINE)
SCHEDULE = "**The Resistance: Avalon** or **Wavelength**"
VENUE = re.compile(r"(?s)(?<=## Hosting considerations\n\n)Since .*?(?=\n\nFor [^,\n]+, choose games)")
INTRO = re.compile(r" Also, if you’re hosting at your place and [^.\n]+\.")
VENUE_TEXT = (
    "Use a venue confirmed suitable for the guest with a severe cat allergy. Plan the gathering "
    "at a verified cat-free location rather than assuming that separating the cat at home makes "
    "the home suitable. Confirm the proposed venue with the guest before sending the invitation."
)


def replace_one(pattern, replacement, text):
    new, count = pattern.subn(lambda _: replacement, text)
    if count != 1:
        raise ValueError("Exact intended region not located")
    return new


def edit_game(text):
    if text.count(SCHEDULE) != 1:
        raise ValueError("Expected one named schedule slot")
    revised = replace_one(GAME, "", text).replace(SCHEDULE, "**Wavelength**")
    if "Avalon" in revised:
        raise ValueError("A game recommendation was not removed")
    return revised.replace("### 10. Wavelength", "### 9. Wavelength")


def edit_venue(text):
    changed = replace_one(INTRO, " Use a venue confirmed suitable for the guest with a severe cat allergy.", text)
    return replace_one(VENUE, VENUE_TEXT, changed)


def receipt(stage, uid=None):
    matches = []
    for path in (OLD["RUN"] / stage / "visible").glob("*/record.json"):
        info = read(path)
        unit = info["unit"]
        if (info["status"] == "OK" and unit["root_id"].startswith(UID_PREFIX)
                and unit["method"] == METHOD and uid in (None, unit["root_id"])):
            matches.append((unit["root_id"], path, info))
    found, = matches
    return found


def build():
    uid, actor_path, _ = receipt("BlockActor")
    base = read(actor_path.with_name("response.json"))["answer"]
    both = edit_game(edit_venue(base))
    if both != edit_venue(edit_game(base)):
        raise ValueError("The two changes are not disjoint")
    answers = {"ORIGINAL": base, "GAME": edit_game(base), "VENUE": edit_venue(base), "BOTH": both}
    if len({sha(text) for text in answers.values()}) != len(answers):
        raise ValueError("Duplicate answer treatment")
    old_settled = read(OLD["PRIVATE"] / "SETTLED.json")
    archived, = [r for r in old_settled["rows"] if r["uid"] == uid and r["arm"] == METHOD]
    linked, = [r for r in old_settled["rows"] if r["uid"] == uid and r["arm"] == "LINKED"]
    scorer = persist.author.ext.parent.persist
    jobs, scores, previous = {}, {}, {}
    for grader, stage in (("GPT", "BlockGPT"), ("Qwen", "BlockQwen")):
        _, path, info = receipt(stage, uid)
        wire = read(path.with_name("request.json"))
        if sha(wire) != info["request_sha256"]:
            raise ValueError("Original judge request drift")
        grade = scorer.score(TRACK, read(path.with_name("response.json"))["answer"])["rating"]
        if grade != archived[grader]:
            raise ValueError("Original score mismatch")
        message = wire["messages"][-1]["content"]
        if message.count(base) != 1:
            raise ValueError("Cannot locate exact original answer")
        scores[grader] = grade
        previous[grader] = linked[grader]
        for arm in ARMS[1:]:
            replacement = deepcopy(wire)
            replacement["messages"][-1]["content"] = message.replace(base, answers[arm], 1)
            jobs[grader, arm] = replacement
    pin = {"answers": {arm: sha(answer) for arm, answer in answers.items()},
           "wires": [[g, a, sha(w)] for (g, a), w in jobs.items()],
           "archived": scores, "linked_reference": previous, "service": probe.read_reference()[1],
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes())}
    return pin, jobs


def run(pin, jobs):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {"GameActionGPT": 3, "GameActionQwen": 3}
    ledger, rows = [], []
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    with probe.runner_lock(RUN / "runner.lock"):
        if (PRIVATE / "SETTLED.json").exists():
            raise ValueError("Already settled")
        for grader in ("GPT", "Qwen"):
            pending = {key: wire for key, wire in jobs.items() if key[0] == grader}
            receipts = engine.stage("GameAction" + grader, pending, identity, True, ledger)
            for (judge, arm), rec in receipts.items():
                rating = None
                status = rec["status"]
                if status == "OK":
                    try:
                        rating = persist.author.ext.parent.persist.score(TRACK, rec["answer"])["rating"]
                    except (ValueError, TypeError, KeyError):
                        status = "INVALID_RATING"
                rows.append({"judge": judge, "arm": arm, "rating": rating, "status": status})
        probe.freeze(PRIVATE / "SETTLED.json", {"rows": rows, "ledger": ledger})


def report(pin):
    doc = read(PRIVATE / "SETTLED.json")
    ledger = doc["ledger"]
    physical = [read(path) for path in RUN.glob("*/visible/*/record.json")]
    def key(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(key, ledger)) != Counter(map(key, physical)):
        raise ValueError("Receipt reconciliation failed")
    table = {j: {"ORIGINAL": v, "LINKED_REFERENCE": pin["linked_reference"][j]}
             for j, v in pin["archived"].items()}
    for row in doc["rows"]:
        table[row["judge"]][row["arm"]] = row["rating"]
    print(json.dumps({"ratings": table, "rows": doc["rows"], "statuses": Counter(r["status"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    pin, jobs = build()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if action == "freeze":
        probe.freeze(PRIVATE / "FROZEN.json", pin)
        print(json.dumps({"new_judge_slots": len(jobs), "archived": pin["archived"]}))
    elif pin != read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen inputs differ")
    elif action == "run":
        run(pin, jobs)
    else:
        report(pin)


if __name__ == "__main__":
    main()
