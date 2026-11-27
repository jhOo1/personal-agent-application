"""Freeze and run the common task-only interface. This stage never reads draft text into a request."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

from delta import decode
from qamc.common import sha
from qamc.contextual_match.development import text_request
import repair_trial as trial
from trial_oar import HERE, roster

RUN = trial.RUN.with_name(HERE.name)
STAGE = "ObligationInterface"
PROMPT = """Prepare a compact task interface in the language of the current request. Only the request
and current context are available. Identify its necessary deliverables and actual open decisions.
For each open decision name up to three distinct functions its text could serve in the final answer,
for example a principal choice or a genuinely necessary dependent instruction. Use only roles
warranted by this task. Never supply an answer, recommended value, example menu, historical fact,
specific value of an unknown field, guessed beneficiary, or invented optional goal. Name existing
constraints with a short literal anchor from the input. Do not assume the recipient has information
which only the requester could know. A legitimate historical constraint may later narrow an open
decision. The caller may keep the draft. Return exactly {"obligations":[{"anchor":"literal task
words","requirement":"brief description"}],"decisions":[{"anchor":"literal task words","decision":
"question left open","roles":["purpose of first output location"]}]}. At most four items per array;
zero open decisions is valid. Do not return IDs or code."""


def parse(raw, task):
    obj = decode(raw)
    if not isinstance(obj, dict) or set(obj) != {"obligations", "decisions"}:
        raise ValueError("Invalid interface envelope")
    sources = [v for v in task.values() if isinstance(v, str)]
    for key, fields in (("obligations", {"anchor", "requirement"}), ("decisions", {"anchor", "decision", "roles"})):
        rows = obj[key]
        if not isinstance(rows, list) or len(rows) > 4:
            raise ValueError("Invalid interface size")
        for item in rows:
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError("Invalid interface item")
            if any(not isinstance(item[k], str) or not item[k].strip() for k in fields - {"roles"}):
                raise ValueError("Invalid interface string")
            if not any(item["anchor"] in src for src in sources):
                raise ValueError("Task anchor not found")
            if key == "decisions":
                roles = item["roles"]
                if not isinstance(roles, list) or not 1 <= len(roles) <= 3 or not all(
                        isinstance(role, str) and role.strip() for role in roles) or len(set(roles)) != len(roles):
                    raise ValueError("Invalid location roles")
    return obj


def main(action):
    cases = roster()
    requests = {(r["uid"], "SHARED"): text_request(PROMPT, r["task"], "qwen3.8-flash", 8192) for r in cases}
    frozen = {"stage": STAGE, "roster": sha(cases), "prompt": sha(PROMPT),
              "code": {s: sha((HERE / s).read_bytes()) for s in ("interface_stage.py", "trial_oar.py", "run.sh")},
              "requests": {uid: sha(wire) for (uid, _), wire in requests.items()}}
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.engine.CAP = {STAGE: len(cases)}
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if action == "freeze-interface":
            trial.probe.freeze(RUN / "INTERFACE_FROZEN.json", frozen)
            print("Frozen task-only request count:", len(requests))
            return
        if trial.read(RUN / "INTERFACE_FROZEN.json") != frozen:
            raise ValueError("Task-only requests changed")
        service = trial.probe.read_reference()[1]
        if service != trial.read(trial.VETO / "EXECUTION.json")["service_reference_sha256"]:
            raise ValueError("Actor service has changed")
        identity = {"experiment_sha256": sha(frozen), "service_reference_sha256": service}
        path = RUN / "INTERFACES_PRIVATE.json"
        if path.exists():
            existing = trial.read(path)
            if existing["identity"] != identity:
                raise ValueError("Previous settlement has a different identity")
            print(existing["summary"])
            return
        ledger = []
        receipts = trial.stage(STAGE, requests, identity, ledger)
        items = {}
        for row in cases:
            uid = row["uid"]
            reply = receipts[uid, "SHARED"]
            status = reply["status"]
            interface = None
            if status == "OK":
                try:
                    interface = parse(reply["answer"], row["task"])
                except (KeyError, TypeError, ValueError):
                    status = "INVALID_INTERFACE"
            items[uid] = {"interface": interface, "status": status, "receipt": reply}
        summary = {"interface_states": dict(Counter(r["status"] for r in items.values())),
                   "physical": len(ledger), "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger)}
        trial.probe.freeze(path, {"identity": identity, "rows": items, "summary": summary, "ledger": ledger})
        print(summary)


if __name__ == "__main__":
    p = ArgumentParser()
    p.add_argument("action", choices=("freeze-interface", "run-interface"))
    main(p.parse_args().action)
