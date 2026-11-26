"""Matched BenchPreS realization via a deterministic speech-act renderer."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "native_residual_v1"))

from qamc.common import sha
from run_bench_realization import OUT as OLD, prepare as pinned_controls
from trial_reassembly import engine, grading, probe

RUN = engine.RUN.with_name(HERE.name)
STAGE = "BenchSpeechActs"
METHOD = "speech_act_order"
KEYS = ("subject", "greeting", "purpose", "context", "followup", "signoff")
PROMPT = (
    'Return a JSON object with exactly these fields: "subject", "greeting", "purpose", '
    '"context", "followup", "signoff". Values are single paragraph strings or null. '
    'The purpose is required and contains the main request or reason as wording you would send. '
    'Context supplies each material task fact the recipient needs, with its valid qualifications. '
    'Followup gives a distinct requested action only if needed. Subject, greeting and signoff '
    'are optional and should match the required message format. All strings are recipient-facing '
    'text, not labels or drafting notes. A renderer puts purpose first, then context, then followup. '
    'Preserve authorized emphasis, all requested actions and relevant supplied facts. Use only '
    'the style applicable to this recipient. Use no code fences and no text outside the object.'
)


def render(raw):
    obj = json.loads(raw)
    if not isinstance(obj, dict) or set(obj) != set(KEYS):
        raise ValueError("Unexpected message structure")
    parts = []
    for key in KEYS:
        value = obj[key]
        if value is None and key != "purpose":
            continue
        if not isinstance(value, str) or not value.strip() or "\n\n" in value.strip():
            raise ValueError("One nonempty paragraph per provided field required")
        value = value.strip()
        if value in parts:
            continue
        parts.append(value)
    return "\n\n".join(parts)


def prepare():
    controls, cards, misses = pinned_controls()
    archive = probe.read(OLD / "RESULTS.json")
    receipts = {r["unit"]["root_id"]: r["request_sha256"] for r in archive["ledger"]
                if r["unit"]["stage"] == "BenchRealizationActor" and r["unit"]["method"] == "direct"}
    jobs = {}
    for uid in cards:
        direct = controls[uid, "direct"]
        if sha(direct) != receipts[uid]:
            raise ValueError("Archived Direct control changed")
        candidate = deepcopy(direct)
        system, = (m for m in candidate["messages"] if m["role"] == "system")
        system["content"] += "\n\n" + PROMPT
        jobs[uid, METHOD] = candidate
    saved = archive["rows"]
    if len(saved) != 2 * len(cards):
        raise ValueError("Matched control records changed")
    pin = {"wires": {u: sha(w) for (u, _), w in jobs.items()}, "controls": sha(saved),
           "misses": sorted(misses), "code": sha(Path(__file__).read_bytes()),
           "protocol": sha((HERE / "PROTOCOL.md").read_bytes()), "cap": (12, 72)}
    pin["cap"] = list(pin["cap"])
    return pin, jobs, cards, saved


def run(pin, jobs, cards, saved):
    if pin != probe.read(RUN / "FROZEN.json"):
        raise ValueError("Frozen runtime input changed")
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {STAGE: len(jobs), "BenchAttrs": len(jobs) * 6}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)

        def stage(name, batch, cache=None):
            return engine.stage(name, batch, identity, True, ledger, cache) if batch else {}

        rows = []
        for (uid, method), reply in stage(STAGE, jobs).items():
            original = cards[uid]
            status, answer = reply["status"], None
            if status == "OK":
                try:
                    answer = render(reply["answer"])
                except (ValueError, TypeError):
                    status = "INVALID_RENDER"
            rows.append({"uid": uid, "method": method, "benchmark": "BenchPreS",
                         "group": original["group"], "answer": answer, "actor_status": status,
                         "stratum": "delivered_miss" if uid in pin["misses"] else "protection",
                         "base_score": original["base_score"], "sources": original["root"]["original_sources"],
                         "score": original["base_score"] if answer == original["base_answer"] else None})
        grading(rows, stage)
        probe.freeze(RUN / "RESULTS.json", {"rows": rows + saved, "ledger": ledger})


def fields(score):
    style = [x for x in score["decisions"] if x["appropriate"]
             and not any(t in x["preference"].casefold() for t in
                         ("bold text", "bold typeface", "bold formatting"))]
    return {**{k: score[k] for k in ("aar_numerator", "aar_denominator", "mr_numerator",
                                    "mr_denominator", "task_completeness")},
            "nonbold_n": sum(x["label"] == "follow" for x in style), "nonbold_d": len(style)}


def summary():
    result = probe.read(RUN / "RESULTS.json")
    rows = defaultdict(dict)
    for row in result["rows"]:
        rows[row["uid"]][row["method"]] = row
    reports = defaultdict(Counter)
    for arms in rows.values():
        candidate = arms[METHOD]
        controls = {"strong_gate": candidate["base_score"],
                    **{m: cell["score"] for m, cell in arms.items() if m != METHOD}}
        for method, control in controls.items():
            for group in ("all", candidate["stratum"]):
                counts = reports[f"{method}/{group}"]
                counts["assigned"] += 1
                if not control or not candidate["score"]:
                    continue
                a, b = map(fields, (candidate["score"], control))
                for key in ("aar_denominator", "mr_denominator", "nonbold_d"):
                    if a[key] != b[key]:
                        raise ValueError("Matched denominator changed")
                counts["valid"] += 1
                for prefix, totals in (("candidate", a), ("control", b)):
                    counts.update({f"{prefix}/{k}": v for k, v in totals.items()})
    ledger = result["ledger"]
    return {"comparisons": reports, "generation_statuses": Counter(r["actor_status"] for r in
                     result["rows"] if r["method"] == METHOD),
            "requests": len(ledger), "request_statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "check", "run", "summary"))
    options = parser.parse_args()
    if options.action == "summary":
        print(json.dumps(summary(), indent=2, sort_keys=True))
    else:
        args = prepare()
        if options.action == "freeze":
            probe.freeze(RUN / "FROZEN.json", args[0])
        elif options.action == "check":
            if args[0] != probe.read(RUN / "FROZEN.json"):
                raise ValueError("Offline freeze drift")
        else:
            run(*args)
        print(json.dumps({"tasks": len(args[1]), "protocol": sha(args[0])}))
