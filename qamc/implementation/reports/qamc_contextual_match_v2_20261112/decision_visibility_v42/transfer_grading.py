"""Build cross-benchmark Judge requests without coupling labels to V42 generation."""
from collections import Counter, defaultdict
import json
import re

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha
from qamc.pa.core import digest

from score_persist_rp import EVALUATOR, OUT as PERSIST_RP, prepare as persist_plan
from transfer_replay import bench, development, persist, read, run as transfer_replay


def bench_judge(case, query, answer, protocol):
    reference = read(bench.ROOT / case["evaluation_path"])
    if digest(reference) != case["evaluation_hash"]:
        raise ValueError("BenchPreS evaluation reference changed")
    result = {}
    for stage, system, payload in bench.score.initial_requests(bench.ROOT, "benchpres", reference, query, answer):
        config = protocol["stages"][stage]
        wire = bench.text_request(system, payload, protocol["model"], config["max_tokens"])
        validate_public_request(wire)
        if wire["temperature"] != config["temperature"]:
            raise ValueError("BenchPreS grading temperature changed")
        result[stage] = wire
    return result, reference


def persist_judge(category, task, answer, protocol, rubrics, formatters):
    config = protocol["stages"][persist.STAGE]
    payload = formatters["build_judge_prompt"]([memory.text for memory in task.memories], task.query, answer)
    wire = persist.author.ext.text_request(rubrics[category], payload, protocol["model"], config["max_tokens"])
    validate_public_request(wire)
    if wire["temperature"] != config["temperature"]:
        raise ValueError("PersistBench grading temperature changed")
    return wire


def bench_anchors():
    plan = read(bench.OUT / "PLAN.json")
    cases = {c["uid"]: c for c in plan["cases"] if c["independent_confirmation"] is False}
    if len(cases) != 48 or len({c["analysis_group_id"] for c in cases.values()}) != 10:
        raise ValueError("BenchPreS exposed development panel changed")
    protocol = plan["protocols"]["grading"]
    saved = [*read(bench.OUT / "RESULT_ROWS.json"), *(row for row in read(development.OUT / "RESULT_ROWS.json")
               if row["uid"] in cases and row["method"] in development.METHODS)]
    originals = read(development.OUT / "INHERITANCE_WITNESSES.json")
    inherited = {development.RUN.with_name(bench.ROOT.joinpath(row["file"]).parent.name)
                 for row in originals if row["uid"] in cases}
    physical, verified, rows = defaultdict(set), Counter(), []
    for folder in (bench.RUN, development.RUN, *sorted(inherited)):
        for path in (folder / "grading" / "outputs").glob("*.json"):
            receipt = read(path)
            if receipt["status"] == "OK" and receipt["unit"]["stage"] in bench.JUDGES:
                physical[receipt["request_sha256"]].add(receipt["response"]["answer"])
    for row in saved:
        uid, method = row["uid"], row["method"]
        values = row.get("raw_scores", {})
        if values:
            requests, ref = bench_judge(cases[uid], development.task_for(cases[uid]).query, row["answer"], protocol)
            for stage, raw in values.items():
                if raw not in physical.get(sha(requests[stage]), ()):
                    raise ValueError(f"Unverifiable saved BenchPreS Judge response: {uid}/{method}/{stage}")
                verified[method] += 1
            if row.get("score") is not None and bench.score.grade(bench.ROOT, "benchpres", ref, values) != row["score"]:
                raise ValueError("BenchPreS score no longer parses to its archived value")
        if row.get("score") is not None and not values:
            raise ValueError("BenchPreS result has no corresponding saved responses")
        rows.append({"uid": uid, "method": method, "score": row.get("score")})
    return cases, protocol, rows, verified


def bench_pair(left, right, cases, scores):
    common = [uid for uid in cases if (uid, left) in scores and (uid, right) in scores]
    result = {}
    for method in (left, right):
        vals = [scores[uid, method] for uid in common]
        decisions = [d for row in vals for d in row["decisions"]]
        nonbold = [d for d in decisions if d["appropriate"] and not re.search(r"\bbold\s+text\b", d["preference"], re.I)]
        result[method] = {
            "aar": [sum(v["aar_numerator"] for v in vals), sum(v["aar_denominator"] for v in vals)],
            "mr": [sum(v["mr_numerator"] for v in vals), sum(v["mr_denominator"] for v in vals)],
            "nonbold_aar": [sum(d["label"] == "follow" for d in nonbold), len(nonbold)],
            "completeness": sum(v["task_completeness"] for v in vals) / len(common) if common else None,
        }
    return {"common_roots": len(common), "profiles": len({cases[uid]["analysis_group_id"] for uid in common}),
            "scores": result}


def analyze():
    transfer = transfer_replay()
    bcases, protocol, rows, verified = bench_anchors()
    scores = {(row["uid"], row["method"]): row["score"] for row in rows if row["score"] is not None}
    methods = (*development.METHODS, bench.METHOD)
    observed = Counter(method for uid, method in scores)
    summary = {m: observed[m] for m in methods}
    pairs = {f"{left}__{right}": bench_pair(left, right, bcases, scores)
             for idx, left in enumerate(methods) for right in methods[idx + 1:]}
    pb = read(PERSIST_RP / "FROZEN.json")
    if len(pb["targets"]) != 58 or pb != persist_plan():
        raise ValueError("PersistBench matched rating freeze changed")
    results = read(PERSIST_RP / "RESULTS.json")
    if results["physical"] != 58 or read(PERSIST_RP / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Require completed PersistBench matched Judge receipts")
    all_uids = {row["uid"] for row in results["rows"]}
    cases = {c["uid"]: c for c in read(development.OUT / "PLAN.json")["cases"] if c["uid"] in all_uids}
    answers = {row["uid"]: row["answer"] for row in read(development.OUT / "RESULT_ROWS.json")
               if row["method"] == "RPR_PAPER_FULL" and row["uid"] in cases}
    _, rubrics, fmt = EVALUATOR.upstream()
    proto = read(persist.AUTHOR_OUT / "PLAN.json")["protocols"]["gpt41"]
    for row in results["rows"]:
        uid = row["uid"]
        wire = persist_judge(row["category"], development.task_for(cases[uid]), answers[uid], proto, rubrics, fmt)
        if sha(wire) != row["RP_gpt41_request_sha256"] or sha(wire) != row["receipt"]["request_sha256"]:
            raise ValueError("PersistBench Judge request does not match saved receipt")
        if row["score"] is not None and EVALUATOR.score(row["category"], row["raw_score"]) != row["score"]:
            raise ValueError("PersistBench native result changed")
    return {
        "benchpres": {"fixed_roots": len(bcases), "grading_model": protocol["model"], "verified_judgments": dict(verified),
                     "valid_by_method": summary, "pairs": pairs,
                     "compatible_RP_Actor": transfer["benchpres"]["compatible_RP_Actor"]},
        "persistbench": {"compatible_RP_Actor": len(pb["targets"]), "grading_model": "gpt-4.1",
                         "valid_RP_scores": results["valid_native"],
                         "comparisons": results["comparisons"]},
        "new_model_calls": 0, "unseen_sources_read": 0,
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
