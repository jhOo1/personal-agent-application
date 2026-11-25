"""Run an isolated secondary review of five fixed-answer groups."""
import argparse
from collections import Counter
import json

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from recovery_behavior_packets import RUBRIC, build
from run_recovery_strength import HERE, engine, probe, read, sha

OUT = HERE / "recovery_behavior_v1"
RUN = engine.RUN.with_name("nro_recovery_behavior_v1")
STAGE = "RecoveryBehaviorReview"
FIELDS = ("uses_preference", "shared_override", "requirement_omitted")
VALUES = {"YES", "NO", "UNCERTAIN"}
SYSTEM = RUBRIC + (
    ' Return a JSON object keyed by X, Y, Z. Each value contains "quote" (verbatim '
    'from that answer, or null if insufficient), "uses_preference", "shared_override", '
    'and "requirement_omitted". Each judgment is YES, NO, or UNCERTAIN.'
)


def decode(raw, packet):
    result = json.loads(raw)
    if not isinstance(result, dict) or result.keys() != packet["answers"].keys():
        raise ValueError("Invalid aliases")
    for alias, item in result.items():
        if not isinstance(item, dict) or set(item) != {"quote", *FIELDS}:
            raise ValueError("Invalid verdict object")
        if any(not isinstance(item[key], str) or item[key] not in VALUES for key in FIELDS):
            raise ValueError("Invalid verdict")
        quote = item["quote"]
        if quote is None:
            if any(item[key] == "YES" for key in FIELDS):
                raise ValueError("Positive judgment requires a quote")
        elif not isinstance(quote, str) or not quote.strip() or quote not in packet["answers"][alias]:
            raise ValueError("Quote absent from answer")
    return result


def main(action):
    packets, keys = build()
    jobs = {(packet["case"], "blind"): {
        "model": "gpt-6.1-sol", "temperature": 0, "max_tokens": 4096, "stream": True,
        "stream_options": {"include_usage": True},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}],
    } for packet in packets}
    for wire in jobs.values():
        validate_public_request(wire)
    identity = {"experiment_sha256": sha([list(jobs.values()), keys, sha((HERE / "run_recovery_behavior.py").read_bytes())]),
                "service_reference_sha256": probe.read_reference()[1]}
    if action == "check":
        print(f"{len(jobs)} anonymous review requests")
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, {STAGE: 5}
    OUT.mkdir(exist_ok=True)
    live, ledger = action == "run", []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Execution drift")
        replies = engine.stage(STAGE, jobs, identity, live, ledger)
        rows = []
        for packet in packets:
            alias = packet["case"]
            reply = replies[alias, "blind"]
            verdict, status = None, reply["status"]
            if status == "OK":
                try:
                    verdict = decode(reply["answer"], packet)
                except (ValueError, TypeError):
                    status = "INVALID_REVIEW_CONTRACT"
            rows.append({**keys[alias], "case": alias, "status": status, "verdict": verdict})
        result = {"rows": rows, "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", result)
        elif read(OUT / "RESULTS.json") != result:
            raise ValueError("Replay drift")
        print(Counter(row["status"] for row in rows))



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
