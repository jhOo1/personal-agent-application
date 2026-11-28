"""Witness an applicable, currently violated constraint before exposing it."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
old = run_path(str(BASE / "protected_clause_exposure_v1/trial.py"))
archive, engine, probe, sha, read = (old[k] for k in ("archive", "engine", "probe", "sha", "read"))
RUN = old["RUN"].with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("GENERAL", "WITNESSED")
CASES = {
    "off_C": ("implicit/115", "implicit/117", "implicit/148"),
    "on_C": ("explicit/006", "explicit/047", "explicit/056"),
    "all_A": ("explicit/015", "explicit/120", "explicit/063", "implicit/094"),
}
COMMON = """Review the current task, full original historical records and saved answer.
Return at most two sources containing explicit hard constraints relevant to the answer.
A hard constraint must directly constrain a concrete choice in this task for a person
affected by that choice. Preserve the difference between a strict restriction and a
taste, anecdote, or flexible preference. Do not assume the user decides for someone
else. Quote an exact complete excerpt of the original record including its condition
and negation. Ignore a requirement already consistently fulfilled. Return JSON only:
{"constraints":[{"source_id":"M0","source_quote":"exact text","draft_quote":null}]}
or {"constraints":[]} when you cannot justify a revision."""
PROMPTS = {
    "GENERAL": """Identify applicable unmet requirements by reviewing the draft as a whole.
Use null for draft_quote.""",
    "WITNESSED": """Only propose a requirement if the saved answer recommends a concrete
action that would violate it. Put the exact recommendation from that answer in
draft_quote. Similar wording or an abstract topical conflict is not sufficient. A
requirement mentioned as an assumption may warrant keeping the original draft.
Do not recommend a new action or edit the draft in the output.""",
}
ACTOR = """Answer the current task in the original language and requested format. Treat the
constraint excerpts as applicable only to the concrete target and scope supported by
the complete original records and the request. Do not promote any other historical
style, belief, preference or person into a task requirement. Do not assume current
availability. Give a complete feasible answer with practical alternatives when needed.
Do not mention the policy, identifiers, or the selection process."""


def parse(raw, arm, item):
    obj = old["parse_object"](raw)
    if not isinstance(obj, dict) or set(obj) != {"constraints"} or not isinstance(obj["constraints"], list):
        raise ValueError("Invalid constraint response")
    rows = obj["constraints"]
    if len(rows) > 2:
        raise ValueError("Too many proposed requirements")
    sources = {s["memory_id"]: s["text"] for s in item["root"]["original_sources"]}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"source_id", "source_quote", "draft_quote"}:
            raise ValueError("Invalid constraint fields")
        key, quote, draft_quote = (row[k] for k in ("source_id", "source_quote", "draft_quote"))
        if (not isinstance(key, str) or key not in sources or key in seen
                or not isinstance(quote, str) or not quote.strip() or sources[key].count(quote) != 1):
            raise ValueError("Unverified source")
        if arm == "WITNESSED":
            if not isinstance(draft_quote, str) or not draft_quote.strip() or item["draft"].count(draft_quote) != 1:
                raise ValueError("Unverified answer action")
        elif draft_quote is not None:
            raise ValueError("Unexpected witness in general control")
        seen.add(key)
    return rows


def actor(item, rows):
    root = item["root"]
    keys = {row["source_id"] for row in rows}
    packet = root["public_task"] | {"source_evidence": [s for s in root["original_sources"]
                                                        if s["memory_id"] in keys],
        "constraint_excerpts": [{k: row[k] for k in ("source_id", "source_quote")} for row in rows]}
    wire = archive.body(ACTOR, packet, 8192)
    old["validate_public_request"](wire)
    return wire


def prepare():
    exposed = read(BASE / "counterfactual_rpeval_v41/FROZEN.json")
    if exposed["independent_confirmation"]:
        raise ValueError("Expected exposed-only archive")
    roots = {row["uid"]: row for row in exposed["roots"]}
    archived = {r["uid"]: r for r in read(BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    missing = {"rpeval/formal_multi_v1/" + suffix for cases in CASES.values() for suffix in cases} - roots.keys()
    if missing:
        from replay_panel import source_root
        formal = archive.v41.formal.OUT
        manifest = read(formal / "PLAN.json")
        permitted = {c["uid"] for c in manifest["cases"] if c["independent_confirmation"] is False}
        if not missing <= permitted:
            raise ValueError("Missing task is outside exposed development")
        official = {r["uid"]: r for r in read(formal / "RESULT_ROWS.json")
                    if r["uid"] in missing and r["method"] == "RPR_PAPER_FULL"}
        ranks = {r["uid"]: r for r in read(formal / "RPR_RANK_FUSION_AUDIT_300.json")["rows"]
                 if r["uid"] in missing}
        for uid in missing:
            roots[uid] = source_root(official[uid], ranks[uid]) | {"group": archived[uid]["source_group"]}
    items, jobs = {}, {}
    for track, cases in CASES.items():
        for suffix in cases:
            uid = "rpeval/formal_multi_v1/" + suffix
            root, rec = roots[uid], archived[uid]
            if rec["old_route"] == "REUSE_RP":
                draft = root["archived"]["RPR_PAPER_FULL"]["answer"]
            else:
                draft = rec["no_history_state"]["answer"]
            base = rec["ipe_c"]
            if not draft or sha(draft) != base["answer_sha256"] or not base.get("grade"):
                raise ValueError("Unverified IPE-C answer or score")
            if (track == "off_C" and rec["old_route"] == "REUSE_RP"
                    or track == "on_C" and rec["old_route"] != "REUSE_RP"):
                raise ValueError("Unexpected baseline route")
            items[uid] = {"root": root, "draft": draft, "base": base, "track": track}
            packet = root["public_task"] | {"source_evidence": root["original_sources"], "draft": draft}
            for arm in ARMS:
                wire = archive.body(COMMON + "\n" + PROMPTS[arm], packet, 4096)
                old["validate_public_request"](wire)
                jobs[uid, arm] = wire
    pin = {"jobs": [[uid, arm, sha(w)] for (uid, arm), w in jobs.items()],
           "baseline": {uid: sha(i["draft"]) for uid, i in items.items()},
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "service": probe.read_reference()[1]}
    return pin, items, jobs


def run(pin, items, jobs):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {"ConcreteGate": 20, "ConcreteActor": 20, engine.RPE: 20}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    ledger, rows, future = [], [], {}
    with probe.runner_lock(RUN / "runner.lock"):
        if (PRIVATE / "SETTLED.json").exists():
            raise ValueError("Already settled")
        def stage(name, requests, cache=None):
            return engine.stage(name, requests, identity, True, ledger, cache) if requests else {}
        for (uid, arm), rec in stage("ConcreteGate", jobs).items():
            item = items[uid]
            root = item["root"]
            status = rec["status"]
            selected = None
            if status == "OK":
                try:
                    selected = parse(rec["answer"], arm, item)
                except (ValueError, KeyError, TypeError):
                    status = "INVALID_CONSTRAINT"
            row = {"uid": uid, "method": arm, "benchmark": "RPEval", "stratum": item["track"],
                   "group": root["group"], "actor_status": status, "sources": root["original_sources"],
                   "answer": None, "score": None, "score_flags": None, "selected": selected}
            if selected:
                future[uid, arm] = actor(item, selected)
            elif selected == []:
                row.update(answer=item["draft"], score=item["base"]["grade"], score_flags=item["base"]["flags"])
            rows.append(row)
        made = stage("ConcreteActor", future)
        for row in rows:
            key = row["uid"], row["method"]
            if key in made:
                rec = made[key]
                row.update(answer=rec.get("answer"), actor_status=rec["status"])
                if row["answer"] and sha(row["answer"]) == items[row["uid"]]["base"]["answer_sha256"]:
                    base = items[row["uid"]]["base"]
                    row.update(score=base["grade"], score_flags=base["flags"])
        old["grading"](rows, stage)
        probe.freeze(PRIVATE / "SETTLED.json", {"rows": rows, "ledger": ledger})


def report(items):
    data = read(PRIVATE / "SETTLED.json")
    ledger = data["ledger"]
    actual = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    def key(row):
        return row["unit"]["stage"], row["request_sha256"], row["status"]
    if Counter(map(key, actual)) != Counter(map(key, ledger)):
        raise ValueError("Receipt mismatch")
    by_uid = defaultdict(dict)
    for row in data["rows"]:
        by_uid[row["uid"]][row["method"]] = row
    table = defaultdict(lambda: defaultdict(Counter))
    cases = []
    for uid, item in items.items():
        group = by_uid[uid]
        if set(group) != set(ARMS):
            raise ValueError("Missing logical pair")
        c = table[item["track"]]
        c["coverage"]["assigned"] += 1
        metrics = {}
        flags = {}
        out = {"case": uid.rsplit("/", 2)[-2:], "track": item["track"]}
        for arm, row in (group | {"IPE-C": {"score": item["base"]["grade"], "score_flags": item["base"]["flags"]}}).items():
            score = row["score"]
            flags[arm] = row["score_flags"]
            if arm != "IPE-C":
                c["coverage"][f"{arm}/triggered"] += bool(row["selected"])
                c["coverage"][f"{arm}/invalid"] += row["selected"] is None
            if (score or {}).get("match"):
                metrics[arm] = dict(score["match"]) | {k: score[k] for k in ("OPB", "UPB", "FM") if type(score.get(k)) is int}
                c["coverage"][f"{arm}/scored"] += 1
            out[arm] = {"score": metrics.get(arm), "flags": flags[arm], "selected_count": len(row.get("selected") or ())}
        if len(metrics) == 3:
            c["coverage"]["common"] += 1
            clean = not any(flags.values())
            c["coverage"]["common_unflagged"] += clean
            for arm, score in metrics.items():
                c[arm].update(score)
                if clean:
                    c["unflagged/" + arm].update(score)
        cases.append(out)
    print(json.dumps({"table": table, "cases": cases, "statuses": Counter(r["status"] for r in ledger),
                      "stages": Counter(r["unit"]["stage"] for r in ledger),
                      "tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
                      "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                      "retries": sum(r["automatic_retries"] for r in ledger)}, indent=2))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    pin, items, jobs = prepare()
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    if action == "freeze":
        probe.freeze(PRIVATE / "FROZEN.json", pin)
        print(json.dumps(Counter(item["track"] for item in items.values())))
    elif pin != read(PRIVATE / "FROZEN.json"):
        raise ValueError("Frozen inputs changed")
    elif action == "run":
        run(pin, items, jobs)
    else:
        report(items)


if __name__ == "__main__":
    main()
