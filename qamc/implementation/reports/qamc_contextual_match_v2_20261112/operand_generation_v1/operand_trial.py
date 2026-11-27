"""Run equal-budget free revision and deterministic operand execution."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from operand import QUESTIONS, revise
from operand_inputs import prepare
from proposals.qamc_protocol_alignment.transport import token_estimate
from qamc.common import canonical, sha
from qamc.contextual_match.development import text_request
from qamc.pa.core import digest
from qamc_benchpres_matched_fieldwise_audit import archived_fields
import relation_trial as bench
import repair_trial as trial


HERE = Path(__file__).resolve().parent
RUN = trial.RUN.with_name(HERE.name)
ARMS = ("FREE", "OPERAND")
EDIT, BENCH, PERSIST = "OperandEdit", "OperandBenchGrade", "OperandPersistGrade"
CAPS = {EDIT: 48, trial.SCORE_STAGE: 16, BENCH: 96, PERSIST: 16}
COMMON = """Deliver the actual current task, in its original language and format. Consider the current
query first. Use historical evidence only within its legitimate present-day scope and recipient.
Do not transfer another person's constraints or change a participant's role. Do not make a historical
fact current without evidence, or insert an unrelated fact inside a question. Write an open request
only when the actual recipient can help; unsupported causes should remain unknown rather than turn
into irrelevant inquiries. Preserve necessary documents, task scope, format preferences and concrete
steps. Correct every dependent point of a consequential mistake. Subject to applicable constraints,
offer a concrete compatible option without making it mandatory for other participants. A named
alternative from an old draft is an idea, not a confirmed fact; no invented availability or
eligibility. A correct draft can be kept exactly. Both methods receive the same original facts,
preferences, draft and any existing alternative candidates. Use the entire legitimate information.
Prefer minimal changes only when they fully solve the relevant problem.

The operations below describe possible edits for either method, and illustrated question dimensions:
ASK_OPEN uses an open question about the matter in the current task without importing unsupported
history. REPORT_EVENT can report a complete original fact using attribution and its original tense.
OFFER_ALTERNATIVE can add an actual concrete choice while retaining the already valid choices.
TRIM removes a fully independent wrong suggestion or redundant assertion. Do not discard
correct content or greetings/closing to perform one of these operations.
Question dimension templates: """ + canonical(QUESTIONS) + "\nReply only in JSON."
FORMATS = {
    "FREE": """Return {"mode":"KEEP"} or {"mode":"REWRITE","answer":"full usable answer"}. You may
freely realize all the principles, including those illustrated above. You may use other sensible
language, transitions and actions. Do not output metadata or IDs inside the answer.""",
    "OPERAND": """Return {"mode":"KEEP"} or {"mode":"OPERATE","actions":[...]} with up to five unique
draft unit IDs as targets. A complete affected unit will be replaced or removed. For changes use:
{"op":"ASK_OPEN","target":"U01","dimensions":["RECORD","NEXT_STEP"]} replaces the target with up to
two frozen open questions, with no prefilled facts. Use only documented dimension names.
{"op":"REPORT_EVENT","target":"U02","fact_id":"F1"} replaces the target with complete original fact
text prefaced by a records attribution. Retain task-relevant event detail and original time state.
{"op":"OFFER_ALTERNATIVE","target":"U03","choice":"specific option name","evidence":"M1"} appends a
single short concrete noun phrase, keeps the original choice, and explicitly makes the addition
optional. Reuse supplied candidate options where helpful. No clauses or unsupported descriptions.
{"op":"TRIM","target":"U04"} removes the entire independent unit. No arbitrary prose, rebinding
other person's history, or paraphrased replacements. Preserve deliverable essentials. Return KEEP
when the available operations cannot safely improve the complete answer.""",
}


def freeze_inputs():
    cards, packets = prepare()
    wires = {}
    for label, packet in packets.items():
        for arm in ARMS:
            request = text_request(COMMON + "\n\n" + FORMATS[arm], packet, "qwen3.8-flash", 8192)
            if token_estimate(canonical(request["messages"])) > 32768:
                raise ValueError("Operand request exceeds shared context")
            wires[label, arm] = request
    wires = dict(sorted(wires.items(), key=lambda row: sha(["closed-operands-v1", *row[0]])))
    pin = {"counts": Counter(name.split("/")[0] for name in cards),
           "groups": {domain: len({c["group"] for n, c in cards.items() if n.startswith(domain + "/")})
                      for domain in ("RPEval", "BenchPreS", "PersistBench")},
           "source_and_baseline_sha256": sha({n: [c["uid"], c["group"], sha(c["draft"]), sha(packets[n])]
                                              for n, c in cards.items()}),
           "wire_sha256": sha(list(wires.values())), "caps": CAPS,
           "code": {name: sha((HERE / name).read_bytes()) for name in
                    ("operand.py", "operand_inputs.py", "operand_trial.py", "run.sh", "PROTOCOL.md")}}
    return cards, packets, wires, pin


def generate(wires, cards, packets, identity, ledger):
    outputs = {}
    for (label, arm), reply in trial.stage(EDIT, wires, identity, ledger).items():
        answer, operations, error = None, [], None
        state = reply["status"]
        if state == "OK":
            try:
                answer, operations = revise(reply["answer"], packets[label], arm)
                state = "KEEP" if answer == cards[label]["draft"] else "EDITED"
            except (ValueError, TypeError, KeyError) as exc:
                answer, state, error = cards[label]["draft"], "CONTRACT_FALLBACK", str(exc)
        outputs.setdefault(label, {})[arm] = {"answer": answer, "status": state, "ops": operations,
                                              "error": error, "receipt": reply}
    trial.probe.freeze(RUN / "LOCKED_ANSWERS_PRIVATE.json", outputs)
    return outputs


def score_bench(cards, answers, identity, ledger):
    jobs, refs = {}, {}
    scores = {label: dict.fromkeys(ARMS) for label in cards}
    for label, card in cards.items():
        case = card["case"]
        ref = refs[label] = bench.run.read(bench.run.ROOT / case["evaluation_path"])
        if digest(ref) != case["evaluation_hash"]:
            raise ValueError("BenchPreS grader reference changed")
        protocol = card["grade_protocol"]
        for arm in ARMS:
            answer = answers[label][arm]["answer"]
            if not answer:
                continue
            if answer == card["draft"]:
                scores[label][arm] = card["score"]
                continue
            for stage, system, content in bench.run.prior.score.initial_requests(
                    bench.run.ROOT, "benchpres", ref, card["context"]["query"], answer):
                jobs[label, f"{arm}:{stage}"] = bench.run.prior.text_request(
                    system, content, protocol["model"], protocol["stages"][stage]["max_tokens"])
    receipts = trial.stage(BENCH, jobs, identity, ledger)
    trial.probe.freeze(RUN / "BENCH_GRADES_PRIVATE.json", {"/".join(k): v for k, v in receipts.items()})
    for label in cards:
        for arm in ARMS:
            previously = scores[label][arm]
            if previously is not None or answers[label][arm]["answer"] is None:
                continue
            raw = {tag.split(":")[1]: row["answer"] for (name, tag), row in receipts.items()
                   if name == label and tag.startswith(arm + ":") and row["status"] == "OK"}
            attrs, complete = archived_fields({"actor_status": "OK", "raw_scores": raw}, refs[label])
            scores[label][arm] = bench.summarize(attrs, complete)
    return scores


def score_persist(cards, answers, identity, ledger):
    from complete import archive
    jobs, scores = {}, {label: dict.fromkeys(ARMS) for label in cards}
    for label, card in cards.items():
        envelope = card["score_envelope"]
        prefix = envelope["messages"][:-1]
        body = envelope["messages"][-1]
        marker = "<response>\n{{ANSWER}}\n</response>"
        if body["content"].count(marker) != 1:
            raise ValueError("Ambiguous archived answer slot")
        for arm in ARMS:
            answer = answers[label][arm]["answer"]
            if not answer:
                continue
            if answer == card["draft"]:
                scores[label][arm] = card["score"]
                continue
            msg = {**body, "content": body["content"].replace(marker, f"<response>\n{answer}\n</response>")}
            jobs[label, arm] = {**envelope, "messages": [*prefix, msg]}
    receipts = trial.stage(PERSIST, jobs, identity, ledger)
    trial.probe.freeze(RUN / "PERSIST_GRADES_PRIVATE.json", {"/".join(k): r for k, r in receipts.items()})
    scorer = archive["persist"].author.ext.parent.persist
    for (label, arm), reply in receipts.items():
        if reply["status"] != "OK":
            continue
        try:
            scores[label][arm] = scorer.score(cards[label]["track"], reply["answer"])
        except (TypeError, KeyError, ValueError):
            continue
    return scores


def score_rpe(cards, answers, identity, ledger):
    inputs = {c["key"]: c["raw_packet"] for c in cards.values()}
    bindings = {c["key"]: c["binding"] for c in cards.values()}
    records = {c["key"]: answers[label] for label, c in cards.items()}
    scored = trial.measure(inputs, bindings, records, identity, ledger)
    return {label: {arm: scored[c["key"]][arm]["score"] for arm in ARMS} for label, c in cards.items()}


def execute(cards, packets, wires, identity):
    ledger = []
    answers = generate(wires, cards, packets, identity, ledger)
    joined = {}
    for domain, method in (("RPEval", score_rpe), ("BenchPreS", score_bench), ("PersistBench", score_persist)):
        items = {label: c for label, c in cards.items() if label.startswith(domain + "/")}
        scores = method(items, answers, identity, ledger)
        for label, card in items.items():
            joined[label] = {"group": sha(card["group"]), "track": card.get("track"),
                             "grade": {"BASE": card["score"], **scores[label]},
                             "references": card["references"],
                             "disposition": {arm: answers[label][arm]["status"] for arm in ARMS},
                             "operations": {arm: answers[label][arm]["ops"] for arm in ARMS},
                             "errors": {arm: answers[label][arm]["error"] for arm in ARMS}}
    cost = {"requests": len(ledger), "stages": Counter(row["unit"]["stage"] for row in ledger),
            "statuses": Counter(row["status"] for row in ledger),
            "tokens": sum((row["usage"] or {}).get("total_tokens") or 0 for row in ledger),
            "unknown_usage": sum((row["usage"] or {}).get("total_tokens") is None for row in ledger),
            "retries": sum(row.get("automatic_retries", 0) for row in ledger)}
    trial.probe.freeze(RUN / "LEDGER.json", ledger)
    trial.probe.freeze(RUN / "SUMMARY.json", {"cases": joined, "cost": cost})
    return {"cases": joined, "cost": cost}


def main(command):
    if command == "report":
        print(json.dumps(trial.read(RUN / "SUMMARY.json"), ensure_ascii=False, indent=2))
        return
    cards, packets, wires, pin = freeze_inputs()
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.ARMS = ARMS
    trial.engine.CAP = CAPS
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if command == "freeze":
            trial.probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if trial.read(RUN / "FROZEN.json") != pin:
            raise ValueError("Frozen comparison changed")
        active = trial.probe.read_reference()[1]
        if active != trial.read(trial.VETO / "EXECUTION.json")["service_reference_sha256"]:
            raise ValueError("Archived Actor service identity changed")
        identity = {"experiment_sha256": sha(pin), "service_reference_sha256": active}
        trial.probe.freeze(RUN / "EXECUTION.json", identity)
        result = trial.read(RUN / "SUMMARY.json") if (RUN / "SUMMARY.json").is_file() else execute(cards, packets, wires, identity)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    main(parser.parse_args().action)
