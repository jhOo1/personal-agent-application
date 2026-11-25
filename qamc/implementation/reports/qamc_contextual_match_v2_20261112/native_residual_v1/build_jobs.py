"""Validate frozen inputs and construct matched NRO Actor jobs."""
from collections import Counter
from pathlib import Path
import argparse
import json
import sys

from baselines import archive, rpe, transfer
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from freeze_roster import roster
from residual import actor_wire, policy

HERE = Path(__file__).resolve().parent


def archive_inputs():
    plan = archive.read(archive.v41.formal.OUT / "PLAN.json")
    if any(row["independent_confirmation"] for row in plan["cases"]):
        raise ValueError("Unexpected confirmation cohort")
    cases = archive.v41.author_cases(plan)
    wires = {
        ("RPEval", row["uid"]): row
        for row in archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json")
        if row["uid"] in cases and row["method"] == archive.engine.RP
        and row["actor_status"] == "OK"
    }
    cards = {("RPEval", uid): row for uid, row in rpe().items()}
    for benchmark, method in (("BenchPreS", archive.engine.GATE),
                              ("PersistBench", "PB_RUBRIC")):
        cases, _, _ = archive.transfer.context(benchmark)
        eligible = transfer(benchmark)
        cards.update({(benchmark, uid): row for uid, row in eligible.items()})
        for row in archive.transfer.archived_answers(benchmark, cases):
            if row["method"] != method or row["uid"] not in eligible or row["actor_status"] != "OK":
                continue
            key = benchmark, row["uid"]
            if key in wires:
                raise ValueError(f"Ambiguous Actor archive: {key}")
            wires[key] = row
    return wires, cards


def prepare(rules, split):
    rules = policy(rules)
    wires, cards = archive_inputs()
    jobs, baselines = {}, {}
    group_splits = {}
    frozen = archive.read(HERE / "ROSTER.json")
    if frozen != roster():
        raise ValueError("Frozen roster drift")
    for row in frozen["rows"]:
        key = row["benchmark"], row["uid"]
        group = row["benchmark"], row["group"]
        if group in group_splits:
            raise ValueError(f"Duplicate roster group: {group}")
        group_splits[group] = row["split"]
        if row["split"] != split:
            continue
        card = cards[key]
        digest = sha(card["base_answer"])
        if digest != row["baseline_answer_sha256"] or card["group"] != row["group"]:
            raise ValueError(f"Archived baseline drift: {key}")
        baselines[key] = card
        if not rules or not row["history_enabled"]:
            continue
        wire = wires[key]
        request = actor_wire(wire["actor_request"], wire["actor_request_sha256"], rules,
                             history_enabled=True)
        validate_public_request(request)
        if token_estimate(canonical(request["messages"])) > 32768:
            raise ValueError(f"Capacity exceeded: {key}")
        jobs[key] = request
    if len(baselines) != 20:
        raise ValueError("Frozen split must contain exactly 20 roots")
    return jobs, baselines


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("split", choices=("search", "confirmation"))
    args = cli.parse_args()
    jobs, baselines = prepare(json.load(sys.stdin), args.split)
    print(json.dumps({"archived": len(baselines), "reused": len(baselines) - len(jobs),
                      "candidate_actor_jobs": dict(Counter(k[0] for k in jobs))}, sort_keys=True))
