"""Run the newly reconstructed, same-envelope zero-history travel endpoint."""
from argparse import ArgumentParser
import json
from pathlib import Path

from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import sha
from replay import BASE, ROOT, TRAVEL, archive, read, verified
import repair_trial as trial


HERE = Path(__file__).resolve().parent
RUN = ROOT / "runs" / BASE.name / "persist_current_destination_pair"
ACTOR, GRADE = "TravelEmpty", "TravelJudge"
CAP = {ACTOR: 1, GRADE: 1}
METHOD = "REMOVE_ONE_TO_EMPTY"


def archive_service():
    folder = BASE / "native_residual_v1/persist_performance_v1"
    manifest = read(folder / "FinalActor_MANIFEST.json")
    job, = [x for x in manifest["units"] if x["unit"]["root_id"] == TRAVEL
            and x["unit"]["method"] == "SELECTED_GEPA"]
    directory = ROOT / "runs" / BASE.name / folder.name / "FinalActor/visible"
    record = read(directory / sampling_key(job["unit"]) / "record.json")
    if record["request_sha256"] != sha(job["request"]):
        raise ValueError("Original selected Actor service record changed")
    return record["reference_config_sha256"]


def main(action):
    if action == "report" or (action == "run" and (RUN / "SUMMARY.json").is_file()):
        print(json.dumps(read(RUN / "SUMMARY.json"), indent=2))
        return
    observation, actor, envelope = verified()
    original = read(HERE / "SUMMARY.json")["travel"]
    travel = observation["travel"]
    fields = ("actor_request_sha256", "ablated_request_sha256", "selected_rating")
    if any(travel[field] != original[field] for field in fields):
        raise ValueError("Travel request or selected rating changed")
    if action == "freeze" and travel["exact_actor_archive"] is not None:
        raise ValueError("The proposed request already has a transport record")
    pin = {"actor": sha(actor), "scorer_envelope": sha(envelope), "service": archive_service(),
           "cap": CAP, "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PAIR_PROTOCOL.md").read_bytes())}
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.engine.CAP = CAP
    key = TRAVEL, METHOD
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            trial.probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if read(RUN / "FROZEN.json") != pin or pin["service"] != trial.probe.read_reference()[1]:
            raise ValueError("Counterfactual or archived service drift")
        identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service"]}
        trial.probe.freeze(RUN / "EXECUTION.json", identity)
        ledger = []
        response = trial.stage(ACTOR, {key: actor}, identity, ledger)[key]
        trial.probe.freeze(RUN / "ANSWER_PRIVATE.json", response)
        answer = response.get("answer")
        grade, score, score_status = None, None, None
        if response["status"] == "OK" and answer:
            body = envelope["messages"][-1]
            pattern = "<response>\n{{ANSWER}}\n</response>"
            if body["content"].count(pattern) != 1:
                raise ValueError("Ambiguous answer slot in archived grader")
            message = {**body, "content": body["content"].replace(pattern, f"<response>\n{answer}\n</response>")}
            wire = {**envelope, "messages": [*envelope["messages"][:-1], message]}
            grade = trial.stage(GRADE, {key: wire}, identity, ledger)[key]
            trial.probe.freeze(RUN / "GRADE_PRIVATE.json", grade)
            score_status = grade["status"]
            if score_status == "OK":
                evaluator = archive["persist"].author.ext.parent.persist
                try:
                    score = evaluator.score("cross_domain", grade["answer"])
                except (TypeError, KeyError, ValueError):
                    score_status = "INVALID_SCORE"
        summary = {"actor_status": response["status"], "new_answer_sha256": sha(answer) if answer else None,
                   "grade_status": score_status, "grade": score,
                   "archived_selected_rating": observation["travel"]["selected_rating"],
                   "author_control_ratings": observation["travel"]["old_ratings"],
                   "new_requests": len(ledger), "reported_tokens": sum(
                       (row["usage"] or {}).get("total_tokens") or 0 for row in ledger),
                   "unknown_usage": sum((row["usage"] or {}).get("total_tokens") is None for row in ledger),
                   "retries": sum(row.get("automatic_retries", 0) for row in ledger)}
        trial.probe.freeze(RUN / "LEDGER.json", ledger)
        trial.probe.freeze(RUN / "SUMMARY.json", summary)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    main(parser.parse_args().action)
