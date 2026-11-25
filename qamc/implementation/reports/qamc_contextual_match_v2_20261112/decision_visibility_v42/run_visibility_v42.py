"""Run V42 on the exposed RPEval panel with exact stage reuse."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import parse_object, sha
from qamc.pa.core import digest

import run_v41 as prior
from analyze import metric_pairs, paired
from contract import METHOD_PROMPTS, actor_request, compile_scope, selection_request
from score_task_only import OUT as TASK_ONLY, saved_drafts

HERE = Path(__file__).resolve().parent
OUT = HERE.with_name("decision_visibility_rpeval_v42")
RUN = prior.RUN.with_name(OUT.name)
SELECTOR, ACTOR, JUDGE = "Selector", "Actor", prior.NATIVE
PROBE, read = prior.probe, prior.read
ARMS = {"DIRECT_MASKED": ("DIRECT", True), "SCOPED_FULL": ("SCOPED", False),
        "SCOPED_MASKED": ("SCOPED", True)}
COMPARISONS = (("DIRECT_MASKED", "SCOPED_MASKED"), ("SCOPED_FULL", "SCOPED_MASKED"),
               (prior.GATE, "SCOPED_MASKED"), (prior.RP, "SCOPED_MASKED"))
CAP = {SELECTOR: 466, ACTOR: 699, JUDGE: 699}


def prepare():
    saved = read(prior.OUT / "FROZEN.json")
    references = prior.author_cases(read(prior.formal.OUT / "PLAN.json"))
    ids = {root["uid"] for root in saved["roots"]}
    if len(ids) != 233 or not ids <= references.keys():
        raise ValueError("V42 must use the same 233 exposed roots")
    paths = (Path(__file__), HERE / "contract.py", HERE / "PROTOCOL.md", prior.OUT / "FROZEN.json",
             prior.OUT / "TERMINAL.json", TASK_ONLY / "FROZEN.json", TASK_ONLY / "RESULTS.json")
    return {"parents": {path.name + "/" + path.parent.name: sha(path.read_bytes()) for path in paths},
            "waves": saved["waves"], "cap": CAP, "arms": {k: list(v) for k, v in ARMS.items()},
            "service_reference_sha256": saved["service_reference_sha256"],
            "independent_confirmation": False}


def old_receipts(archive):
    drafts = {digest: [entry["record"], entry["answer"]] for digest, entry in saved_drafts(archive).items()
              if entry["record"] is not None}
    outcomes = read(TASK_ONLY / "RESULTS.json")
    if outcomes["state"]["state"] != "COMPLETE":
        raise ValueError("Task-only scoring is not settled")
    scores = {}
    for phase, manifest in read(TASK_ONLY / "FROZEN.json")["waves"].items():
        PROBE.OUT = TASK_ONLY / phase
        PROBE.RUN = prior.RUN.with_name(TASK_ONLY.name) / phase
        if read(PROBE.OUT / (JUDGE + "_MANIFEST.json")) != manifest:
            raise ValueError("Inherited Judge manifest changed")
        for record, raw in PROBE.stage_receipts(JUDGE).values():
            scores[record["request_sha256"]] = [record, raw]
    assert set(scores) == {row["request_sha256"] for row in outcomes["ledger"]}
    return {SELECTOR: {}, ACTOR: drafts, JUDGE: scores}


def manifest(wave, name, jobs):
    model = "gpt-4.1" if name == JUDGE else "qwen3.8-flash"
    cap = 4096 if name == ACTOR else 8192
    protocol = {"experiment": f"{OUT.name}/{wave}", "model": model, "concurrency": 8,
                "spacing_seconds": 3.2, "stages": {name: {"max_tokens": cap, "temperature": 0}},
                "automatic_retries": 0}
    items = []
    for uid, arm, wire in jobs:
        validate_public_request(wire)
        if (wire["model"], wire["max_tokens"], wire["temperature"]) != (model, cap, 0):
            raise ValueError("Sampling settings differ from the frozen protocol")
        items.append({"unit": {"stage": name, "root_id": uid, "method": arm, "replicate": 0,
                               "protocol_sha256": sha(protocol)}, "request": wire})
    return {"protocol": protocol, "units": items}


def execute_stage(plan, wave, name, jobs, inherited, live):
    unique, lookup = {}, {}
    for uid, arm, wire in jobs:
        digest = sha(wire)
        lookup[uid, arm] = digest
        if digest not in inherited:
            unique.setdefault(digest, (uid, arm, wire))
    frozen = manifest(wave, name, unique.values())
    PROBE.freeze(PROBE.OUT / (name + "_MANIFEST.json"), frozen)
    if live:
        prior.dispatch(plan, name, frozen)
    returned = PROBE.stage_receipts(name)
    local = {digest: list(returned[uid, arm]) for digest, (uid, arm, _) in unique.items()}
    if any(record is None for record, _ in local.values()):
        raise RuntimeError(f"{name}: allocation has undispatched jobs")
    PROBE.freeze(PROBE.OUT / (name + "_EXACT.json"), local)
    PROBE.freeze(PROBE.OUT / (name + "_REUSE.json"), [dict(uid=uid, arm=arm, sha256=digest)
                 for (uid, arm), digest in lookup.items() if digest in inherited or unique[digest][:2] != (uid, arm)])
    inherited.update(local)
    return {key: inherited[digest] for key, digest in lookup.items()}


def status(record):
    return record["status"] if record is not None else "UNISSUED"


def predict(plan, wave, roots, cache, live):
    jobs = [(root["uid"], method, selection_request(root, method)) for root in roots for method in METHOD_PROMPTS]
    output = execute_stage(plan, wave, SELECTOR, jobs, cache, live)
    result = {}
    for root in roots:
        uid = root["uid"]
        for method in METHOD_PROMPTS:
            record, raw = output[uid, method]
            value = {"status": status(record), "scope": None, "raw": raw, "request_sha256": record["request_sha256"]}
            if raw is not None:
                try:
                    value["scope"] = compile_scope(root, raw)
                except (ValueError, KeyError, TypeError) as error:
                    value.update(status="INVALID_SELECTOR_CONTRACT", error=str(error))
            result[uid, method] = value
    return result


def make_scores(plan, wave, roots, answers, cache, live, cases, original):
    jobs, aliases = [], {}
    for root in roots:
        uid = root["uid"]
        anchored = {row["answer"]: method for method, row in root["archived"].items()
                    if row["raw_judge"] is not None}
        for arm in ARMS:
            answer = answers[uid, arm]["answer"]
            if not answer:
                continue
            if answer in anchored:
                aliases[uid, arm] = anchored[answer]
                continue
            cell = {"uid": uid, "method": prior.GATE, "actor_status": "OK", "answer": answer}
            item, = prior.formal.grading_jobs(original, [cases[uid]], [cell])
            jobs.append((uid, arm, item["request"]))
    received = execute_stage(plan, wave, JUDGE, jobs, cache, live)
    graded = {}
    for root in roots:
        uid = root["uid"]
        for arm in ARMS:
            old = aliases.get((uid, arm))
            if old is not None:
                saved = root["archived"][old]
                graded[uid, arm] = {"fields": saved["fields"], "raw": saved["raw_judge"], "reuse": old}
                continue
            record, raw = received.get((uid, arm), (None, None))
            entry = {"status": status(record), "fields": {}, "raw": raw,
                     "judge_sha256": record["request_sha256"] if record else None}
            if raw is not None:
                try:
                    entry["fields"], entry["invalid"] = PROBE.fields(parse_object(raw), len(root["original_sources"]), True)
                except (ValueError, KeyError, TypeError) as error:
                    entry.update(status="INVALID_JUDGE_OUTPUT", error=str(error))
            graded[uid, arm] = entry
    return graded


def evaluate(plan, wave, roots, cache, live, cases, original):
    predicted = predict(plan, wave, roots, cache[SELECTOR], live)
    jobs, views = [], {}
    for root in roots:
        uid = root["uid"]
        for arm, (method, masked) in ARMS.items():
            scope = predicted[uid, method]["scope"]
            if scope is None:
                continue
            wire = actor_request(root, scope, masked=masked)
            actual = json.loads(wire["messages"][1]["content"])
            views[uid, arm] = {"request_sha256": sha(wire), "visible_ids": [m["memory_id"] for m in actual["source_evidence"]]}
            jobs.append((uid, arm, wire))
    received = execute_stage(plan, wave, ACTOR, jobs, cache[ACTOR], live)
    answers = {}
    for root in roots:
        for arm in ARMS:
            key = root["uid"], arm
            if key not in received:
                answers[key] = {"status": "NO_VALID_SELECTOR", "answer": None}
            else:
                record, raw = received[key]
                answers[key] = {"status": status(record), "answer": raw, **views[key]}
    graded = make_scores(plan, wave, roots, answers, cache[JUDGE], live, cases, original)
    rows = []
    for root in roots:
        uid = root["uid"]
        case = cases[uid]
        gold = read(prior.formal.ROOT / case["evaluation_path"])
        if digest(gold) != case["evaluation_hash"]:
            raise ValueError("RPEval evaluation reference changed")
        rows.append({"uid": uid, "group": root["group"], "in_sensitivity": root["in_sensitivity"],
                     "labels": gold["intent_type"], "positions": len(root["original_sources"]),
                     "selected": {m: predicted[uid, m] for m in METHOD_PROMPTS},
                     "answers": {arm: answers[uid, arm] for arm in ARMS},
                     "native": {**{k: {"fields": row["fields"], "raw": row["raw_judge"]}
                                   for k, row in root["archived"].items()},
                                **{arm: graded[uid, arm] for arm in ARMS}}})
    ledger = [record for stage in CAP for record, _ in PROBE.stage_receipts(stage).values() if record]
    return {"rows": rows, "ledger": ledger}


def report(plan):
    rows, ledger = [], []
    for i, expected in enumerate(plan["waves"]):
        path = OUT / f"wave_{i:02d}" / "COMPLETED.json"
        if not path.exists():
            break
        saved = read(path)
        if [row["uid"] for row in saved["rows"]] != expected:
            raise ValueError("Completed root order changed")
        rows.extend(saved["rows"])
        ledger.extend(saved["ledger"])
    strata = {"all": rows, "all_A": [row for row in rows if set(row["labels"]) == {"A"}],
              "BC": [row for row in rows if set(row["labels"]) != {"A"}],
              "less_exposed": [row for row in rows if row["in_sensitivity"]],
              "additional": [row for row in rows if not row["in_sensitivity"]]}
    issuance = Counter(rec["unit"]["stage"] for rec in ledger)
    if any(issuance[stage] > cap for stage, cap in CAP.items()):
        raise ValueError("Physical cap exceeded")
    selections, visibility = defaultdict(Counter), defaultdict(Counter)
    archive = {root["uid"]: root for root in read(prior.OUT / "FROZEN.json")["roots"]}
    for row in rows:
        labels = dict(zip((value["memory_id"] for value in archive[row["uid"]]["original_sources"]),
                          row["labels"], strict=True))
        for name, value in row["selected"].items():
            selections[name][value["status"]] += 1
            if value["scope"] is not None:
                allowed = {x["memory_id"] for x in value["scope"]}
                levels = dict.fromkeys(labels, "A")
                for use in value["scope"]:
                    levels[use["memory_id"]] = max(levels[use["memory_id"]], use["level"])
                selections[name]["empty"] += not allowed
                selections[name]["all_A_empty"] += set(labels.values()) == {"A"} and not allowed
                selections[name]["BC_empty"] += set(labels.values()) != {"A"} and not allowed
                for mid, expected in labels.items():
                    selections[name][f"author_{expected}_predicted_{levels[mid]}"] += 1
                for label in "ABC":
                    selections[name][label + "_positions"] += list(labels.values()).count(label)
                    selections[name][label + "_selected"] += sum(labels[k] == label for k in allowed)
        for arm, value in row["answers"].items():
            visibility[arm][value["status"]] += 1
            for mid in value.get("visible_ids", []):
                visibility[arm][labels[mid] + "_visible"] += 1
    return {"completed": len(rows), "planned": sum(map(len, plan["waves"])), "issued": issuance,
            "physical_receipts": len(ledger), "usage_known_tokens": sum((x["usage"] or {}).get("total_tokens", 0) for x in ledger),
            "unknown_usage": sum("total_tokens" not in (x["usage"] or {}) for x in ledger),
            "transport_status": Counter(x["status"] for x in ledger), "selector_counts": selections,
            "actor_counts": visibility,
            "paired": {key: {f"{left}__{right}": {
                **paired(members, left, right), "metric_pairs": metric_pairs(members, left, right)}
                for left, right in COMPARISONS} for key, members in strata.items()}}


def run(plan, smoke):
    if prepare() != plan or PROBE.read_reference()[1] != plan["service_reference_sha256"]:
        raise ValueError("V42 freeze or service reference changed")
    archive = read(prior.OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in archive["roots"]}
    original = read(prior.formal.OUT / "PLAN.json")
    refs = prior.author_cases(original)
    cache = old_receipts(archive)
    state = OUT / "RUN_STATE.json"
    for i, uids in enumerate(plan["waves"][:1] if smoke else plan["waves"]):
        wave = f"wave_{i:02d}"
        PROBE.OUT, PROBE.RUN = OUT / wave, RUN / wave
        path = PROBE.OUT / "COMPLETED.json"
        PROBE.atomic_json(state, {"state": "RUNNING", "wave": wave})
        try:
            if path.exists():
                completed = read(path)
                for stage in CAP:
                    cache[stage].update(read(PROBE.OUT / (stage + "_EXACT.json")))
            else:
                completed = evaluate(plan, wave, [roots[uid] for uid in uids], cache, True, refs, original)
                PROBE.freeze(path, completed)
            if i == 0:
                valid = sum(all("match" in row["native"][arm]["fields"] for arm in ARMS) for row in completed["rows"])
                PROBE.freeze(OUT / "SMOKE.json", {"valid_three_arm_pairs": valid, "planned": len(uids)})
                if valid < 2:
                    raise RuntimeError("Fewer than two usable three-arm smoke outcomes")
        except (ValueError, RuntimeError, TypeError, KeyError) as error:
            PROBE.atomic_json(state, {"state": "STOPPED", "wave": wave, "error": str(error)})
            raise
        PROBE.atomic_json(OUT / "CHECKPOINT.json", report(plan))
    PROBE.atomic_json(state, {"state": "SMOKE_COMPLETE" if smoke else "COMPLETE", "waves": i + 1})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "smoke", "run", "report"))
    action = parser.parse_args().action
    path = OUT / "FROZEN.json"
    if action == "report":
        print(json.dumps(report(read(path)), ensure_ascii=False, indent=2))
    else:
        with PROBE.runner_lock(RUN / "runner.lock"):
            if action == "freeze":
                PROBE.freeze(path, prepare())
                print("Frozen 233 exposed roots, physical caps:", CAP)
            else:
                run(read(path), smoke=action == "smoke")
