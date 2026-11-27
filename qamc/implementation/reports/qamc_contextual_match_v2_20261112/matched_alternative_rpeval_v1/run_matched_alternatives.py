"""Open versus matched task alternatives with one shared editor contract."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

import baselines
import candidate_space as prior_panel
import run_decision_edit as grading
import run_delta as single
from qamc.common import canonical, sha
from qamc.contextual_match.development import text_request
from qamc.pa.core import digest
from delta import decode
import repair_trial as trial


HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RUN = trial.RUN.with_name(HERE.name)
ARMS = ("OPEN", "MATCHED")
SUPPLY, DRAFT, NATIVE = "CandidateSupply", "CandidateAnswer", "MultiCandidateJudge"
BRUNCH = "f051b02d"
CAPS = {SUPPLY: 26, DRAFT: 26, NATIVE: 24, trial.SCORE_STAGE: 2}
COMMON = """You supply exactly two independent concrete possibilities for the current user's task.
You see the current request, facts, and original candidate history. Keep the intended recipients,
people, task, and applicable hard constraints intact. History may be used only when it helps the
person and goal it actually applies to. Do not assume unlisted dietary restrictions, private regimes
for third parties, or details about unknown real-world availability. Output two meaningful actions or
specific recommendations that could be executed rather than categories or generic guidance. Neither
option is a final answer and neither commits to using memory. You cannot see or edit the baseline.
In the language of the task, return only a JSON object {"ideas":[{"name":"specific choice","how":
"one or two sentences of actual execution"}, {"name":"specific choice","how":"actual execution"}]}.
Give short names and keep each explanation below 650 characters. Consider useful ideas without
needing to include a historical preference at all."""
SUPPLY_POLICY = {
    "OPEN": """Choose the two most useful distinct ways to fulfil the task. Explore a diversity
of feasible options, including task-only ideas when history does not help. Both can differ on any
feasible dimension as long as they serve the actual task.""",
    "MATCHED": """Identify one actual consequential decision in the request. Keep both options
matched on that decision, the same people and the same current constraints. The first plan must be
sufficient from current facts and task alone. Make the second concretely different in this same
decision. Where a relevant preference might benefit someone, offer one compatible change without
imposing it on anyone else; otherwise choose another task-supported concrete change. Do not use
added fictional circumstances as the reason a variant works. Do not write your internal comparison.""",
}
REALIZE = """Answer the original request completely in its language and format. The archived response is
an option worth retaining if still best, and the two suggested plans are fallible ideas. Verify that
any revised choice is feasible under the stated facts and hard conditions; only bring in historical
preferences that serve the people and goal currently involved. Current query constraints control the
answer. Treat old people, locations and private details as historical unless the task connects them.
A soft preference of one person must not become a shared requirement. If including a suggestion,
make it concrete and usable, protect correct aspects of the existing delivery, and avoid announcing
the memory mechanism. No suggested option is mandatory. Return only {"mode":"KEEP"} if no
material improvement, or {"mode":"ANSWER","answer":"complete user-facing answer"}."""


def cards():
    panel, roots = prior_panel.roster()
    history = baselines.rpe()
    archived = {row["uid"]: row for row in prior_panel.read(
        BASE / "candidate_distribution_rpeval_v1/SETTLED.json")["rows"]}
    rows = []
    for stratum, size in (("B_only", 6), ("all_A", 3), ("contains_C", 3)):
        subset = [r for r in panel if r["stratum"] == stratum]
        subset = sorted(subset, key=lambda row: sha(["matched-supply-v1", row["source_group"]]))[:size]
        if len(subset) != size:
            raise ValueError("Exposed control stratum changed")
        for case in subset:
            uid = case["uid"]
            anchor = roots[uid]
            old = history[uid]
            saved = archived[uid]
            if old["group"] != case["source_group"] or anchor["public_task"] != old["root"]["public_task"]:
                raise ValueError("Exact IPE-C task or group drift")
            refs = {alias: {"grade": cell["fields"], "flags": cell["flags"]}
                    for alias, cell in saved["controls"].items()}
            refs.update({alias: {"grade": cell["grade"]["fields"],
                                 "flags": cell["grade"].get("invalid_fields")}
                         for alias, cell in saved["new"].items()})
            rows.append({**case, "track": "multi", "answer": old["base_answer"], "grade": old["base_score"],
                         "flags": old["base_flags"], "references": refs,
                         "task": {**anchor["public_task"], "history": anchor["original_sources"]}})
    packets, binding, choices, _, _ = single.assign()
    key, = [k for k, row in binding.items() if row["uid"].rsplit("/", 1)[-1].startswith(BRUNCH)]
    packet = packets[key]
    selected = choices[key]["choice"] or packet["default_id"]
    uid = binding[key]["uid"]
    source, = [r for r in prior_panel.read(BASE / "paper_baseline_validation_156_v1/MANIFEST_156.json") if r["uid"] == uid]
    if source["independent_confirmation"]:
        raise ValueError("Brunch reference must be exposed")
    archived_single = trial.read(single.RUN / "SCORED_ROWS.json")[key]["grade"]
    rows.append({"uid": uid, "track": "single", "stratum": "B_only",
                 "source_group": source["group_id"], "answer": packet["candidates"][selected],
                 "grade": archived_single["V1"], "flags": None,
                 "references": {m: {"grade": archived_single[m]} for m in ("RP", "Des2Gen", "MemAdapter", "IPE-C")},
                 "task": packet["context"], "native_key": key, "native_binding": binding[key], "native_input": packet})
    if len({r["source_group"] for r in rows}) != len(rows) or len(rows) != 13:
        raise ValueError("Unexpected evidence group allocation")
    return {r["uid"]: r for r in rows}


def parse_ideas(reply):
    value = decode(reply)
    items = value.get("ideas")
    if set(value) != {"ideas"} or not isinstance(items, list) or len(items) != 2:
        raise ValueError("Two candidate plans required")
    for idea in items:
        if set(idea) != {"name", "how"} or any(not isinstance(idea[k], str) or
            not 1 <= len(idea[k].strip()) <= limit for k, limit in (("name", 90), ("how", 650))):
            raise ValueError("Candidate name or execution fails schema")
    if items[0] == items[1]:
        raise ValueError("Exactly duplicated plans")
    return items


def freeze_plan():
    roster = cards()
    jobs = {(uid, arm): text_request(COMMON + "\n\n" + SUPPLY_POLICY[arm], row["task"], "qwen3.8-flash", 3072)
            for uid, row in roster.items() for arm in ARMS}
    jobs = dict(sorted(jobs.items(), key=lambda pair: sha(["matched-alt-experiment", *pair[0]])))
    pin = {"source_pins": sha(roster), "candidate_wires": sha(list(jobs.values())), "caps": CAPS,
           "roster": Counter((row["track"] + "/" + row["stratum"]) for row in roster.values()),
           "files": {f: sha((HERE / f).read_bytes()) for f in ("run_matched_alternatives.py", "run.sh", "PROTOCOL.md")}}
    return roster, jobs, pin


def produce(roster, jobs, identity, ledger):
    plans = trial.stage(SUPPLY, jobs, identity, ledger)
    outputs, drafts = {}, {}
    for key, receipt in plans.items():
        uid, arm = key
        row = outputs.setdefault(uid, {})[arm] = {"supply_status": receipt["status"], "supply_receipt": receipt,
                "ideas": None, "answer": None, "status": receipt["status"]}
        if receipt["status"] != "OK":
            continue
        try:
            row["ideas"] = parse_ideas(receipt["answer"])
        except (TypeError, ValueError, KeyError) as error:
            row.update(status="SUPPLY_CONTRACT_FALLBACK", answer=roster[uid]["answer"], error=str(error))
            continue
        packet = {"task_and_history": roster[uid]["task"], "reference_answer": roster[uid]["answer"],
                  "candidate_ideas": row["ideas"]}
        drafts[key] = text_request(REALIZE, packet, "qwen3.8-flash", 8192)
    trial.probe.freeze(RUN / "ACTOR_REQUESTS_PRIVATE.json", {"/".join(k): w for k, w in drafts.items()})
    for (uid, arm), result in trial.stage(DRAFT, drafts, identity, ledger).items():
        row = outputs[uid][arm]
        row.update(status=result["status"], actor_receipt=result)
        if result["status"] != "OK":
            continue
        try:
            answer = decode(result["answer"])
            if answer == {"mode": "KEEP"}:
                row.update(answer=roster[uid]["answer"], status="KEEP")
            elif set(answer) == {"mode", "answer"} and answer["mode"] == "ANSWER" and isinstance(
                answer["answer"], str) and answer["answer"].strip():
                full = answer["answer"]
                row.update(answer=full, status="KEEP" if full == roster[uid]["answer"] else "DRAFTED")
            else:
                raise ValueError("Unusable final answer envelope")
        except (TypeError, ValueError, KeyError) as error:
            row.update(status="DRAFT_CONTRACT_FALLBACK", answer=roster[uid]["answer"], error=str(error))
    trial.probe.freeze(RUN / "LOCKED_ANSWERS_PRIVATE.json", outputs)
    return outputs


def measure(roster, outputs, identity, ledger):
    prior = grading.prior
    plan = prior.read(prior.formal.OUT / "PLAN.json")
    cases = prior.author_cases(plan)
    scored = {uid: dict.fromkeys(ARMS) for uid in roster}
    grades, ref_lengths = {}, {}
    single_uid, = [uid for uid, card in roster.items() if card["track"] == "single"]
    card = roster[single_uid]
    key = card["native_key"]
    result = trial.measure({key: card["native_input"]}, {key: card["native_binding"]},
                           {key: outputs[single_uid]}, identity, ledger)
    for arm in ARMS:
        scored[single_uid][arm] = result[key][arm]["score"]
    for uid, row in roster.items():
        if row["track"] == "single":
            continue
        case = cases[uid]
        source = prior.read(prior.formal.ROOT / case["evaluation_path"])
        if digest(source) != case["evaluation_hash"] or case["independent_confirmation"]:
            raise ValueError("Native grader source drift or inadmissible split")
        ref_lengths[uid] = len(source["intent_type"])
        for arm in ARMS:
            answer = outputs[uid][arm]["answer"]
            if answer is None:
                continue
            if answer == row["answer"]:
                scored[uid][arm] = row["grade"]
            else:
                grades[uid, arm] = grading.grade_request(plan, case, answer)
    receipts = trial.stage(NATIVE, grades, identity, ledger)
    parsed = {uid: {} for uid in roster}
    for (uid, arm), reply in receipts.items():
        cell = grading.parse_grade(reply, reply["answer"], ref_lengths[uid])
        parsed[uid][arm] = cell
        if cell["fields"].get("match"):
            scored[uid][arm] = cell["fields"]
    trial.probe.freeze(RUN / "GRADES_PRIVATE.json", parsed)
    return scored


def summarize(roster, outputs, scores, ledger):
    rows = {}
    for uid, card in roster.items():
        rows[uid] = {"track": card["track"], "stratum": card["stratum"], "source_group": sha(card["source_group"]),
                     "grade": {"BASE": card["grade"], **scores[uid]}, "base_flags": card["flags"],
                     "references": card["references"],
                     "status": {arm: outputs[uid][arm]["status"] for arm in ARMS},
                     "valid_ideas": {arm: outputs[uid][arm]["ideas"] is not None for arm in ARMS},
                     "answer_sha256": {arm: sha(outputs[uid][arm]["answer"]) if outputs[uid][arm]["answer"] else None for arm in ARMS}}
    return {"rows": rows, "cost": {"requests": len(ledger), "stages": Counter(r["unit"]["stage"] for r in ledger),
                 "statuses": Counter(r["status"] for r in ledger),
                 "reported_tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                 "unknown_usage": sum((r["usage"] or {}).get("total_tokens") is None for r in ledger),
                 "retries": sum(r.get("automatic_retries", 0) for r in ledger)}}


def main(command):
    if command == "report":
        print(json.dumps(trial.read(RUN / "SUMMARY.json"), ensure_ascii=False, indent=2))
        return
    roster, jobs, pin = freeze_plan()
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
            raise ValueError("Actor service identity changed")
        identity = {"experiment_sha256": sha(pin), "service_reference_sha256": active}
        trial.probe.freeze(RUN / "EXECUTION.json", identity)
        if not (RUN / "SUMMARY.json").is_file():
            ledger = []
            outputs = produce(roster, jobs, identity, ledger)
            scores = measure(roster, outputs, identity, ledger)
            trial.probe.freeze(RUN / "LEDGER.json", ledger)
            trial.probe.freeze(RUN / "SUMMARY.json", summarize(roster, outputs, scores, ledger))
        print(json.dumps(trial.read(RUN / "SUMMARY.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "run", "report"))
    main(parser.parse_args().command)
