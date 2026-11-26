"""Run the same masked checklist under a separate reviewer model and journal."""
import argparse
import json
from runpy import run_path
from pathlib import Path

from qamc.common import sha

HERE = Path(__file__).resolve().parent
REVIEWER = "gpt-4.1"


def run(action):
    base = run_path(str(HERE / "review.py"))
    pin, jobs, mapping, packet = base["prepare"]()
    read, probe, engine = (base[key] for key in ("read", "probe", "engine"))
    original = base["RUN"]
    if (pin != read(original / "FROZEN.json")
            or mapping != read(original / "PRIVATE_MAPPING.json")
            or packet != read(original / "PRIVATE_PACKET.json")):
        raise ValueError("Underlying review freeze changed")
    root = original.with_name(original.name + "_gpt41")
    jobs = {key: dict(wire, model=REVIEWER) for key, wire in jobs.items()}
    freeze = {**pin, "prior_freeze_sha256": sha(pin), "reviewer": REVIEWER,
              "request_sha256": sha(sorted((u, sha(w)) for (u, _), w in jobs.items())),
              "second_reviewer_code_sha256": sha(Path(__file__).read_bytes())}
    if action == "freeze":
        probe.freeze(root / "FROZEN.json", freeze)
        probe.freeze(root / "PRIVATE_MAPPING.json", mapping)
    elif action == "run":
        if read(root / "FROZEN.json") != freeze:
            raise ValueError("Second reviewer freeze changed")
        engine.OUT = probe.OUT = probe.RUN = root
        stage = base["STAGE"]
        engine.CAP = {stage: pin["cap"]}
        identity = {"experiment_sha256": sha(freeze),
                    "service_reference_sha256": probe.read_reference()[1]}
        ledger = []
        with probe.runner_lock(root / "runner.lock"):
            probe.freeze(root / "EXECUTION.json", identity)
            responses = engine.stage(stage, jobs, identity, True, ledger)
            reviews = {}
            for (identifier, _), response in responses.items():
                status, checks = response["status"], None
                if status == "OK":
                    try:
                        checks = base["validate"](response["answer"], packet[identifier]["answer"])
                    except (ValueError, TypeError, KeyError):
                        status = "INVALID_REVIEW"
                reviews[identifier] = {"status": status, "checks": checks, "receipt": response}
            probe.freeze(root / "RESULTS.json", {"reviews": reviews, "ledger": ledger})
    print(json.dumps({"reviewer": REVIEWER, "cap": len(jobs), "freeze_sha256": sha(freeze)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run"))
    run(parser.parse_args().action)
