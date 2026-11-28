"""Blind, evidence-linked behavior read on fixed Figure 14 endpoint outputs."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
previous = run_path(str(BASE / "rpeval_figure14_judge_v1" / "evaluate.py"))
archive, engine, probe, sha, FULL, ZERO, ROUTED = (previous[name] for name in
    ("archive", "engine", "probe", "sha", "FULL", "ZERO", "ROUTED"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
STAGE = "AnswerBehaviorRead"
ORIGINAL_CODE = "bd4ce954cdaf32884a3d8d5746660a99b2bf44e03fa850ade5c4a6a9e831a3f5"
PROMPT = """Review a single finished answer. Describe what it actually does as it relates to each visible memory. You do not know what the answering system received and should not infer causation from overlap. Do not evaluate whether history should have been applied and do not infer author labels. Mark NONE when the answer gives no observable implementation of the memory, TASK_SUPPORTED when similar content is independently called for by the current task or facts, SOFT when it concretely uses the content to support an option or choice, BINDING when it imposes that content as a requirement or qualifying condition, and UNCERTAIN if you cannot distinguish. Mere topical similarity is not a use. For TASK_SUPPORTED, SOFT or BINDING copy one short exact contiguous quote from the answer that shows the action. For NONE or UNCERTAIN leave the quote empty. Return only valid JSON with this shape: {"observations":[{"id":"existing exact memory ID","status":"NONE","quote":""}]}. Include every supplied memory ID once. No rationale and no overall score."""
STATUSES = {"NONE", "TASK_SUPPORTED", "SOFT", "BINDING", "UNCERTAIN"}
QUOTED = {"TASK_SUPPORTED", "SOFT", "BINDING"}


def prepare():
    fig = BASE / "rpeval_figure14_judge_v1" / "FORMAT_CONTROL.json"
    outcomes = archive.read(fig)
    old = previous["old"]
    old_plan = old["prepare"]()
    ext = old["ext"]
    endpoints = {r["uid"]: r for r in archive.read(old["ENDPOINTS"] / "RESULTS.json")["rows"]}
    v41 = old["v41"]
    bank = {r["uid"]: r for r in archive.read(v41.formal.OUT / "RESULT_ROWS.json")
            if r["method"] == FULL and r["actor_status"] == "OK"}
    eligible = {row["uid"]: row for row in old_plan["cards"]}
    contains_c = sorted((r for r in eligible.values() if r["stratum"] == "contains_C"),
                        key=lambda r: sha(["figure-behavior-positive-controls", r["uid"]]))[:2]
    records = [r for r in eligible.values() if r["stratum"] == "all_A"] + contains_c
    if len(records) != 6:
        raise ValueError("Need all four all-A roots and two fixed C-containing controls")
    fig_cells = {r["case"]: r for r in outcomes["cases"]}
    cases, jobs, annotations = {}, {}, {}
    for item in records:
        uid = item["uid"]
        suffix = "/".join(uid.split("/")[-2:])
        full, old_row = bank[uid], endpoints[uid]
        wire = full["actor_request"]
        if sha(wire) != full["actor_request_sha256"]:
            raise ValueError("Archived Actor request drift")
        actor_packet = json.loads(wire["messages"][1]["content"])
        history = actor_packet["source_evidence"]
        labels = dict(zip((m["memory_id"] for m in history), old_row["labels"], strict=True))
        if len(labels) != len(history):
            raise ValueError("Ambiguous history identifiers")
        cases[uid] = {"case": suffix, "labels": labels, "stratum": item["stratum"], "routed": item["routed"],
                      "figure_grade": fig_cells[suffix]["grades"], "adapted": item["adapted"]}
        for method, answer in ((FULL, full["answer"]), (ZERO, old_row["no_history_state"]["answer"])):
            if sha(answer) != item["endpoint_hashes"][method]:
                raise ValueError("Archived endpoint answer drift")
            packet = {k: actor_packet[k] for k in ("query", "current_context", "facts")}
            packet["memories"], packet["answer"] = history, answer
            base = item["requests"][method]
            opaque = sha(["figure-behavior-side-v1", uid, method])
            jobs[opaque, "REVIEW"] = {**base, "model": "qwen3.8-flash", "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}]}
            annotations[opaque] = (uid, method)
    pin = {"figure_outcomes_sha256": sha(fig.read_bytes()), "caps": {STAGE: len(jobs)},
           "wire_hashes": {key[0]: sha(req) for key, req in jobs.items()},
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "service_reference_sha256": probe.read_reference()[1]}
    return pin, cases, jobs, annotations


def read_review(raw, packet):
    expected = {m["memory_id"] for m in packet["memories"]}
    parsed = previous["old"]["parse_object"](raw)
    observations = parsed.get("observations") if isinstance(parsed, dict) else None
    if not isinstance(observations, list):
        raise ValueError("Observation array missing")
    counts, good = Counter(), {}
    for cell in observations:
        if not isinstance(cell, dict) or set(cell) != {"id", "status", "quote"}:
            counts["bad_schema"] += 1
            continue
        mid, status, quote = (cell[k] for k in ("id", "status", "quote"))
        if not all(isinstance(value, str) for value in (mid, status, quote)):
            counts["bad_type"] += 1
        elif mid not in expected or status not in STATUSES:
            counts["bad_id_or_status"] += 1
        elif mid in good:
            counts["duplicate_id"] += 1
            good[mid] = {"status": "UNCERTAIN", "quote": ""}
        elif (status in QUOTED and (not quote or quote not in packet["answer"] or len(quote) > 300)
              or status not in QUOTED and quote):
            counts["bad_quote"] += 1
        else:
            good[mid] = {"status": status, "quote": quote}
    counts["absent_or_invalid"] = len(expected - good.keys())
    return good, counts


def execute(pin, cases, jobs, annotations, live):
    probe.OUT = engine.OUT = PRIVATE
    probe.RUN = RUN
    engine.CAP = pin["caps"]
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service_reference_sha256"]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        replies = engine.stage(STAGE, jobs, identity, live, ledger)
        audits = {}
        errors = Counter()
        for (key, tag), response in replies.items():
            uid, method = annotations[key]
            entries, state = {}, response["status"]
            if state == "OK":
                try:
                    entries, reject = read_review(response["answer"], json.loads(jobs[key, tag]["messages"][1]["content"]))
                    errors.update(reject)
                except (KeyError, TypeError, ValueError, AttributeError):
                    state = "INVALID_REVIEW"
            audits[uid, method] = (state, entries)
        data, diagnosis = [], defaultdict(Counter)
        for uid, item in cases.items():
            views = {m: audits[uid, m] for m in (FULL, ZERO)}
            views[ROUTED] = views[item["routed"]]
            info = {"case": item["case"], "stratum": item["stratum"], "positions": len(item["labels"]), "arms": {}}
            paired = {id for id in item["labels"] if all(id in views[m][1] and views[m][1][id]["status"] != "UNCERTAIN"
                                                      for m in (FULL, ZERO))}
            for method, (state, entries) in views.items():
                counts = Counter()
                for mid in sorted(paired):
                    label = item["labels"][mid]
                    status = entries[mid]["status"]
                    counts[label + "/" + status] += 1
                diagnosis[item["stratum"] + "/" + method].update(counts)
                info["arms"][method] = {"status": state, "paired_cells": counts,
                                        "figure_grade": item["figure_grade"][method],
                                        "adapted_match": item["adapted"][method]["match"]}
            info["paired_determinate_positions"] = len(paired)
            data.append(info)
        aggregate = {"cases": data, "behavior_counts": diagnosis, "errors": errors, "calls": len(ledger),
                     "transport": Counter(x["status"] for x in ledger),
                     "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                     "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                     "automatic_retries": sum(r["automatic_retries"] for r in ledger)}
        records = {"summary": aggregate, "reviews": [[u, m, v] for (u, m), v in audits.items()], "ledger": ledger}
        target = PRIVATE / "RESULTS.json"
        if live:
            probe.freeze(target, records)
        elif sha(archive.read(target)) != sha(records):
            raise ValueError("Behavior audit settlement drift")
        print(json.dumps(aggregate, sort_keys=True, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "replay"))
    action = parser.parse_args().action
    data = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    location = PRIVATE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(location, data[0])
        found, _ = previous["previous"]["support"]["prior"]["find_archived"](data[2], BASE.parents[1])
        if found:
            raise ValueError("Preserve earlier exact runs")
        print({"cases": len(data[1]), "calls": len(data[2])})
    else:
        saved = archive.read(location)
        if saved != data[0] and (action != "replay" or saved != {**data[0], "code": ORIGINAL_CODE}):
            raise ValueError("Frozen judge-audit inputs changed")
        execute(saved, *data[1:], live=action == "run")
