"""Compare one shared defect diagnosis followed by free or bounded answer repair."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from experiment import RUN as VETO
from extend import archived, merge_stage
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from protected import FORMATS, LOCATE, REVISE, apply, default_answer, locate
from qamc.common import parse_object, sha
from qamc.contextual_match.development import text_request
from qamc.pa.rpeval_scoring import parse_score
from run_bridge import MODEL, ROOT, engine, prepare, probe, read, score_wire
from run_reward import PEERS, totals
from selection import METHODS
from settle_reward import verify_inputs

HERE = Path(__file__).resolve().parent
RUN = VETO.with_name(HERE.name)
ARMS = ("FREE", "PATCH")
LOCATE_STAGE, REPAIR_STAGE, SCORE_STAGE = "Locate", "Repair", "SingleDetailJudge"
CAPS = {LOCATE_STAGE: 24, REPAIR_STAGE: 48, SCORE_STAGE: 48}


def assign():
    original, binding = verify_inputs()
    veto = read(VETO / "LOCKED_CHOICES.json")
    packets = {key: {**packet, "default_id": next(cid for cid, method in binding[key]["order"].items()
                                                if method == METHODS[0])}
               for key, packet in original.items()}
    jobs = {(key, "LOCATE"): text_request(LOCATE, packet, MODEL, 8192) for key, packet in packets.items()}
    for key, choice in veto.items():
        if choice["choice"] is not None and choice["choice"] not in packets[key]["candidates"]:
            raise ValueError("The witnessed selection does not bind to a frozen candidate")
    pin = {"case_count": len(packets), "packets_sha256": sha(packets), "binding_sha256": sha(binding),
           "locate_wires_sha256": sha(list(jobs.values())), "veto_sha256": sha(veto), "caps": CAPS,
           "code_sha256": {name: sha((HERE / name).read_bytes()) for name in
                           ("repair_trial.py", "protected.py", "PROTOCOL.md", "run.sh")}}
    if len(packets) != 24 or set(packets) != set(veto):
        raise ValueError("Unexpected case inventory")
    return packets, binding, veto, jobs, pin


def stage(name, jobs, identity, ledger):
    unique, aliases = {}, {}
    for key, wire in jobs.items():
        validate_public_request(wire)
        aliases[key] = unique.setdefault(sha(wire), key)
    canonical = {key: jobs[key] for key in unique.values()}
    cache, _ = archived(canonical, ROOT)
    outside = {key: value for key, value in cache.items() if RUN.name not in Path(value["archive"]).parts}
    returned = merge_stage(name, canonical, outside, identity, ledger)
    if set(returned) != set(canonical):
        raise ValueError("Incomplete stage receipt inventory")
    for key, result in returned.items():
        if result["request_sha256"] != sha(jobs[key]):
            raise ValueError("Stage receipt does not bind to its input")
    return {key: returned[alias] for key, alias in aliases.items()}


def generate(packets, jobs, identity, ledger):
    diagnoses, revisions = {}, {}
    for (key, _), result in stage(LOCATE_STAGE, jobs, identity, ledger).items():
        diagnosis = None
        state = result["status"]
        error = None
        if state == "OK":
            try:
                diagnosis = locate(result["answer"], packets[key])
                state = diagnosis["mode"]
            except (ValueError, TypeError, KeyError) as exc:
                state, error = "INVALID_LOCATOR", str(exc)
        diagnoses[key] = {"state": state, "error": error, "diagnosis": diagnosis,
                          "receipt": result}
        if state == "ACT":
            payload = {**packets[key], "proposed_diagnosis": diagnosis}
            for arm in ARMS:
                revisions[key, arm] = text_request(REVISE + "\n\n" + FORMATS[arm], payload, MODEL, 8192)
    probe.freeze(RUN / "DIAGNOSES.json", diagnoses)
    revisions = dict(sorted(revisions.items(), key=lambda row: sha(["protected-repair-v2", *row[0]])))
    probe.freeze(RUN / "REVISION_WIRES.json", {f"{key}/{arm}": sha(wire) for (key, arm), wire in revisions.items()})
    returned = stage(REPAIR_STAGE, revisions, identity, ledger)
    delivered = {}
    for key, record in diagnoses.items():
        packet = packets[key]
        original = default_answer(packet)
        delivered[key] = {}
        for arm in ARMS:
            receipt = returned.get((key, arm))
            error, final = None, None
            route = record["state"]
            if route in ("KEEP", "INVALID_LOCATOR"):
                final = original
            elif receipt:
                route = receipt["status"]
                if route == "OK":
                    try:
                        final = apply(receipt["answer"], packet, record["diagnosis"], arm)
                        route = "KEEP" if final == original else "EDITED"
                    except (ValueError, TypeError, KeyError) as exc:
                        route, final, error = "INVALID_REVISION", original, str(exc)
            delivered[key][arm] = {"status": route, "answer": final, "error": error, "receipt": receipt}
    probe.freeze(RUN / "LOCKED_ANSWERS.json", delivered)
    return delivered


def measure(packets, binding, delivered, identity, ledger):
    # Annotation and score assets are available only after the complete output inventory is frozen.
    _, _, refs, rubrics, archive, _, _, _ = prepare()
    rows, judge_wires = {}, {}
    for key, packet in packets.items():
        item = binding[key]
        for arm in ARMS:
            entry = delivered[key][arm]
            answer = entry["answer"]
            score, origin = None, "DELIVERY_MISSING"
            if answer is not None:
                exact = [method for cid, method in item["order"].items() if packet["candidates"][cid] == answer]
                if exact:
                    score = archive[item["uid"]][exact[0]]
                    if any(score != archive[item["uid"]][method] for method in exact):
                        raise ValueError("Exact archived answer has inconsistent grades")
                    origin = "ARCHIVED_EXACT"
                else:
                    judge_wires[key, arm] = score_wire(rubrics, refs[item["uid"]], answer)
                    origin = "AWAITING_SCORE"
            rows[key, arm] = {"answer_sha256": sha(answer) if answer is not None else None, "score": score,
                              "status": entry["status"], "score_status": origin, "judge": None}
    for (key, arm), response in stage(SCORE_STAGE, judge_wires, identity, ledger).items():
        row = rows[key, arm]
        row.update(judge=response, score_status=response["status"])
        if response["status"] == "OK":
            try:
                row["score"] = parse_score(parse_object(response["answer"]))
            except (ValueError, TypeError, KeyError):
                row["score_status"] = "INVALID_SCORE"
    graded = {key: {arm: rows[key, arm] for arm in ARMS} for key in packets}
    probe.freeze(RUN / "GRADED_ANSWERS.json", graded)
    return graded


def summarize(packets, binding, veto, graded, ledger):
    _, _, _, _, archive, _, _, _ = prepare()
    bridge = read(VETO.with_name("rpe_single_endpoint_bridge_v1") / "RESULTS.json")
    groups = {row["uid"]: row for row in bridge["rows"]}
    labels = {key: groups[item["uid"]]["label"] for key, item in binding.items()}
    historical = [key for key, item in binding.items() if groups[item["uid"]]["scores"]["IPE_C"] is not None]
    if len(historical) != 22:
        raise ValueError("Historical denominator changed")
    grades = {arm: {} for arm in (*PEERS, "IPE-C", "V1", *ARMS)}
    for key, item in binding.items():
        uid, order = item["uid"], item["order"]
        for method, peer in zip(METHODS, PEERS, strict=True):
            grades[peer][key] = archive[uid][method]
        grades["V1"][key] = archive[uid][order[veto[key]["choice"] or packets[key]["default_id"]]]
        grades["IPE-C"][key] = groups[uid]["scores"]["IPE_C"]
        for arm in ARMS:
            grades[arm][key] = graded[key][arm]["score"]

    def available(keys):
        return {name: totals([key for key in keys if table[key] is not None], table)
                for name, table in grades.items()}

    common = [key for key in historical if all(grades[arm][key] is not None for arm in ARMS)]
    all_common = [key for key in packets if all(grades[arm][key] is not None for arm in ARMS)]
    paired = {}
    for arm in ARMS:
        paired[arm] = {}
        for other in (*PEERS, "IPE-C", "V1", *(x for x in ARMS if x != arm)):
            diffs = [grades[arm][key]["matched"] - grades[other][key]["matched"] for key in common]
            paired[arm][other] = {"wins": diffs.count(1), "losses": diffs.count(-1), "ties": diffs.count(0)}
    all_rows = {key: {**{arm: graded[key][arm] for arm in ARMS}, "historical": key in historical,
                      "label": labels[key], "grade": {name: scores[key] for name, scores in grades.items()}}
                for key in packets}
    usage = [(row.get("usage") or {}).get("total_tokens") for row in ledger]
    report = {"assigned": len(packets), "historical_assigned": len(historical), "historical_common": len(common),
              "all_common": len(all_common), "historical_available_scores": available(historical),
              "historical_matched_scores": available(common), "all_available_scores": available(list(packets)),
              "all_matched_scores": available(all_common), "historical_paired": paired,
              "by_author_label": {label: available([key for key in common if labels[key] == label])
                                  for label in ("A", "B", "C")},
              "disposition": {arm: Counter(graded[key][arm]["status"] for key in packets) for arm in ARMS},
              "score_status": {arm: Counter(graded[key][arm]["score_status"] for key in packets) for arm in ARMS},
              "requests": {"count": len(ledger), "usage_unknown": usage.count(None),
                           "reported_tokens": sum(value or 0 for value in usage),
                           "by_stage": Counter(row["unit"]["stage"] for row in ledger),
                           "by_status": Counter(row["status"] for row in ledger),
                           "automatic_retries": sum(row.get("automatic_retries", 0) for row in ledger)}}
    probe.freeze(RUN / "SCORED_ROWS.json", all_rows)
    probe.freeze(RUN / "SUMMARY.json", report)
    return report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    packets, binding, veto, jobs, pin = assign()
    RUN.mkdir(parents=True, exist_ok=True)
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = CAPS
    with probe.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if read(RUN / "FROZEN.json") != pin:
            raise ValueError("The public-input or code freeze differs")
        if action == "run" and not (RUN / "SUMMARY.json").is_file():
            identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
            if identity["service_reference_sha256"] != read(VETO / "EXECUTION.json")["service_reference_sha256"]:
                raise ValueError("New and historical methods use different service configurations")
            probe.freeze(RUN / "EXECUTION.json", identity)
            ledger = []
            delivered = generate(packets, jobs, identity, ledger)
            graded = measure(packets, binding, delivered, identity, ledger)
            if len(ledger) > sum(CAPS.values()):
                raise ValueError("Physical request cap exceeded")
            probe.freeze(RUN / "LEDGER.json", ledger)
        else:
            graded = read(RUN / "GRADED_ANSWERS.json")
            ledger = read(RUN / "LEDGER.json")
        print(json.dumps(summarize(packets, binding, veto, graded, ledger), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
