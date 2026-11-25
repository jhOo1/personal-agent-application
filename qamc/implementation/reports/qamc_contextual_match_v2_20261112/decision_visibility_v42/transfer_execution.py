"""Use the V42 generation contract with the matched BenchPreS and PersistBench judges."""
from collections import Counter, defaultdict
import json

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha

from contract import actor_request, compile_scope, selection_request
from preflight import public_roots
from run_visibility_v42 import ACTOR, ARMS, SELECTOR
from transfer_grading import EVALUATOR, PERSIST_RP, bench, bench_anchors, bench_judge, bench_pair, development, persist
from transfer_grading import persist_judge, read
from transfer_replay import C5, GATE, PERSIST_CONTROLS, RP


def development_roots(benchmark):
    panel = [root for name, root in public_roots() if name == benchmark]
    expected = {"BenchPreS": 48, "PersistBench": 58}
    if len(panel) != expected[benchmark] or len({r["uid"] for r in panel}) != len(panel):
        raise ValueError("Exposed transfer panel changed")
    return panel


def checked_dispatch(dispatch, jobs):
    for payload in jobs.values():
        validate_public_request(payload)
    received = dispatch(jobs)
    if jobs.keys() != received.keys():
        raise ValueError("Dispatch must report a status for every requested operation")
    for key, wire in jobs.items():
        response = received[key]
        if response["request_sha256"] != sha(wire):
            raise ValueError("Dispatch returned a result for a different request")
        if response["status"] == "OK" and not isinstance(response.get("answer"), str):
            raise ValueError("An acknowledged response must have answer text")
    return received


def generate(panel, dispatch):
    methods = ("DIRECT", "SCOPED")
    tasks = {root["uid"]: root for root in panel}
    selected = checked_dispatch(dispatch, {
        (uid, method, SELECTOR): selection_request(root, method)
        for uid, root in tasks.items() for method in methods
    })
    selection, rejects = {}, {}
    for (uid, method, _), response in selected.items():
        if response["status"] != "OK":
            rejects[uid, method] = response["status"]
            continue
        try:
            selection[uid, method] = compile_scope(tasks[uid], response["answer"])
        except (ValueError, KeyError, TypeError):
            rejects[uid, method] = "INVALID_SELECTOR_CONTRACT"
    jobs = {(uid, arm, ACTOR): actor_request(root, selection[uid, method], masked=masked)
            for uid, root in tasks.items() for arm, (method, masked) in ARMS.items() if (uid, method) in selection}
    actors = checked_dispatch(dispatch, jobs)
    answers = []
    for uid in tasks:
        for arm, (method, _) in ARMS.items():
            key = (uid, arm, ACTOR)
            row = {"uid": uid, "method": arm, "score": None}
            if key not in actors:
                row.update(actor_status="NO_VALID_SELECTOR", selector_status=rejects[uid, method])
            else:
                wire = jobs[key]
                read_view = json.loads(wire["messages"][1]["content"])
                value = actors[key]
                row.update(actor_status=value["status"], actor_sha256=sha(wire), selector_status="OK",
                           visible_ids=[source["memory_id"] for source in read_view["source_evidence"]])
                if value["status"] == "OK":
                    row["answer"] = value["answer"]
            answers.append(row)
    return answers


def bench_context():
    cases, protocol, controls, _ = bench_anchors()
    return cases, protocol, controls


def persist_context():
    author = read(persist.AUTHOR_OUT / "PLAN.json")
    cases = {c["uid"]: c for c in author["cases"] if c["role"] == "DEV"}
    allowed = {r["uid"] for r in read(PERSIST_RP / "FROZEN.json")["targets"]}
    cases = {uid: case for uid, case in cases.items() if uid in allowed}
    archived_authors = [row for path in sorted((persist.AUTHOR_OUT / "waves").glob("*.json"))
                        for row in read(path)["rows"] if row["uid"] in allowed and row["method"] in PERSIST_CONTROLS]
    internal = [row for row in read(persist.OUT / "RESULTS.json")["rows"]
                if row["uid"] in allowed and row["method"] in (C5, GATE)]
    rp = [{**row, "method": RP} for row in read(PERSIST_RP / "RESULTS.json")["rows"]]
    controls = [{"uid": row["uid"], "method": row["method"], "score": row["score"]}
                for row in (*archived_authors, *internal, *rp)]
    return cases, author["protocols"]["gpt41"], controls


def grading_jobs(benchmark, answers, cases, protocol):
    jobs, refs = {}, {}
    _, rubrics, fmt = EVALUATOR.upstream() if benchmark == "PersistBench" else (None, None, None)
    for row in answers:
        if row["actor_status"] != "OK" or not row.get("answer"):
            continue
        uid, method = row["uid"], row["method"]
        case = cases[uid]
        task = development.task_for(case)
        if benchmark == "BenchPreS":
            requests, refs[uid] = bench_judge(case, task.query, row["answer"], protocol)
        else:
            category = case["category"]
            requests = {persist.STAGE: persist_judge(category, task, row["answer"], protocol, rubrics, fmt)}
        jobs.update({(uid, method, field): wire for field, wire in requests.items()})
    return jobs, refs


def grade(benchmark, answers, cases, protocol, dispatch):
    jobs, refs = grading_jobs(benchmark, answers, cases, protocol)
    judged = checked_dispatch(dispatch, jobs)
    by_answer = defaultdict(dict)
    for (uid, method, stage), response in judged.items():
        by_answer[uid, method][stage] = response
    for row in answers:
        uid = row["uid"]
        values = by_answer[uid, row["method"]]
        row["judge_statuses"] = {stage: x["status"] for stage, x in values.items()}
        row["raw_scores"] = {stage: x["answer"] for stage, x in values.items() if x["status"] == "OK"}
        if not values or len(row["raw_scores"]) != len(values):
            continue
        try:
            if benchmark == "BenchPreS":
                row["score"] = bench.score.grade(bench.ROOT, "benchpres", refs[uid], row["raw_scores"])
            else:
                row["score"] = EVALUATOR.score(cases[uid]["category"], row["raw_scores"][persist.STAGE])
        except (ValueError, KeyError, TypeError) as error:
            row["score_error"] = str(error)
    return answers


def persist_pair(left, right, cases, scores):
    metrics = {}
    for category in sorted({case["category"] for case in cases.values()}):
        same = [uid for uid, case in cases.items() if case["category"] == category
                and (uid, left) in scores and (uid, right) in scores]
        metrics[category] = {"common": len(same)}
        for flag in ("failure_release", "failure_strict_utility"):
            values = [(scores[uid, left][flag], scores[uid, right][flag]) for uid in same]
            metrics[category][flag] = {left: sum(a for a, _ in values), right: sum(b for _, b in values),
                                       "left_only_failures": sum(a and not b for a, b in values),
                                       "right_only_failures": sum(b and not a for a, b in values)}
    return metrics


def summarize(benchmark, rows, cases, controls):
    cells = {(row["uid"], row["method"]): row["score"] for row in (*rows, *controls) if row["score"] is not None}
    comparisons = [("DIRECT_MASKED", "SCOPED_MASKED"), ("SCOPED_FULL", "SCOPED_MASKED")]
    comparisons.extend((method, "SCOPED_MASKED") for method in sorted({row["method"] for row in controls}))
    summarize_pair = bench_pair if benchmark == "BenchPreS" else persist_pair
    return {
        "valid_native_by_arm": Counter(row["method"] for row in rows if row["score"] is not None),
        "actor_statuses": Counter(row["method"] + "/" + row["actor_status"] for row in rows),
        "paired": {f"{a}__{b}": summarize_pair(a, b, cases, cells) for a, b in comparisons},
    }


def evaluate(benchmark, dispatch, *, panel=None):
    exposed = development_roots(benchmark)
    authorized = {root["uid"]: root for root in exposed}
    panel = exposed if panel is None else panel
    if len({root["uid"] for root in panel}) != len(panel) or any(
        authorized.get(root["uid"]) != root for root in panel
    ):
        raise ValueError("Only exact exposed development inputs can enter dispatch")
    answers = generate(panel, dispatch)
    cases, protocol, controls = bench_context() if benchmark == "BenchPreS" else persist_context()
    ids = {row["uid"] for row in panel}
    cases = {uid: case for uid, case in cases.items() if uid in ids}
    if cases.keys() != ids:
        raise ValueError("Cross-benchmark pipeline can only score exposed and authorized development tasks")
    controls = [row for row in controls if row["uid"] in ids]
    scored = grade(benchmark, answers, cases, protocol, dispatch)
    return scored, summarize(benchmark, scored, cases, controls)
