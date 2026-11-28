"""Assess final actions for a single prespecified legal source across four fixed endpoints."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
crossed = run_path(str(BASE / "ipe_c_crossed_judge_v1/trial.py"))
old = crossed["old"]
engine, probe, sha = old.engine, old.probe, old.sha
read = crossed["read"]
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
STAGE = "FocalAction"
MODEL = "gpt-6.1-sol"
STATES = {"DELIVERED", "VIOLATED", "MENTION_ONLY", "ABSENT", "UNCLEAR"}
WITH_QUOTE = {"DELIVERED", "VIOLATED", "MENTION_ONLY"}
PROMPT = """Review the actual answer behavior for one focal record. You receive the original current request,
task context and facts, one historical record, and four anonymous complete answers. Identify the
specific requirement or preference from that record that can apply to the current context and owner.
Evaluate answers independently. Do not infer whether an answer was exposed to this record.
For each answer use:
DELIVERED: a concrete action or choice actually implements the focal preference at an appropriate
strength for this task. A strict constraint must hold across the actual recommended choices.
VIOLATED: the answer actually recommends a choice that conflicts with the applicable condition, or
forces a flexible personal preference as a hard rule for others. A warning does not cancel a conflicting
recommendation elsewhere in the same answer. Quote the executable conflict, not the warning.
MENTION_ONLY: recognizes the relevant preference without making it actionable.
ABSENT: no such use, mention, or recommendation violating a focal condition.
UNCLEAR: application or behavior cannot be resolved from the visible material.
For DELIVERED, VIOLATED or MENTION_ONLY quote a short, exact contiguous string from that answer.
For ABSENT or UNCLEAR leave the quote empty. Give a brief explanation of the concrete observation,
especially where one history contains multiple preferences. Use JSON only:
{"focal_action":"short task-relevant condition or choice",
 "answers":{"V1":{"state":"DELIVERED","quote":"verbatim","note":"short explanation"},
 "V2":{"state":"ABSENT","quote":"","note":"short explanation"},
 "V3":{"state":"UNCLEAR","quote":"","note":"short explanation"},
 "V4":{"state":"MENTION_ONLY","quote":"verbatim","note":"short explanation"}}}
Do not give benchmark labels, grades, method names, or a single best answer."""


def setup():
    _, cards, _ = crossed["build"]()
    archive = read(old.v41.OUT / "FROZEN.json")
    if archive["independent_confirmation"]:
        raise ValueError("Require exposed archive")
    roots = {r["uid"]: r for r in archive["roots"]}
    jobs, roster = {}, {}
    for uid, c in cards.items():
        if c["stratum"] not in ("B_only", "contains_C"):
            continue
        target = "C" if c["stratum"] == "contains_C" else "B"
        history = roots[uid]["original_sources"]
        if [m["memory_id"] for m in history] != [f"M{i}" for i in range(len(c["labels"]))]:
            raise ValueError("Cannot align focal position to original source identifier")
        candidates = [i for i, label in enumerate(c["labels"]) if label == target]
        index = min(candidates, key=lambda i: sha(["focal-action-v1", uid, i]))
        ordered = sorted(c["cells"], key=lambda pair: sha(["action-side-v1", uid, list(pair)]))
        mapped = {f"V{i}": key for i, key in enumerate(ordered, 1)}
        public = roots[uid]["public_task"]
        packet = {"task": public, "focal_history": history[index]["text"],
                  "answers": {side: c["cells"][endpoint][0] for side, endpoint in mapped.items()}}
        opaque = sha(["focal-action-v1", uid])
        wire = {"model": MODEL, "stream": True, "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}]}
        jobs[opaque, "OBSERVE"] = wire
        roster[opaque] = {"uid": uid, "selected": c["branch"], "intent": target,
                          "index": index, "sides": mapped}
    if Counter(c["intent"] for c in roster.values()) != {"B": 7, "C": 7}:
        raise ValueError("Fixed B/C roster drift")
    frozen = {"wires": [[key[0], sha(w)] for key, w in jobs.items()],
              "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
              "service": probe.read_reference()[1]}
    return frozen, roster, jobs


def parse(raw, answers):
    data = old.parse_object(raw)
    if (not isinstance(data, dict) or not isinstance(data.get("focal_action"), str)
            or not isinstance(data.get("answers"), dict)):
        raise ValueError("Unrecognized reply")
    usable = {}
    for side, item in data["answers"].items():
        if side not in answers or not isinstance(item, dict) or set(item) != {"state", "quote", "note"}:
            continue
        state, quote, note = (item[key] for key in ("state", "quote", "note"))
        if not isinstance(state, str) or state not in STATES or not isinstance(quote, str) or not isinstance(note, str):
            continue
        if state in WITH_QUOTE:
            if not quote.strip() or len(quote) > 350 or quote not in answers[side]:
                continue
        elif quote:
            continue
        usable[side] = item
    return data["focal_action"], usable


def run(pin, cards, jobs):
    ledger = []
    def check(vote, wire):
        answer_packet = json.loads(wire["messages"][-1]["content"])
        _, cells = parse(json.dumps(vote, ensure_ascii=False), answer_packet["answers"])
        if not cells:
            raise ValueError("No attributable answer cells")

    with probe.runner_lock(RUN / "runner.lock"):
        ids = list(cards)
        for batch, cohort in enumerate((ids[:2], ids[2:]), 1):
            with (patch.object(probe, "RUN", RUN), patch.object(probe, "OUT", PRIVATE / str(batch)),
                  patch.object(probe, "CAP", {"Blind": len(cohort)}), patch.object(probe, "validate_blind", check),
                  patch.object(probe, "answer_grid", lambda roots: {r["uid"]: {"ready": True} for r in roots}),
                  patch.object(probe, "blind_wire", lambda root, _: jobs[root["uid"], "OBSERVE"])):
                probe.blind({"roots": [{"uid": key} for key in cohort],
                             "service_reference_sha256": pin["service"]})
            if batch == 1 and all(read(RUN / "Blind" / sha(k) / "record.json")["status"]
                                  in {"FAILED_DELIVERY_UNKNOWN", "HTTP_ERROR"} for k in cohort):
                break
        rows = []
        for key, card in cards.items():
            folder = RUN / "Blind" / sha(key)
            path = folder / "record.json"
            observed, focal = {}, None
            status = "UNISSUED"
            if path.is_file():
                rec = read(path)
                if rec["request_sha256"] != sha(jobs[key, "OBSERVE"]):
                    raise ValueError("Physical request identity mismatch")
                ledger.append(rec)
                status = rec["status"]
            if status == "OK":
                packet = json.loads(jobs[key, "OBSERVE"]["messages"][-1]["content"])
                try:
                    focal, observed = parse(read(folder / "response.json")["answer"], packet["answers"])
                except (ValueError, TypeError, KeyError):
                    status = "INVALID_SCHEMA"
            rows.append({"key": key, "status": status, "focal_action": focal,
                         "observations": observed, "uid": card["uid"]})
        probe.freeze(PRIVATE / "RESULTS.json", {"rows": rows, "ledger": ledger})


def report(cards):
    data = read(PRIVATE / "RESULTS.json")
    out, paired = defaultdict(Counter), defaultdict(Counter)
    issues = Counter()
    for r in data["rows"]:
        card = cards[r["key"]]
        if r["status"] != "OK":
            issues[r["status"]] += 1
        for actor, arms in crossed["NAMES"].items():
            pair = {arm: r["observations"].get(which, {}).get("state") for which, (model, arm)
                    in card["sides"].items() if actor == model}
            k = f"{card['intent']}/{actor}"
            if None in pair.values() or "UNCLEAR" in pair.values():
                paired[k]["unknown"] += 1
                continue
            for tag, arm in (("Task", arms[0]), ("Memory", arms[1]), ("IPE_C", card["selected"][actor])):
                out[k + "/" + tag][pair[arm]] += 1
            task, memory = (pair[a] == "DELIVERED" for a in arms)
            paired[k][("both_delivered" if task else "neither_delivered") if task == memory else
                      ("task_only_delivers" if task else "memory_only_delivers")] += 1
    ledger = data["ledger"]
    stored = [read(p) for p in RUN.glob("Blind/*/record.json")]
    def key(row):
        return row["unit"]["root_id"], row["request_sha256"], row["status"]
    if Counter(map(key, ledger)) != Counter(map(key, stored)):
        raise ValueError("Physical calls do not reconcile")
    print(json.dumps({"choices": out, "paired": paired, "issues": issues,
                      "status": Counter(r["status"] for r in ledger),
                      "known_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("freeze", "run", "report"))
    action = p.parse_args().action
    pin, cards, jobs = setup()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = PRIVATE / "FREEZE.json"
    if action == "freeze":
        probe.freeze(marker, pin)
        print("Cases", Counter(c["intent"] for c in cards.values()), "maximum requests", len(jobs))
    elif read(marker) != pin:
        raise ValueError("Frozen observer request drift")
    elif action == "run":
        run(pin, cards, jobs)
    else:
        report(cards)
