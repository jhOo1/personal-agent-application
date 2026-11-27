"""Score fixed BenchPreS relation corrections and recipient-action variants."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from freeze_reflection import PRIVATE, inventory, token
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import canonical, sha
from qamc.pa.core import digest
from qamc_benchpres_matched_fieldwise_audit import BOLD, archived_fields
from run_reflection_model import PROMPT, parse
from trace_misuse import run
import run_reflection_gpt41 as reflection
import run_reflection_nonbold_census as census
import repair_trial as trial


HERE = Path(__file__).resolve().parent
RUN = trial.RUN.with_name(HERE.name)
QWEN = "BenchQwen"
GPT = "BenchReflection"
VARIANTS = {"BASE": (), "GROUND": ("ground",), "ACTION": ("action",), "JOINT": ("ground", "action")}


def render(source, edits):
    ranges = []
    for original, replacement in edits:
        if not original or source.count(original) != 1 or original == replacement:
            raise ValueError("A fixed edit does not uniquely bind")
        start = source.index(original)
        ranges.append((start, start + len(original), replacement))
    ranges.sort()
    if any(b[0] < a[1] for a, b in zip(ranges, ranges[1:])):
        raise ValueError("Grounding and communication edits overlap")
    answer, end = [], 0
    for start, stop, text in ranges:
        answer.extend((source[end:start], text))
        end = stop
    answer.append(source[end:])
    return "".join(answer)


def old_reflection(source, manual, method, answer):
    plan = run.read(census.ROOT / "PLAN_PRIVATE.json")
    if not (census.ROOT / "TERMINAL").is_file():
        raise ValueError("Only terminal reference grades can be reused")
    seed = bytes.fromhex((PRIVATE / "SEED_PRIVATE").read_text())
    opaque = token(seed, "census-slot", manual["uid"], manual["draw"], manual["target"])[:24]
    slot, = [r for r in plan["slots"] if r["pair"] == opaque and r["was_original_common"]]
    expected = slot["arms"][method]["request_sha256"]
    for root, units in ((census.ROOT, plan["units"]), (reflection.ROOT, reflection.plan_from_source()["units"])):
        for job in units:
            if sha(job["request"]) != expected:
                continue
            receipt, vote = reflection.receipt(job, root)
            if receipt is None or vote is None:
                raise ValueError("Missing target reflection response")
            payload = json.loads(job["request"]["messages"][1]["content"])
            attr = source["preference_attribute"][manual["target"]]
            if payload != {"attribute": attr, "answer": answer}:
                raise ValueError("Target reflection grading envelope drift")
            data = run.read(root / "execution" / "visible" / sampling_key(job["unit"]) / "response.json")
            return parse(data["answer"], job["request"])
    raise ValueError("Unbound target reflection score")


def assign():
    edits = run.read(RUN / "MANUAL_EDITS_PRIVATE.json")
    if set(edits) != {"tax_discrepancy", "debt_consolidation"}:
        raise ValueError("Only the two known development diagnostic cases are allocated")
    parent = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(parent)
    cases = {r["uid"]: r for r in parent["cases"]}
    draws, _ = inventory()
    archived = {(r["uid"], r["draw"], r["method"]): r for r in draws}
    job_rows, cards = {QWEN: {}, GPT: {}}, {}
    protocol = parent["protocols"]["grading"]
    for name, m in edits.items():
        case = cases[m["uid"]]
        if case["independent_confirmation"]:
            raise ValueError("Diagnostic is restricted to exposed tasks")
        ref = run.read(run.ROOT / case["evaluation_path"])
        if digest(ref) != case["evaluation_hash"]:
            raise ValueError("Reference drift")
        base = archived[m["uid"], m["draw"], run.GATE]
        if not base["old_strict_score"] or sha(base["answer"]) != m["base_sha256"]:
            raise ValueError("Missing exact strong baseline")
        target = m["target"]
        if not ref["preference_label"][target] or BOLD.search(ref["preference_attribute"][target]):
            raise ValueError("Target must be applicable and non-bold")
        task = run.prior.base.task_for(case)
        outputs = {arm: render(base["answer"], [line for part in parts for line in m[part]])
                   for arm, parts in VARIANTS.items()}
        if len(set(outputs.values())) != len(VARIANTS):
            raise ValueError("Diagnostic answers must differ")
        if any(bit not in answer for bit in m["protected"] for answer in outputs.values()):
            raise ValueError("Verified formatting or message identity was removed")
        for arm, answer in outputs.items():
            if arm == "BASE":
                continue
            for stage, sys, content in run.prior.score.initial_requests(run.ROOT, "benchpres", ref, task.query, answer):
                wire = run.prior.text_request(sys, content, protocol["model"], protocol["stages"][stage]["max_tokens"])
                job_rows[QWEN][name, f"{arm}:{stage}"] = wire
            job_rows[GPT][name, arm] = {
                "model": reflection.PROTOCOL["model"], "stream": True, "stream_options": {"include_usage": True},
                **reflection.PROTOCOL["stages"]["Reflection"],
                "messages": [{"role": "system", "content": PROMPT},
                             {"role": "user", "content": canonical(
                                 {"attribute": ref["preference_attribute"][target], "answer": answer})}]}
        cards[name] = {"reference": ref, "base": base, "answers": outputs, "manual": m}
    pin = {"manual_edits_sha256": sha(edits), "answer_inventory_sha256": sha({n: c["answers"] for n, c in cards.items()}),
           "wires_sha256": {s: sha(list(v.values())) for s, v in job_rows.items()},
           "cap": {s: len(v) for s, v in job_rows.items()},
           "code": {f: sha((HERE / f).read_bytes()) for f in ("action_grounding.py", "run.sh", "PROTOCOL.md")}}
    return cards, job_rows, pin


def fields(attrs, complete, target, gpt):
    def count(selected):
        known = sum(a["follow"] is not None for a in selected)
        return {"follow": sum(a["follow"] or 0 for a in selected), "valid": known, "allocated": len(selected)}
    return {"target_qwen": attrs[target]["follow"], "target_gpt41": gpt, "completeness": complete,
            "AAR": count([a for a in attrs if a["appropriate"]]),
            "MR": count([a for a in attrs if not a["appropriate"]]),
            "bold_AAR": count([a for a in attrs if a["appropriate"] and BOLD.search(a["attribute"])]),
            "nonbold_AAR": count([a for a in attrs if a["appropriate"] and not BOLD.search(a["attribute"])])}


def settle(cards, jobs, receipts, ledger):
    details, diagnostics = {}, {}
    for name, row in cards.items():
        target = row["manual"]["target"]
        base = row["base"]
        prior = old_reflection(row["reference"], row["manual"], run.GATE, base["answer"])
        diagnostics[name] = {"BASE": fields(base["attributes"], base["old_completeness"], target, prior["reflection"])}
        details[name] = {"BASE": {"answer": base["answer"], "old_reflection": prior}}
        for arm, answer in row["answers"].items():
            if arm == "BASE":
                continue
            delivered = {stage: r for (case, tag), r in receipts[QWEN].items() if case == name
                         for method, stage in [tag.split(":")] if method == arm}
            raw = {s: r["answer"] for s, r in delivered.items() if r["status"] == "OK"}
            attrs, complete = archived_fields({"raw_scores": raw, "actor_status": "OK"}, row["reference"])
            r = receipts[GPT][name, arm]
            reflection_value = None
            if r["status"] == "OK":
                try:
                    reflection_value = parse(r["answer"], jobs[GPT][name, arm])["reflection"]
                except (TypeError, ValueError, KeyError):
                    pass
            details[name][arm] = {"answer": answer, "raw_qwen": delivered, "raw_gpt41": r, "attributes": attrs}
            diagnostics[name][arm] = fields(attrs, complete, target, reflection_value)
    usage = [(r["usage"] or {}).get("total_tokens") for r in ledger]
    result = {"cases": diagnostics, "physical_requests": len(ledger),
              "by_stage": Counter(r["unit"]["stage"] for r in ledger),
              "transport_status": Counter(r["status"] for r in ledger),
              "usage_unknown": usage.count(None), "tokens": sum(t or 0 for t in usage),
              "automatic_retries": sum(r.get("automatic_retries", 0) for r in ledger),
              "new_generation_calls": 0, "manual_diagnostic": True}
    trial.probe.freeze(RUN / "COMPLETE_PRIVATE.json", details)
    trial.probe.freeze(RUN / "SUMMARY.json", result)
    return result


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    cards, jobs, pin = assign()
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.engine.CAP = pin["cap"]
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            trial.probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if pin != trial.read(RUN / "FROZEN.json"):
            raise ValueError("Diagnostic freeze drift")
        if action == "run" and not (RUN / "LEDGER.json").is_file():
            seen = {n: row["answers"] for n, row in cards.items()}
            trial.probe.freeze(RUN / "LOCKED_VARIANTS_PRIVATE.json", seen)
            identity = {"experiment_sha256": sha(pin), "service_reference_sha256": trial.probe.read_reference()[1]}
            archived_identity = run.read(census.ROOT / "PLAN_PRIVATE.json")["service_sha256"]
            if identity["service_reference_sha256"] != archived_identity:
                raise ValueError("Grading service differs from the older evaluator")
            trial.probe.freeze(RUN / "EXECUTION.json", identity)
            ledger = []
            receipts = {s: trial.stage(s, table, identity, ledger) for s, table in jobs.items()}
            serial = {s: {f"{n}/{arm}": row for (n, arm), row in table.items()} for s, table in receipts.items()}
            trial.probe.freeze(RUN / "RECEIPTS_PRIVATE.json", serial)
            if len(ledger) > sum(pin["cap"].values()):
                raise ValueError("Diagnostic grading cap exceeded")
            trial.probe.freeze(RUN / "LEDGER.json", ledger)
        else:
            saved = trial.read(RUN / "RECEIPTS_PRIVATE.json")
            receipts = {s: {tuple(tag.split("/")): row for tag, row in table.items()} for s, table in saved.items()}
            ledger = trial.read(RUN / "LEDGER.json")
        print(json.dumps(settle(cards, jobs, receipts, ledger), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
