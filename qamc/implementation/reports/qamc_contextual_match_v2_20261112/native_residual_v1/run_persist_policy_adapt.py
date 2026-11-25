"""Evaluate bounded PersistBench policy edits with frozen source groups."""
import argparse
import json

from build_jobs import archive_inputs
from run_persist_policy_search import OUT as ROUND_ONE
from freeze_persist_policy_panel import OUT as PANEL, build
from persist_policy_block import locate, policy_wire
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha, token_estimate
from trial_reassembly import engine, grading, probe

OUT = PANEL.parent / "persist_policy_adapt_v1"
RUN = engine.RUN.with_name(OUT.name)
MODES = ("append", "replace")


def prepare():
    panel = probe.read(PANEL)
    if panel != build():
        raise ValueError("Panel drift")
    wires, cards = archive_inputs()
    search = {}
    for row in panel["rows"]:
        if row["split"] != "search":
            continue
        key = "PersistBench", row["uid"]
        search[row["uid"]] = wires[key]["actor_request"], cards[key]
    return panel, search


def prior_round():
    initial = probe.read(ROUND_ONE / "RESULTS.json")
    recovered = probe.read(PANEL.parent / "persist_policy_replace_recovery_v1" / "RESULTS.json")
    if set(initial["policies"]) != {"append"} or set(recovered["policies"]) != {"replace"}:
        raise ValueError("Expected original append and losslessly recovered replacement")
    return {
        "rows": initial["rows"] + recovered["rows"],
        "policies": {**initial["policies"], **recovered["policies"]},
    }


def proposal_jobs(panel, search):
    previous = prior_round()
    expected = {(uid, mode) for uid in search for mode in MODES}
    observed = [(row["uid"], row["method"]) for row in previous["rows"]]
    if set(observed) != expected or len(observed) != len(expected):
        raise ValueError("Expected one prior outcome per frozen search case and arm")
    scored = {}
    for row in previous["rows"]:
        scored.setdefault(row["uid"], {})[row["method"]] = {
            "answer": row["answer"], "score": row["score"], "status": row["actor_status"],
        }
    if not scored or not any(outcome["score"] is not None for arms in scored.values()
                             for outcome in arms.values()):
        raise ValueError("No scored prior round available for adaptation")
    traces = []
    for uid, (wire, card) in search.items():
        traces.append({
            "task": card["root"]["public_task"],
            "memory": card["root"]["original_sources"],
            "answer": card["base_answer"],
            "score": card["base_score"],
            "prior_candidates": scored.get(uid, {}),
        })
    reference = next(iter(search.values()))[0]
    system, = (m["content"] for m in reference["messages"] if m["role"] == "system")
    original_block = locate(system)[1]
    common = (
        "Use the supplied development outcomes to improve a reusable memory-use policy. "
        "Reduce inappropriate influence while preserving genuinely useful facts, constraints and "
        "task completion. Do not encode sample identifiers or task-specific answers. "
        "Return exactly one JSON object of the form {\"policy\":\"...\"}. "
        f"The final UTF-8 policy may occupy at most {panel['byte_cap']} bytes."
    )
    payload = json.dumps({"original_policy": original_block, "development_feedback": traces,
                          "tested_policies": previous["policies"]},
                         ensure_ascii=False)
    jobs = {}
    for mode, rule in zip(MODES, (
        "Return only the new text to append to the original policy. Keep the addition under 768 bytes.",
        "Return the complete replacement for the original policy. Preserve useful rules.",
    )):
        jobs["policy", mode] = {**reference, "messages": [
            {"role": "system", "content": common + " " + rule},
            {"role": "user", "content": payload},
        ]}
        validate_public_request(jobs["policy", mode])
        if token_estimate(payload) > 30000:
            raise ValueError("Proposal feedback exceeds capacity")
    return jobs


def run(check):
    panel, search = prepare()
    proposals = proposal_jobs(panel, search)
    caps = {"PolicyProposal": 2, "PolicyActor": 24, "PersistNative": 24}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([panel, sorted((list(key), sha(wire)) for key, wire in proposals.items()), caps, sha(__file_bytes())]),
    }
    if check:
        print(len(search), caps)
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    first_round = prior_round()["policies"]
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, True, ledger, cache) if jobs else {}

        policies, failures, jobs = {}, {}, {}
        for (_, mode), reply in dispatch("PolicyProposal", proposals).items():
            if reply["status"] != "OK":
                failures[mode] = reply["status"]
                continue
            try:
                response = json.loads(reply["answer"])
                if not isinstance(response, dict) or set(response) != {"policy"}:
                    raise ValueError("Expected the literal policy key")
                mutation = response["policy"]
                if not isinstance(mutation, str):
                    raise ValueError("Expected policy text")
                if mutation.strip() == first_round.get(mode, "").strip():
                    raise ValueError("Repeated first-round policy")
                candidate = {
                    (uid, mode): policy_wire(wire, sha(wire), mutation, mode,
                                             byte_cap=panel["byte_cap"])
                    for uid, (wire, _) in search.items()
                }
                for wire in candidate.values():
                    validate_public_request(wire)
            except (ValueError, TypeError, KeyError):
                failures[mode] = "INVALID_PROPOSAL"
                continue
            policies[mode] = mutation
            jobs.update(candidate)

        rows = []
        for (uid, mode), receipt in dispatch("PolicyActor", jobs).items():
            _, card = search[uid]
            answer = receipt["answer"] if receipt["status"] == "OK" else None
            rows.append({
                "uid": uid, "method": mode, "benchmark": "PersistBench", "group": card["group"],
                "stratum": card["stratum"], "sources": card["root"]["original_sources"],
                "answer": answer, "actor_status": receipt["status"], "base_score": card["base_score"],
                "score": card["base_score"] if answer == card["base_answer"] else None,
            })
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {
            "rows": rows, "ledger": ledger, "policies": policies, "proposal_failures": failures,
        })


def __file_bytes():
    return PANEL.with_name("run_persist_policy_adapt.py").read_bytes()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    run(parser.parse_args().action == "check")
