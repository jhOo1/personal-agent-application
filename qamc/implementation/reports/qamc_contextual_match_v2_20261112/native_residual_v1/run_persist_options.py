"""Run a shared task-only option proposal and two matched Actor arms."""
import argparse
import json
from pathlib import Path

from persist_criteria_panel import prepare as panel
from persist_option_contract import compile_options
from persist_option_prepare import final_messages, prepare_messages
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "persist_options_v1"
RUN = engine.RUN.with_name("nro_persist_options_v1")


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
        request = {**original, "messages": prepare_messages(task, sources, [])}
        validate_public_request(request)
        items[uid] = card, task, sources, original, request
    return items


def read_options(answer):
    rows = json.loads(answer)["options"]
    if not isinstance(rows, list) or len(rows) > 4:
        raise ValueError("Invalid option count")
    for row in rows:
        if (not isinstance(row["id"], str) or not row["id"].strip()
                or not isinstance(row["description"], str) or not row["description"].strip()
                or type(row["conditional"]) is not bool):
            raise ValueError("Malformed option")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate option")
    return rows


def run(live):
    items = prepare()
    n = len(items)
    caps = {"OptionPlan": n, "OptionActor": 2*n, "PersistNative": 2*n}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([
            [(uid, sha(item[-1]), sha(item[3])) for uid, item in items.items()], caps,
            [sha((HERE / name).read_bytes()) for name in (
                "run_persist_options.py", "persist_option_prepare.py", "persist_option_contract.py",
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

        plans = dispatch("OptionPlan", {(uid, "shared"): item[-1] for uid, item in items.items()})
        contracts, jobs, proposed = {}, {}, {}
        for (uid, _), reply in plans.items():
            if reply["status"] != "OK":
                contracts[uid] = reply["status"]
                continue
            try:
                options = read_options(reply["answer"])
            except (ValueError, KeyError, TypeError):
                contracts[uid] = "INVALID_PLAN"
                continue
            if not options:
                contracts[uid] = "OUT_OF_SCOPE"
                continue
            proposed[uid] = options
            _, task, sources, original, _ = items[uid]
            for method in ("direct", "locked"):
                request = {**original, "messages": final_messages(
                    task, sources, [], options, locked=method == "locked",
                )}
                validate_public_request(request)
                jobs[uid, method] = request

        replies = dispatch("OptionActor", jobs)
        rows = []
        for uid, (card, _, _, _, _) in items.items():
            for method in ("direct", "locked"):
                reply = replies.get((uid, method))
                status = reply["status"] if reply else contracts[uid]
                answer = reply["answer"] if status == "OK" else None
                if status == "OK" and method == "locked":
                    try:
                        body = json.loads(answer)
                        if not isinstance(body["lead"], str):
                            raise ValueError("Expected lead")
                        visible = compile_options(proposed[uid], body["decisions"], {})
                        answer = "\n\n".join([body["lead"], *(
                            f'{option["role"].capitalize()}: {option["description"]}'
                            for option in visible
                        )]).strip()
                    except (ValueError, KeyError, TypeError):
                        status, answer = "INVALID_ACTOR", None
                fallback = status == "OUT_OF_SCOPE"
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
