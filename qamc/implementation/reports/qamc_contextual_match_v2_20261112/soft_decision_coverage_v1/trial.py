"""Compare ranked soft evidence with equal-cardinality decision coverage."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
old = run_path(str(BASE / "protected_clause_exposure_v1/trial.py"))
archive, engine, probe, sha, read = (old[k] for k in ("archive", "engine", "probe", "sha", "read"))
RUN = old["RUN"].with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("TOP", "COVER")
PROMPT = """You evaluate original historical records for a current task. The draft was written
without consulting those records. Identify concrete, useful optional improvements in existing
decisions that the draft does not already achieve. A remembered preference must not replace
the user's current objective, restrict people who did not express it, or undermine task facts
or hard requirements. Do not assume that a relevant source necessarily changes an action.
For each proposed source, attach one indexed existing D paragraph containing the decision it
would improve. Do not use headings, boilerplate, generic introductions or end questions as
decision paragraphs. If a source has no useful new decision impact or only prompts a repeat
of an already offered choice, omit it. Order by expected task benefit, best first. Return
only {"ranked":[{"source_id":"M1","decision_id":"D2"}]} with up to four different source IDs,
or {"ranked":[]} if no sources should be used. Do not generate an answer or paraphrase the draft."""


def parse(raw, sources, draft):
    value = old["parse_object"](raw)
    if not isinstance(value, dict) or set(value) != {"ranked"} or not isinstance(value["ranked"], list):
        raise ValueError("Invalid planner response")
    rows = value["ranked"]
    if len(rows) > 4:
        raise ValueError("Too many associations")
    if any(not isinstance(row, dict) or set(row) != {"source_id", "decision_id"}
           or not all(isinstance(v, str) for v in row.values())
           or row["source_id"] not in sources or row["decision_id"] not in draft for row in rows):
        raise ValueError("Unknown original source or decision")
    if len({row["source_id"] for row in rows}) != len(rows):
        raise ValueError("Repeated source")
    return rows


def alternatives(rows):
    first, repeated = [], []
    used = set()
    for row in rows:
        dest = first if row["decision_id"] not in used else repeated
        dest.append(row["source_id"])
        used.add(row["decision_id"])
    return {"TOP": [row["source_id"] for row in rows[:2]], "COVER": (first + repeated)[:2]}


def prepare():
    frozen = read(BASE / "counterfactual_rpeval_v41/FROZEN.json")
    prior = read(BASE / "source_local_reentry_v1/ELIGIBILITY.json")
    panel = read(BASE / "soft_only_nested_contrasts_v1/PAIRS.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Expected exposed development inputs")
    roots = {r["uid"]: r for r in frozen["roots"]}
    endpoints = {e["uid"]: e for pair in prior["pairs"] for e in pair["endpoints"]}
    items = {}
    for pair in panel["pairs"]:
        for arm, track in (("all_A", "all_A"), ("only_B_added", "B_expanded")):
            uid = pair[arm]
            root, saved = roots[uid], endpoints[uid]
            historical = saved["methods"]["TASK_ONLY"]
            if root["group"] != pair["root"] or saved["route"] not in ("NO_HISTORY", "TASK_ONLY", "OFF"):
                # Exact task-only identity and explicit selector path, independent of score.
                if root["group"] != pair["root"] or saved["route"] is not False:
                    raise ValueError("Archived route/group drift")
            if not historical["answer"] or historical["grade"] is None or historical["visible_ids"]:
                raise ValueError("Missing valid archived task-only endpoint")
            parts = [text for text in re.split(r"\n\s*\n", historical["answer"]) if text.strip()]
            draft = {f"D{i}": v for i, v in enumerate(parts, 1)}
            sources = root["original_sources"]
            if len({s["memory_id"] for s in sources}) != len(sources):
                raise ValueError("Source identity is ambiguous")
            task = {key: root["public_task"][key] for key in ("query", "current_context", "facts")}
            wire = archive.body(PROMPT, {"task": task, "sources": sources, "task_only_draft": draft}, 4096)
            old["validate_public_request"](wire)
            items[uid] = {"root": root, "track": track, "draft": draft, "sources": sources,
                          "planner": wire, "base": historical, "rp": saved["methods"]["RPR_PAPER_FULL"]}
    if len(items) != 18 or len({r["root"]["group"] for r in items.values()}) != 9:
        raise ValueError("Panel coverage drift")
    pin = {"selection": {uid: sha(r["planner"]) for uid, r in items.items()},
           "archive": {uid: [r["base"]["actor_sha256"], sha(r["base"]["answer"]),
                             r["root"]["archived_actor_sha256"]] for uid, r in items.items()},
           "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "code": sha(Path(__file__).read_bytes()), "service": probe.read_reference()[1]}
    return pin, items


def actor(item, ids):
    root = item["root"]
    wire = deepcopy(root["archived_actor_request"])
    if sha(wire) != root["archived_actor_sha256"]:
        raise ValueError("Archived Actor prompt drift")
    packet = json.loads(wire["messages"][1]["content"])
    if packet["source_evidence"] != item["sources"]:
        raise ValueError("Source manifest drift")
    kept = [s for s in packet["source_evidence"] if s["memory_id"] in ids]
    packet["source_evidence"] = kept
    packet["preference_use_policy"] = [{"memory_id": s["memory_id"], "policy": "B"} for s in kept]
    wire["messages"][1]["content"] = json.dumps(packet, ensure_ascii=False)
    old["validate_public_request"](wire)
    return wire


def run(pin, items):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {"SoftCoveragePlan": 18, "SoftCoverageActor": 36, engine.RPE: 36}
    ident = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger, rows, next_jobs = [], [], {}
    with probe.runner_lock(RUN / "runner.lock"):
        if (PRIVATE / "SETTLED.json").exists():
            raise ValueError("Already settled")
        def stage(name, jobs, cache=None):
            return engine.stage(name, jobs, ident, True, ledger, cache) if jobs else {}
        for (uid, _), receipt in stage("SoftCoveragePlan", {(u, "SHARED"): c["planner"] for u, c in items.items()}).items():
            item = items[uid]
            found = None
            status = receipt["status"]
            if status == "OK":
                try:
                    found = parse(receipt["answer"], {s["memory_id"] for s in item["sources"]}, item["draft"])
                except (ValueError, TypeError, KeyError):
                    status = "INVALID_PLAN"
            choice = alternatives(found or [])
            for arm in ARMS:
                selected = choice[arm]
                row = {"uid": uid, "method": arm, "benchmark": "RPEval", "stratum": item["track"],
                       "group": item["root"]["group"], "selected": selected, "answer": None, "score": None,
                       "score_flags": None, "actor_status": status, "sources": item["sources"]}
                if selected:
                    next_jobs[uid, arm] = actor(item, selected)
                elif found == []:
                    row.update(answer=item["base"]["answer"], score=item["base"]["grade"],
                               score_flags=item["base"]["flags"], actor_status="OK")
                rows.append(row)
        delivered = stage("SoftCoverageActor", next_jobs)
        for row in rows:
            rec = delivered.get((row["uid"], row["method"]))
            if rec is not None:
                row.update(answer=rec.get("answer"), actor_status=rec["status"])
            if row["answer"]:
                row["answer_sha256"] = sha(row["answer"])
        old["grading"](rows, stage)
        probe.freeze(PRIVATE / "SETTLED.json", {"rows": rows, "ledger": ledger})


def report(items):
    result = read(PRIVATE / "SETTLED.json")
    ledger = result["ledger"]
    physical = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    def key(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(key, physical)) != Counter(map(key, ledger)):
        raise ValueError("Ledger mismatch")
    groups = defaultdict(dict)
    for row in result["rows"]:
        groups[row["uid"]][row["method"]] = row
    table = defaultdict(lambda: defaultdict(Counter))
    for uid, item in items.items():
        group = groups[uid]
        track = item["track"]
        c = table[track]
        c["allocation"]["assigned"] += 1
        c["allocation"]["exposure_changed"] += group["TOP"]["selected"] != group["COVER"]["selected"]
        scores = {k: row["score"] for k, row in group.items()} | {
            "IPE-C": item["base"]["grade"], "RP": item["rp"]["grade"]}
        if not all((s or {}).get("match") for s in scores.values()):
            continue
        c["allocation"]["common"] += 1
        clean = not any(row["score_flags"] for row in group.values()) and not (
            item["base"]["flags"] or item["rp"]["flags"]
        )
        for arm, score in scores.items():
            values = dict(score["match"]) | {k: score[k] for k in ("OPB", "UPB", "FM") if type(score.get(k)) is int}
            c[arm].update(values)
            if clean:
                c["unflagged/" + arm].update(values)
    print(json.dumps({"table": table, "statuses": Counter(r["status"] for r in ledger),
                      "stages": Counter(r["unit"]["stage"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    pin, items = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if action == "freeze":
        probe.freeze(PRIVATE / "FROZEN.json", pin)
        print(json.dumps(Counter(r["track"] for r in items.values())))
    elif pin != read(PRIVATE / "FROZEN.json"):
        raise ValueError("Freeze drift")
    elif action == "run":
        run(pin, items)
    else:
        report(items)


if __name__ == "__main__":
    main()
