"""Compare draft-independent and draft-aware acceptance tests."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
old = run_path(str(BASE / "protected_clause_exposure_v1/trial.py"))
archive, engine, probe, sha, read = (old[key] for key in ("archive", "engine", "probe", "sha", "read"))
RUN = old["RUN"].with_name(HERE.name)
PRIVATE = RUN / "private"
ARMS = ("ORDINARY", "DRAFT_BLIND")
ROOTS = (
    "implicit/094", "explicit/076", "explicit/116", "46dca8c0", "43a1728d",
    "3776469a", "dbcf603f", "0613beea", "a47fceb8",
)
CONTRACT = """Use the current task, current facts and original historical evidence. If a draft
is supplied, review it critically. Write up to three acceptance tests that could change a concrete
action or wording in the requested deliverable. Prioritize governing hard requirements and one
useful condition or boundary when evidenced. Do not infer that a history item applies just because
it is topical. Consider whether the evidence concerns the person actually affected. For supported
conditions, describe what the final answer would have to do; for inapplicable history, specify an
actual misapplication to avoid. Genuine hard constraints need to govern the main action, not appear
only in a disclaimer. Do not invent an available option, a recipient's preference or a task fact.
Return only {"tests":[{"task_quote":"exact substring of task.query","source_id":"memory_id",
"source_quote":"exact substring of that source's text","criterion":"specific check of the final
deliverable"}]}. Use {"tests":[]} if there is no reliable actionable signal. No answer draft."""

ACTOR = """Produce the final deliverable in the original task's requested language and format.
Start with the supplied draft. Consult the current task, facts, original evidence and acceptance tests.
A test is a proposal, so reject unsupported requirements and preserve useful correct original content.
Revise actual actions or wording when needed to pass an applicable test. A necessary prerequisite
that is unknown must affect whether the main action can be adopted. Do not turn a private preference
into a shared default or make a necessary restriction optional. If the draft already meets the task
and supported tests, preserve it. Provide only the final answer without review notes."""


def parse_plan(answer, packet):
    plan = old["parse_object"](answer)
    if not isinstance(plan, dict) or set(plan) != {"tests"} or not isinstance(plan["tests"], list):
        raise ValueError("Invalid tests")
    tests = plan["tests"]
    if len(tests) > 3:
        raise ValueError("Too many tests")
    sources = {row["memory_id"]: row["text"] for row in packet["source_evidence"]}
    fields = {"task_quote", "source_id", "source_quote", "criterion"}
    for test in tests:
        if (not isinstance(test, dict) or set(test) != fields
                or any(not isinstance(value, str) or not 1 <= len(value.strip()) <= 500
                       for value in test.values())
                or test["task_quote"] not in packet["task"]["query"]
                or test["source_id"] not in sources
                or test["source_quote"] not in sources[test["source_id"]]):
            raise ValueError("Unanchored acceptance test")
    return plan


def body(prompt, packet):
    wire = archive.body(prompt, packet, 8192)
    old["validate_public_request"](wire)
    return wire


def prepare():
    saved = read(BASE / "transactional_reassembly_v1/FROZEN.json")
    if not saved["exposed_development_only"]:
        raise ValueError("Expected exposed-only input")
    cards = {}
    for key in ROOTS:
        row, = [r for r in saved["rows"] if key in r["uid"]]
        if sha(row["base_answer"]) != row["baseline_answer_sha256"]:
            raise ValueError("Archived draft digest mismatch")
        cards[row["uid"]] = row
    if len(cards) != len(ROOTS) or len({row["group"] for row in cards.values()}) != len(ROOTS):
        raise ValueError("Duplicate source group")
    packets = {
        uid: {key: row["packet"][key] for key in ("task", "source_evidence")} | {"draft": row["base_answer"]}
        for uid, row in cards.items()
    }
    jobs = {}
    for uid, packet in packets.items():
        draft_blind = {key: packet[key] for key in ("task", "source_evidence")}
        jobs[uid, "ORDINARY"] = body(CONTRACT, packet)
        jobs[uid, "DRAFT_BLIND"] = body(CONTRACT, draft_blind)
    pin = {"archive": sha(saved), "code": sha(Path(__file__).read_bytes()),
           "protocol": sha((HERE / "PROTOCOL.md").read_bytes()), "service": probe.read_reference()[1],
           "requests": [[uid, arm, sha(wire)] for (uid, arm), wire in jobs.items()]}
    return cards, packets, jobs, pin


def run(cards, packets, jobs, pin):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {"ExecutionReview": 18, "ExecutionActor": 18, engine.RPE: 6,
                  "BenchAttrs": 28, "PersistNative": 8}
    ledger, plans, rows, final_jobs = [], {}, [], {}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
    with probe.runner_lock(RUN / "runner.lock"):
        if (PRIVATE / "SETTLED.json").exists():
            raise ValueError("Experiment already settled")
        def stage(name, requests, cache=None):
            return engine.stage(name, requests, identity, True, ledger, cache) if requests else {}
        for (uid, arm), receipt in stage("ExecutionReview", jobs).items():
            row = {key: cards[uid][key] for key in ("uid", "benchmark", "group", "stratum")}
            row.update(method=arm, actor_status=receipt["status"], disposition="REVIEW_MISSING",
                       sources=packets[uid]["source_evidence"], answer=None, score=None, score_flags=None)
            if receipt["status"] == "OK":
                try:
                    plan = parse_plan(receipt["answer"], packets[uid])
                except (ValueError, TypeError):
                    row["disposition"] = "INVALID_REVIEW"
                else:
                    plans[uid, arm] = plan
                    final_jobs[uid, arm] = body(ACTOR, packets[uid] | {"acceptance_tests": plan["tests"]})
                    row["disposition"] = "ANCHORED_TESTS" if plan["tests"] else "EMPTY_TESTS"
            rows.append(row)
        final = stage("ExecutionActor", final_jobs)
        for row in rows:
            key = row["uid"], row["method"]
            if key not in final:
                continue
            rec = final[key]
            row["actor_status"] = rec["status"]
            row["answer"] = rec.get("answer")
            if row["answer"]:
                row["answer_sha256"] = sha(row["answer"])
                source = cards[row["uid"]]
                if row["answer_sha256"] == source["baseline_answer_sha256"]:
                    row.update(score=source["base_score"], score_flags=source["base_flags"])
        old["grading"](rows, stage)
        probe.freeze(PRIVATE / "SETTLED.json", {"rows": rows, "ledger": ledger,
                     "plans": [[uid, arm, plan] for (uid, arm), plan in plans.items()]})


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "run"))
    action = cli.parse_args().action
    cards, packets, jobs, pin = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if action == "freeze":
        probe.freeze(PRIVATE / "FREEZE.json", pin)
        print(json.dumps(dict(roots=Counter(row["benchmark"] for row in cards.values()), reviews=len(jobs))))
    elif read(PRIVATE / "FREEZE.json") == pin:
        run(cards, packets, jobs, pin)
    else:
        raise ValueError("Frozen experiment inputs differ")


if __name__ == "__main__":
    main()
