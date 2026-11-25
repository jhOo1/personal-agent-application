"""Test a grounded open question against shared ordinary preparation."""
import argparse
import json
from pathlib import Path

from persist_criteria_panel import prepare as panel
from persist_premise_contract import comparison_inputs
from persist_option_prepare import messages
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "persist_decoupling_v1"
RUN = engine.RUN.with_name("nro_persist_decoupling_v1")


def prepare():
    rows, wires, cards = panel()
    items = {}
    for row in rows:
        uid = row["uid"]
        key = "PersistBench", uid
        card = cards[key]
        root = card["root"]
        task = root["public_task"]
        sources = [
            {"id": source["memory_id"], "text": source["text"]}
            for source in root["original_sources"]
        ]
        original = wires[key]["actor_request"]
        sources = {source["id"]: source["text"] for source in sources}
        request = {**original, "messages": messages(
            "Prepare to solve the current task using the complete evidence. Return JSON with "
            "reasoning_note (a useful concrete preparation for the requested deliverable), "
            "and premise_probe (null or an object with source_id, exact quote and open_question). "
            "Select a probe only if an unsupported inference would materially change an actual choice, "
            "requirement or factual assertion. Phrase it as a question without assuming its answer. "
            "Use source_id query for a quotation from the current query. Do not rewrite the user's goal.",
            {"task": task, "memory": sources},
        )}
        validate_public_request(request)
        items[uid] = card, task, sources, original, request
    return items


def run(live):
    items = prepare()
    n = len(items)
    caps = {"PremisePlan": n, "PremiseAnswer": 2*n, "PersistNative": 2*n}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([
            [(uid, sha(item[-1]), sha(item[3])) for uid, item in items.items()], caps,
            [sha((HERE / name).read_bytes()) for name in (
                "run_persist_decoupling.py", "persist_option_prepare.py", "persist_premise_contract.py",
            )],
        ]),
    }
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, live, ledger, cache) if jobs else {}

        plans = dispatch("PremisePlan", {(uid, "shared"): item[-1] for uid, item in items.items()})
        contracts, jobs, proposed = {}, {}, {}
        for (uid, _), reply in plans.items():
            if reply["status"] != "OK":
                contracts[uid] = reply["status"]
                continue
            _, task, sources, original, _ = items[uid]
            try:
                prepared = json.loads(reply["answer"])
                if not isinstance(prepared["reasoning_note"], str):
                    raise ValueError("Expected a preparation note")
                control, treatment = comparison_inputs(task, sources, prepared)
            except (ValueError, KeyError, TypeError, AttributeError):
                contracts[uid] = "INVALID_PLAN"
                continue
            proposed[uid] = treatment.get("open_premise")
            instruction = (
                "Complete the original task and preserve its explicit requirements. "
                "Use the preparation as provisional analysis. If an open premise question is "
                "provided, resolve it against the evidence or make the dependent decision conditional. "
                "Return only the complete deliverable."
            )
            for method, data in (("direct", control), ("locked", treatment)):
                request = {**original, "messages": messages(instruction, data)}
                validate_public_request(request)
                jobs[uid, method] = request

        replies = dispatch("PremiseAnswer", jobs)
        rows = []
        for uid, (card, _, _, _, _) in items.items():
            for method in ("direct", "locked"):
                reply = replies.get((uid, method))
                status = reply["status"] if reply else contracts[uid]
                answer = reply["answer"] if status == "OK" else None
                fallback = False
                rows.append({
                    "uid": uid, "method": method, "benchmark": "PersistBench",
                    "group": card["group"], "stratum": card["stratum"],
                    "answer": card["base_answer"] if fallback else answer,
                    "actor_status": "OK" if fallback else status,
                    "fallback": fallback, "base_score": card["base_score"],
                    "sources": card["root"]["original_sources"],
                    "score": card["base_score"] if fallback or answer == card["base_answer"] else None,
                })
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger, "options": proposed})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    args = parser.parse_args()
    if args.action == "check":
        print(f"Validated {len(prepare())} archived preparation requests")
    else:
        run(True)
