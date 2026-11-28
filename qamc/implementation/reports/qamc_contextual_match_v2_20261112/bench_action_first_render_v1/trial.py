"""Measure the effect of ordering the recipient action before unchanged context."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
parent = run_path(str(BASE / "bench_relation_compiler_v1" / "relation_trial.py"))
previous = run_path(str(BASE / "strong_wire_pruning_replay_v1" / "run.py"))
archive, engine, probe, sha = (previous[k] for k in ("archive", "engine", "probe", "sha"))
run, digest, archived_fields, summarize, parse_object = (parent[k] for k in
    ("run", "digest", "archived_fields", "summarize", "parse_object"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
LABELS = ("tax_discrepancy", "debt_consolidation", "annual_physical", "rental_history", "protection_1")
PRODUCERS = ("DIRECT", "STRUCTURED")
OUTPUTS = ("DIRECT", "CONTEXT_FIRST", "ACTION_FIRST")
PROMPTS = {
    "DIRECT": """Deliver the complete final message using plain, concise and objective language when appropriate. Make the recipient's action clear. Preserve all requested deliverables and supported facts, retain applicable presentation requirements, and ask for verification rather than claiming unavailable facts. Return only the recipient-facing message.""",
    "STRUCTURED": """Deliver a final message in plain, concise, objective language when appropriate. Preserve all requested deliverables and supported facts, retain applicable presentation requirements, and ask for verification rather than claiming unavailable facts. Write one complete message in this JSON shape: {"header":"existing greeting/subject required by the task or empty","actions":"exact complete recipient-facing requests and questions","context":"exact complete recipient-facing facts and background","closing":"recipient-facing closing or empty"}. Do not use Markdown fences. Fields are literal text and must read coherently whichever body block comes first. Make the action meaningful without relying on a prior sentence. Context is not a recap of the actions. Retain all material facts and any required formatting inside the fields. No field labels will appear in the rendered answer.""",
}
ACTOR = "BenchActionOrderActor"


def render(text):
    parts = parse_object(text)
    if (not isinstance(parts, dict) or set(parts) != {"header", "actions", "context", "closing"}
            or any(not isinstance(p, str) or "\x00" in p for p in parts.values())
            or not parts["actions"].strip()):
        raise ValueError("Malformed complete message")
    common = ("header", "closing")
    if any(parts[k].count("\n") > 3 for k in common):
        raise ValueError("Unexpected header or closing")
    a, b = ("header", "actions", "context", "closing"), ("header", "context", "actions", "closing")

    def join(keys):
        return "\n\n".join(parts[k].strip() for k in keys if parts[k].strip())

    return {"ACTION_FIRST": join(a), "CONTEXT_FIRST": join(b)}


def prepare():
    all_cards, _, grader, _ = parent["prepare"]()
    cards = {label: all_cards[label] for label in LABELS}
    jobs = {}
    for label, card in cards.items():
        for arm, policy in PROMPTS.items():
            wire = deepcopy(card["original"])
            if wire["messages"][0]["role"] != "system":
                raise ValueError("Expected original system message")
            wire["messages"][0]["content"] += "\n\n" + policy
            jobs[label, arm] = wire
    pin = {"cases": list(cards), "input": {"/".join(k): sha(v) for k, v in jobs.items()},
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "reference": probe.read_reference()[1], "actor_cap": len(jobs), "scorer_cap": len(cards) * len(OUTPUTS) * 6}
    return cards, grader, jobs, pin


def execute(cards, grader, jobs, pin, live):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {ACTOR: pin["actor_cap"]}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["reference"]}
    ledger, reused = [], {}

    def stage(name, wires):
        by_digest = {}
        for key, wire in sorted(wires.items()):
            by_digest.setdefault(sha(wire), key)
        unique = {key: wires[key] for key in by_digest.values()}
        if not unique:
            return {}
        target = PRIVATE / f"{name}_archive.json"
        if live and not target.exists():
            found, _ = previous["support"]["prior"]["find_archived"](unique, BASE.parents[1])
            rows = []
            for (case, arm), item in found.items():
                meta = (BASE.parents[1] / item["archive"]).parent / "visible" / item["archive_unit"] / "record.json"
                ref = archive.read(meta).get("reference_config_sha256") if meta.is_file() else None
                if item["status"] == "OK" and ref != pin["reference"]:
                    item = dict(item, status="ARCHIVED_PROTOCOL_UNVERIFIED", answer=None)
                rows.append([case, arm, item])
            probe.freeze(target, rows)
        known = {(case, arm): item for case, arm, item in archive.read(target)}
        if any(item["request_sha256"] != sha(unique[key]) for key, item in known.items()):
            raise ValueError("Archived receipt drift")
        pending = {key: wire for key, wire in unique.items() if key not in known}
        used = known | (engine.stage(name, pending, identity, live, ledger) if pending else {})
        reused[name] = dict(Counter(x["status"] for x in known.values()))
        return {key: used[by_digest[sha(wire)]] for key, wire in wires.items()}

    with probe.runner_lock(RUN / "runner.lock"):
        actors = stage(ACTOR, jobs)
        finals, failures = {}, {}
        for (label, method), record in actors.items():
            if record["status"] != "OK":
                failures[label + "/" + method] = record["status"]
            elif method == "DIRECT":
                finals[label, "DIRECT"] = record["answer"]
            else:
                try:
                    finals.update({(label, arm): text for arm, text in render(record["answer"]).items()})
                except (KeyError, TypeError, AttributeError, ValueError):
                    failures[label + "/" + method] = "INVALID_MESSAGE"
        requests, references = defaultdict(dict), {}
        for label, card in cards.items():
            case = card["case"]
            ref = references[label] = run.read(run.ROOT / case["evaluation_path"])
            if digest(ref) != case["evaluation_hash"]:
                raise ValueError("Archived evaluation hash mismatch")
            for arm in OUTPUTS:
                if (label, arm) not in finals:
                    continue
                for field, system, content in run.prior.score.initial_requests(
                    run.ROOT, "benchpres", ref, card["packet"]["query"], finals[label, arm]
                ):
                    wire = run.prior.text_request(system, content, grader["model"], grader["stages"][field]["max_tokens"])
                    name = "BenchGrade" + str(wire["max_tokens"])
                    requests[name][label, arm + ":" + field] = wire
        if sum(map(len, requests.values())) > pin["scorer_cap"]:
            raise ValueError("Scoring budget exceeded")
        receipts = {}
        for name, group in sorted(requests.items()):
            engine.CAP[name] = len(group)
            receipts.update(stage(name, group))
        metrics = {}
        for label, card in cards.items():
            scores = metrics.setdefault(label, {})
            for arm in ("base", "external"):
                row = card[arm]
                scores[arm] = summarize(row["attributes"], row["old_completeness"]) if row["old_strict_score"] else None
            for arm in OUTPUTS:
                scores[arm] = None
                if (label, arm) in finals:
                    fields = {tag.split(":")[1]: receipt["answer"] for (case, tag), receipt in receipts.items()
                              if case == label and tag.split(":")[0] == arm and receipt["status"] == "OK"}
                    attrs, complete = archived_fields({"raw_scores": fields, "actor_status": "OK"}, references[label])
                    scores[arm] = summarize(attrs, complete)
        result = {"metrics": metrics, "failures": failures, "ledger": ledger, "archive_reuse": reused,
                  "grade_status": Counter(r["status"] for r in receipts.values()),
                  "answers": [[label, arm, text] for (label, arm), text in finals.items()]}
        location = PRIVATE / "RESULTS.json"
        if live:
            probe.freeze(location, result)
        elif archive.read(location) != result:
            raise ValueError("Settlement replay mismatch")
        print({"physical": len(ledger), "statuses": Counter(r["status"] for r in ledger), "failures": failures})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "check", "run", "replay"))
    action = cli.parse_args().action
    data = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    frozen = PRIVATE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(frozen, data[3])
    elif archive.read(frozen) != data[3]:
        raise ValueError("Frozen comparison drift")
    if action in ("run", "replay"):
        execute(*data, live=action == "run")
    else:
        print(LABELS, data[3]["actor_cap"], data[3]["scorer_cap"])
