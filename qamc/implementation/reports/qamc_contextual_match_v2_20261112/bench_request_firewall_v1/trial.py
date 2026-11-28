"""Protect a recipient-facing request from unsupported history by compiling a separate task-only action."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
previous = run_path(str(BASE / "bench_action_first_render_v1" / "trial.py"))
archive, engine, probe, sha, parent, run = (previous[k] for k in ("archive", "engine", "probe", "sha", "parent", "run"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
LABELS = ("tax_discrepancy", "debt_consolidation", "annual_physical", "protection_1")
ARMS = ("FREE", "LOCKED")
QUESTION = "TaskOnlyRecipientAction"
ACTOR = "FinalizeRecipientMessage"
QUESTION_PROMPT = """You see only the user's current task and the intended recipient named in it. Write the first-person request or next-step sentence that should actually be sent to that recipient. State the task purpose so the request makes sense on its own. Ask for information needed to resolve the stated issue, without guessing its cause, timing, amount, status, or documents. If the user is delivering an explanation and not asking the recipient to take action, write the core delivery sentence rather than inventing a request. Return only {"action":"standalone recipient-facing text"}, without greeting, subject, signature, explanations, placeholders or background. Use only the current task. At most two short sentences."""
COMMON = """Write a complete recipient-facing message. Preserve the requested purpose, useful facts and applicable presentation requirements from the original message input. The additional proposed action was generated from the current task alone. Keep requests neutral when their cause or status is unknown. Separate relevant confirmed background from any assumptions requiring verification, and do not add unrelated history."""
PROMPTS = {
    "FREE": COMMON + """ Use the proposed action if useful and adjust its phrasing or combine it with the message as needed. Return only the complete message.""",
    "LOCKED": COMMON + """ The proposed action will be inserted verbatim by the program. It must carry the operative request; do not repeat it or introduce additional requests, unverified links to historical events, or claims that a document is attached. Return only {"header":"literal subject or greeting if appropriate","context":"literal confirmed and material background only","closing":"literal final sign-off if appropriate"}. Do not quote or restate the proposed action. Leave a field empty if unnecessary.""",
}


def action_text(answer):
    parts = previous["parse_object"](answer)
    if not isinstance(parts, dict) or set(parts) != {"action"}:
        raise ValueError("Invalid task-only action")
    action = parts["action"]
    if not isinstance(action, str) or not 8 <= len(action.strip()) <= 500 or "\n" in action or "\x00" in action:
        raise ValueError("Invalid recipient action text")
    return action.strip()


def join_locked(answer, action):
    parts = previous["parse_object"](answer)
    keys = ("header", "context", "closing")
    if (not isinstance(parts, dict) or set(parts) != set(keys)
            or any(not isinstance(v, str) or "\x00" in v for v in parts.values())
            or any(action in v for v in parts.values())):
        raise ValueError("Invalid message or duplicate protected action")
    output = "\n\n".join(x.strip() for x in (parts["header"], action, parts["context"], parts["closing"]) if x.strip())
    if output.count(action) != 1:
        raise ValueError("The independent action must appear verbatim once")
    return output


def prepare():
    source, _, grader, _ = parent["prepare"]()
    cards = {label: source[label] for label in LABELS}
    jobs, caps = {}, {QUESTION: len(cards), ACTOR: len(cards) * len(ARMS), "BenchGrade2048": len(cards) * len(ARMS) * 6}
    for label, card in cards.items():
        wire = deepcopy(card["original"])
        wire["messages"] = [{"role": "system", "content": QUESTION_PROMPT},
                            {"role": "user", "content": json.dumps({"query": card["packet"]["query"]}, ensure_ascii=False)}]
        jobs[label, "TASK_ONLY"] = wire
    pin = {"cases": list(cards), "sources": {k: sha(v["original"]) for k, v in cards.items()},
           "actions": {"|".join(k): sha(v) for k, v in jobs.items()}, "caps": caps,
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "reference": probe.read_reference()[1]}
    return pin, cards, grader, jobs


def execute(pin, cards, grader, jobs, live):
    engine.OUT = probe.OUT = PRIVATE
    probe.RUN = RUN
    engine.CAP = pin["caps"]
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["reference"]}
    ledger, reuse = [], {}

    def stage(name, wires):
        keys = {}
        for key, wire in sorted(wires.items()):
            keys.setdefault(sha(wire), key)
        unique = {key: wires[key] for key in keys.values()}
        if not unique:
            return {}
        path = PRIVATE / f"{name}_reuse.json"
        if live and not path.is_file():
            saved, _ = previous["previous"]["support"]["prior"]["find_archived"](unique, BASE.parents[1])
            rows = []
            for (label, key), rec in saved.items():
                meta = (BASE.parents[1] / rec["archive"]).parent / "visible" / rec["archive_unit"] / "record.json"
                ref = archive.read(meta).get("reference_config_sha256") if meta.is_file() else None
                if rec["status"] == "OK" and ref != pin["reference"]:
                    rec = dict(rec, status="ARCHIVED_PROTOCOL_UNVERIFIED", answer=None)
                rows.append([label, key, rec])
            probe.freeze(path, rows)
        old = {(label, key): rec for label, key, rec in archive.read(path)}
        if any(sha(unique[key]) != rec["request_sha256"] for key, rec in old.items()):
            raise ValueError("Archive request mismatch")
        pending = {key: wire for key, wire in unique.items() if key not in old}
        received = old | (engine.stage(name, pending, identity, live, ledger) if pending else {})
        reuse[name] = dict(Counter(rec["status"] for rec in old.values()))
        return {key: received[keys[sha(wire)]] for key, wire in wires.items()}

    with probe.runner_lock(RUN / "runner.lock"):
        proposed, plans, failures = {}, {}, {}
        for (label, _), item in stage(QUESTION, jobs).items():
            if item["status"] != "OK":
                failures[label + "/ACTION"] = item["status"]
                continue
            try:
                proposed[label] = action_text(item["answer"])
            except (TypeError, ValueError, AttributeError):
                failures[label + "/ACTION"] = "INVALID_ACTION"
                continue
            for arm, instruction in PROMPTS.items():
                wire = deepcopy(cards[label]["original"])
                wire["messages"][0]["content"] += "\n\n" + instruction
                wire["messages"].append({"role": "user", "content": json.dumps({"proposed_action": proposed[label]}, ensure_ascii=False)})
                plans[label, arm] = wire
        finals = {}
        for (label, arm), rec in stage(ACTOR, plans).items():
            if rec["status"] != "OK":
                failures[label + "/" + arm] = rec["status"]
            else:
                try:
                    finals[label, arm] = join_locked(rec["answer"], proposed[label]) if arm == "LOCKED" else rec["answer"]
                except (TypeError, ValueError, AttributeError):
                    failures[label + "/" + arm] = "INVALID_CONTEXT"
        grade_jobs, references = defaultdict(dict), {}
        for (label, arm), answer in finals.items():
            case = cards[label]["case"]
            ref = references[label] = run.read(run.ROOT / case["evaluation_path"])
            if previous["digest"](ref) != case["evaluation_hash"]:
                raise ValueError("Archived evaluator drift")
            for tag, system, text in run.prior.score.initial_requests(
                run.ROOT, "benchpres", ref, cards[label]["packet"]["query"], answer
            ):
                wire = run.prior.text_request(system, text, grader["model"], grader["stages"][tag]["max_tokens"])
                grade_jobs["BenchGrade" + str(wire["max_tokens"])][label, arm + ":" + tag] = wire
        grades = {}
        if set(grade_jobs) - engine.CAP.keys():
            raise ValueError("Unexpected score sampling settings")
        for name, wires in grade_jobs.items():
            grades.update(stage(name, wires))
        metrics = {}
        for label, card in cards.items():
            results = metrics.setdefault(label, {})
            for arm in ("base", "external"):
                row = card[arm]
                results[arm] = previous["summarize"](row["attributes"], row["old_completeness"]) if row["old_strict_score"] else None
            for arm in ARMS:
                results[arm] = None
                if (label, arm) in finals:
                    raw = {tag.split(":")[1]: r["answer"] for (case, tag), r in grades.items()
                           if case == label and tag.split(":")[0] == arm and r["status"] == "OK"}
                    attrs, complete = previous["archived_fields"]({"raw_scores": raw, "actor_status": "OK"}, references[label])
                    results[arm] = previous["summarize"](attrs, complete)
        output = {"proposed": proposed, "answers": [[label, arm, text] for (label, arm), text in finals.items()],
                  "metrics": metrics, "failures": failures, "ledger": ledger, "reuse": reuse}
        path = PRIVATE / "RESULTS.json"
        if live:
            probe.freeze(path, output)
        elif archive.read(path) != output:
            raise ValueError("Settlement replay differs")
        print({"calls": len(ledger), "status": Counter(x["status"] for x in ledger), "failures": failures})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("freeze", "check", "run", "replay"))
    action = cli.parse_args().action
    data = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    freeze = PRIVATE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(freeze, data[0])
    elif archive.read(freeze) != data[0]:
        raise ValueError("Frozen roster or requests changed")
    if action in ("run", "replay"):
        execute(*data, live=action == "run")
    else:
        print(LABELS, data[0]["caps"])
