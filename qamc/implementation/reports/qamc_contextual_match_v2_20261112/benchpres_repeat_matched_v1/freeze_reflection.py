"""Freeze fixed BenchPreS answers for independent, method-masked reflection review."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import hmac
import io
import json
from pathlib import Path
import secrets

from qamc.common import sha
from report_qamc_benchpres_three_draw import replay
from trace_misuse import jobs, run
from trace_nonbold import response
from trace_partial_grades import fields


PRIVATE = run.RUN.with_name("benchpres_frozen_reflection_v1")
RATERS = ("A", "B")


def token(key, purpose, *values):
    message = json.dumps([purpose, *values], ensure_ascii=False).encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def write_frozen(path, content):
    data = content.encode("utf-8")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Existing frozen review asset differs: {path.name}")
        return
    with path.open("xb") as handle:
        path.chmod(0o600)
        handle.write(data)


def inventory():
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    result = replay(plan)
    committed = run.read(run.OUT / "FINAL_REPLAY.json")
    if result != committed or not result["full_allocation_terminal"]:
        raise ValueError("Source benchmark must reproduce the committed final replay")
    cases = {case["uid"]: case for case in plan["cases"]}
    draws, paired, statuses = [], defaultdict(list), defaultdict(Counter)
    for wave in result["settled_waves"]:
        area = run.RUN / f"wave-{wave}"
        actor, judge = jobs(area, "ACTOR"), jobs(area, "JUDGE")
        for row in run.read(area / "RESULTS.json"):
            uid, method, draw = (row[k] for k in ("uid", "method", "replicate"))
            case = cases[uid]
            statuses[method][row["status"]] += 1
            item = {
                "uid": uid, "method": method, "draw": draw, "wave": wave,
                "profile_group": case["analysis_group_id"], "status": row["status"],
                "actor_status": row["actor_status"], "old_strict_score": row["score"] is not None,
                "answer": None,
            }
            if row["actor_status"] == "OK":
                job = actor[uid, method, draw, "Actor"]
                answer = response(area, "generation", job)
                if answer:
                    ref = run.read(run.ROOT / case["evaluation_path"])
                    query = run.prior.base.task_for(case).query
                    attrs, completeness = fields(area, row, ref, query, plan["protocols"]["grading"], actor, judge)
                    item.update(answer=answer, attributes=attrs, old_completeness=completeness,
                                actor_request_sha256=sha(job["request"]), answer_sha256=sha(answer))
                    paired[uid, draw].append(item)
            draws.append(item)
    complete = [values for values in paired.values() if len(values) == 2]
    availability = Counter(item["method"] for item in draws if item["answer"] is not None)
    strict = sum(all(x["old_strict_score"] for x in pair) for pair in complete)
    if len(draws) != result["allocated_task_draw_pairs"] * len(run.METHODS):
        raise ValueError("Unexpected reflection allocation")
    if strict != result["available_pairs"]["task_draw_pairs"] or statuses != result["scoring_states"]:
        raise ValueError("Inventory disagrees with original grade availability")
    return draws, {
        "input_plan_sha256": result["plan_sha256"], "allocated_answers": len(draws),
        "available_answers_by_arm": availability, "missing_answers": len(draws) - sum(availability.values()),
        "common_answer_pairs": len(complete), "common_original_strict_score_pairs": strict,
        "single_arm_answers": sum(availability.values()) - 2 * len(complete),
        "human_reviews_completed": 0, "model_calls_added": 0,
    }


def export(draws, key, target):
    private_index = {rater: {} for rater in RATERS}
    for rater in RATERS:
        packet = []
        for item in draws:
            if item["answer"] is None:
                continue
            for i, attr in enumerate(item["attributes"]):
                row_id = token(key, "review", rater, item["uid"], item["method"], item["draw"], i)[:24]
                if row_id in private_index[rater]:
                    raise ValueError("Review identifier collision")
                packet.append({"id": row_id, "attribute": attr["attribute"], "answer": item["answer"]})
                private_index[rater][row_id] = [item["uid"], item["method"], item["draw"], i]
        packet.sort(key=lambda row: token(key, "order", rater, row["id"]))
        write_frozen(target / f"RATER_{rater}.jsonl", "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in packet
        ))
        template = io.StringIO(newline="")
        writer = csv.writer(template)
        writer.writerow(("id", "reflection", "evidence"))
        writer.writerows((row["id"], "", "") for row in packet)
        write_frozen(target / f"RATER_{rater}_VOTES.csv", template.getvalue())
    index = [{k: v for k, v in item.items() if k != "answer"} for item in draws]
    write_frozen(target / "CUSTODIAN_ONLY.json",
                 json.dumps({"rater_ids": private_index, "draws": index}, ensure_ascii=False, indent=2) + "\n")
    return {rater: len(private_index[rater]) for rater in RATERS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    draws, summary = inventory()
    if args.freeze:
        PRIVATE.mkdir(mode=0o700, exist_ok=True)
        if PRIVATE.stat().st_mode & 0o077:
            raise ValueError("Private review directory must restrict access to its owner")
        seed = PRIVATE / "SEED_PRIVATE"
        if not seed.exists():
            write_frozen(seed, secrets.token_hex(32))
        summary["ratings_allocated_per_rater"] = export(draws, bytes.fromhex(seed.read_text()), PRIVATE)
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
