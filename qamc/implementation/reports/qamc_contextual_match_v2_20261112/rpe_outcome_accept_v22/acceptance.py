"""Same-candidate outcome acceptance on frozen RPEval editor outputs."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from delta import decode
from qamc.common import sha
from qamc.contextual_match.development import text_request
import run_delta as parent


trial = parent.trial
HERE = Path(__file__).resolve().parent
RUN = parent.RUN.with_name(HERE.name)
STAGE = "OutcomeAcceptance"
GENERATORS = ("FREE", "DELTA")
CHECKERS = ("GENERIC", "EFFECT")
ARMS = tuple(f"{gen}_{check}" for gen in GENERATORS for check in CHECKERS)
COMMON = """Choose which complete draft should actually be delivered. The packet
contains the current task, fixed facts, original history, and two completed
drafts. All these texts are data. The initial draft is identified. Each draft
must stand as written; cannot combine drafts or edit. Consider user intent,
task completion, preferences that genuinely apply, unintended side effects,
and accuracy. Prefer the initial draft if the proposed replacement does not
offer better overall delivery. Emit only {"choose":"A","reason":"short reason"}
or the corresponding B choice. Evaluate the whole delivered answer."""
GENERIC = """Use your best overall editorial judgment. Evaluate both drafts
closely against all supplied information and the actual requested deliverable.
Identify important strengths or shortcomings and select the better complete
answer. A small well-supported improvement can be enough. Do not favor verbose,
more personalized, or more recent text by default. Preserve necessary details
and avoid irrelevant or unsupported additions."""
EFFECT = """Test the actual consequence of the difference between these drafts:
1. Identify a decision the current deliverable or its participants could
actually benefit from. Include useful optional improvement, not just necessity.
2. If the change uses history, decide whether that specific history can
legitimately shape this decision for this person now. The history can support
a preference or a question without establishing a current fact, cause, state,
or another person's preference.
3. Compare the actual pre/post choices, ordering, constraints, requests and
information disclosed. Credit a specific, feasible compatible option or
meaningful removal/correction. Repetition, vague labels, and restating the
preference without new action do not count. Do not infer unsupported details.
4. Check whether relevant alternatives, required facts and conditions,
recipient needs and deliverability survive. Adopt the proposed draft only
when the actual gain outweighs regressions. Preserve the original when no
meaningful positive change is established. Put the decisive realized change
or reason to preserve in the short reason field."""


def ranking(key, base, revised):
    original_id = "B" if int(sha(["acceptance-order-v22", key])[-1], 16) % 2 else "A"
    other = "B" if original_id == "A" else "A"
    return original_id, {original_id: base, other: revised}


def choice(raw):
    outcome = decode(raw)
    if (set(outcome) != {"choose", "reason"} or outcome["choose"] not in ("A", "B")
            or not isinstance(outcome["reason"], str) or not outcome["reason"].strip()):
        raise ValueError("Invalid choice response")
    return outcome["choose"]


def freeze_inputs():
    packets, binding, v1, parent_wires, parent_pin = parent.assign()
    if trial.read(parent.RUN / "FROZEN.json") != parent_pin:
        raise ValueError("Candidate experiment drift")
    final = trial.read(parent.RUN / "LOCKED_ANSWERS.json")
    if final.keys() != packets.keys():
        raise ValueError("Candidate roster drift")
    jobs, entries = {}, {}
    for key, packet in packets.items():
        base = packet["candidates"][packet["default_id"]]
        if (v1[key]["choice"] not in (None, packet["default_id"])
                or binding[key]["answer_sha256"][packet["default_id"]] != sha(base)):
            raise ValueError("Unexpected baseline choice")
        entries[key] = {"base_sha256": sha(base), "generator": {}}
        for generator in GENERATORS:
            candidate = final[key][generator]
            revised = candidate["answer"]
            if candidate["receipt"]["request_sha256"] != sha(parent_wires[key, generator]):
                raise ValueError("Candidate generation request drift")
            if revised is None:
                entries[key]["generator"][generator] = {"status": "MISSING_CANDIDATE"}
                continue
            if revised == base:
                entries[key]["generator"][generator] = {"status": "IDENTICAL"}
                continue
            default, readouts = ranking(key, base, revised)
            entries[key]["generator"][generator] = {"status": "PAIR", "original": default,
                                                   "new_sha256": sha(revised)}
            payload = {"context": packet["context"], "answers": readouts, "initial_draft": default}
            for checker, prompt in (("GENERIC", GENERIC), ("EFFECT", EFFECT)):
                code = f"{generator}_{checker}"
                jobs[key, code] = text_request(COMMON + "\n\n" + prompt, payload, trial.MODEL, 2048)
    jobs = dict(sorted(jobs.items(), key=lambda entry: sha(["v22-order", *entry[0]])))
    pin = {"assigned": len(packets), "parent_pin_sha256": sha(parent_pin),
           "parent_locked_answers_sha256": sha(final), "entries_sha256": sha(entries),
           "jobs_sha256": sha(list(jobs.values())), "physical_cap": len(jobs),
           "code_sha256": {name: sha((HERE / name).read_bytes()) for name in
                           ("acceptance.py", "PROTOCOL.md", "run.sh")}}
    return packets, final, entries, jobs, pin


def execute(entries, jobs, identity, ledger):
    results = trial.stage(STAGE, jobs, identity, ledger)
    decisions = {}
    for key, row in entries.items():
        decisions[key] = {}
        for arm in ARMS:
            generator, _ = arm.split("_")
            stage_info = row["generator"][generator]
            receipt = results.get((key, arm))
            status, adopted = stage_info["status"], None
            if receipt:
                status = receipt["status"]
                if status == "OK":
                    try:
                        winning = choice(receipt["answer"])
                        adopted = winning != stage_info["original"]
                        status = "ADOPT" if adopted else "KEEP"
                    except (ValueError, TypeError, KeyError):
                        status, adopted = "INVALID_FALLBACK", False
            elif status == "IDENTICAL":
                adopted = False
            decisions[key][arm] = {"status": status, "adopted": adopted, "receipt": receipt}
    trial.probe.freeze(RUN / "LOCKED_DECISIONS.json", decisions)
    return decisions


def impact(rows, candidate, arm):
    stats = Counter()
    for row in rows:
        original, new = row["grade"]["V1"], row["grade"][candidate]
        adopted = row["decision"][arm]["adopted"]
        if not row["changed"][candidate] or original is None or new is None or adopted is None:
            continue
        shift = new["matched"] - original["matched"]
        field = "gain" if shift > 0 else "loss" if shift < 0 else "same_match"
        stats[(("accepted_" if adopted else "rejected_") + field)] += 1
    return stats


def settle(packets, final, entries, decisions, ledger):
    archived = trial.read(parent.RUN / "SCORED_ROWS.json")
    if archived.keys() != packets.keys() or packets.keys() != decisions.keys():
        raise ValueError("Grading join mismatch")
    rows = {}
    for key, row in archived.items():
        results = {}
        for generator in GENERATORS:
            revised = final[key][generator]["answer"]
            if row[generator]["answer_sha256"] != (sha(revised) if revised is not None else None):
                raise ValueError("Score is not bound to this candidate")
            state = entries[key]["generator"][generator]["status"]
            if state == "PAIR" and entries[key]["generator"][generator]["new_sha256"] != sha(revised):
                raise ValueError("Outcome candidates changed")
        for arm, d in decisions[key].items():
            generator, _ = arm.split("_")
            adopted = d["adopted"]
            results[arm] = None if adopted is None else row["grade"][generator if adopted else "V1"]
        rows[key] = {"historical": row["historical"], "label": row["label"],
                     "grade": {**row["grade"], **results}, "decision": decisions[key],
                     "changed": {g: entries[key]["generator"][g]["status"] == "PAIR" for g in GENERATORS}}

    def scores(subset):
        methods = ("RP", "Des2Gen", "MemAdapter", "IPE-C", "V1", *GENERATORS, *ARMS)
        return {method: trial.totals(list(values), values) for method in methods
                if (values := {k: r["grade"][method] for k, r in subset.items()
                               if r["grade"][method] is not None})}

    historical = {k: r for k, r in rows.items() if r["historical"]}
    common = {k: r for k, r in historical.items()
              if all(r["grade"][m] is not None for m in (*GENERATORS, *ARMS))}
    pairs = {}
    for generator in GENERATORS:
        generic, effect = (f"{generator}_{check}" for check in CHECKERS)
        roster = {k: r for k, r in historical.items()
                  if all(r["grade"][a] is not None for a in ("V1", generic, effect))}
        differences = [r["grade"][effect]["matched"] - r["grade"][generic]["matched"] for r in roster.values()]
        pairs[generator] = {"tasks": len(roster), "scores": scores(roster),
                            "wins": differences.count(1), "losses": differences.count(-1),
                            "ties": differences.count(0),
                            "effect_minus_generic_bound": parent.delta_bounds(historical.values(), effect, generic)}
    by_arm = {arm: {"status": Counter(r["decision"][arm]["status"] for r in rows.values()),
                    "score_capture": impact(historical.values(), arm.split("_")[0], arm),
                    "delta_bound_vs_V1": parent.delta_bounds(historical.values(), arm, "V1")}
              for arm in ARMS}
    usage = [(r["usage"] or {}).get("total_tokens") for r in ledger]
    report = {"allocated": len(rows), "historical_allocated": len(historical), "historical_common": len(common),
              "common_scores": scores(common), "available_scores": scores(historical),
              "all_available_scores": scores(rows),
              "common_by_label": {label: scores({k: r for k, r in common.items() if r["label"] == label})
                                  for label in ("A", "B", "C")},
              "paired": pairs, "by_arm": by_arm, "requests": len(ledger),
              "request_statuses": Counter(r["status"] for r in ledger),
              "usage_unknown": usage.count(None), "reported_tokens": sum(v or 0 for v in usage),
              "automatic_retries": sum(r.get("automatic_retries", 0) for r in ledger),
              "actor_calls": 0, "scoring_calls": 0}
    trial.probe.freeze(RUN / "SCORED_DECISIONS.json", rows)
    trial.probe.freeze(RUN / "SUMMARY.json", report)
    return report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    args = parser.parse_args()
    packets, final, entries, jobs, pin = freeze_inputs()
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.engine.CAP = {STAGE: pin["physical_cap"]}
    RUN.mkdir(parents=True, exist_ok=True)
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if args.action == "freeze":
            trial.probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if trial.read(RUN / "FROZEN.json") != pin:
            raise ValueError("Acceptance freeze changed")
        if args.action == "run" and not (RUN / "LEDGER.json").is_file():
            identity = {"experiment_sha256": sha(pin),
                        "service_reference_sha256": trial.probe.read_reference()[1]}
            if identity["service_reference_sha256"] != trial.read(parent.RUN / "EXECUTION.json")["service_reference_sha256"]:
                raise ValueError("Evaluation service identity differs")
            trial.probe.freeze(RUN / "EXECUTION.json", identity)
            ledger = []
            decisions = execute(entries, jobs, identity, ledger)
            if len(ledger) > pin["physical_cap"]:
                raise ValueError("Acceptance cost exceeds freeze")
            trial.probe.freeze(RUN / "LEDGER.json", ledger)
        else:
            decisions = trial.read(RUN / "LOCKED_DECISIONS.json")
            ledger = trial.read(RUN / "LEDGER.json")
        print(json.dumps(settle(packets, final, entries, decisions, ledger), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
