"""Check exact paired-draft transfer readiness on the two exposed development panels."""
from collections import Counter
import json

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import canonical, sha, token_estimate

import preflight_fixed_answer_choice as choice
from transfer_execution import (RP, bench, bench_context, development, development_roots,
                                grading_jobs, persist, persist_context)

prior = choice.study.prior


def benchmark(name):
    roots = development_roots(name)
    allowed = {root["uid"] for root in roots}
    if name == "BenchPreS":
        cases, protocol, controls = bench_context()
        archive_paths = (development.OUT / "RESULT_ROWS.json", bench.OUT / "RESULT_ROWS.json")
        other_rows = [r for path in archive_paths for r in prior.read(path) if r["uid"] in allowed]
    else:
        cases, protocol, controls = persist_context()
        source = (persist.AUTHOR_OUT / "waves").glob("*.json")
        other_rows = [r for r in prior.read(development.OUT / "RESULT_ROWS.json") if r["uid"] in allowed]
        other_rows.extend(r for path in sorted(source) for r in prior.read(path)["rows"] if r["uid"] in allowed)
    if cases.keys() != allowed:
        raise ValueError("Exposed grading cohort differs from generation inputs")
    replies, archive = {}, {}
    for row in other_rows:
        if row["method"] == RP:
            archive[row["uid"]] = row
        if row.get("answer") and row.get("actor_status") == "OK" and row.get("actor_request"):
            wire = sha(row["actor_request"])
            replies.setdefault((row["uid"], wire), set()).add(sha(row["answer"]))
    proposals, unique, available, answer_fixture = [], set(), 0, []
    for root in roots:
        uid = root["uid"]
        old_reply = archive[uid]
        if sha(old_reply["actor_request"]) != root["archived_actor_sha256"]:
            raise ValueError("Archived RP answer has another generation request")
        wire = prior.task_only_request(root)
        system, user = wire["messages"]
        empty = {**root["public_task"], "source_evidence": [], "preference_use_policy": []}
        if json.loads(user["content"]) != empty or system != root["archived_actor_request"]["messages"][0]:
            raise ValueError("Task-only drafting exposed memory or altered the RP system prompt")
        validate_public_request(wire)
        digest = sha(wire)
        unique.add(digest)
        matches = sorted(replies.get((uid, digest), ()))
        available += len(matches) == 1
        proposals.append({"uid": uid, "rp_wire_sha256": root["archived_actor_sha256"],
                          "task_only_wire_sha256": digest, "exact_archived_answer_sha256": matches})
        if old_reply.get("answer") and old_reply.get("actor_status") == "OK":
            rp = old_reply["answer"]
            fake = rp + "\n[Offline structure fixture]"
            payload = choice.packet(root, rp, fake)
            for method in choice.METHOD_PROMPTS:
                request = choice.request(payload, method)
                if token_estimate(canonical(request["messages"])) > 32768:
                    raise ValueError("Structure fixture exceeds selection input capacity")
            answer_fixture.append({"uid": uid, "method": RP, "answer": rp, "actor_status": "OK"})
    jobs, _ = grading_jobs(name, answer_fixture, cases, protocol)
    return {
        "development_roots": len(roots), "unique_task_only_requests": len(unique),
        "available_exact_task_only_answers": available,
        "verified_archived_rp_inputs_to_grading": len(answer_fixture),
        "native_grading_shapes": Counter(stage for _, _, stage in jobs),
        "valid_archived_strict": Counter(r["method"] for r in controls if r["score"] is not None),
        "nominal_upper_ceilings_if_expanded": {
            "new_task_only_actors": len(unique), "new_comparisons": 2 * len(roots),
            "task_only_native_scores": (6 if name == "BenchPreS" else 1) * len(roots),
        },
        "roots": proposals,
    }


if __name__ == "__main__":
    print(json.dumps({"new_model_calls": 0, "method_scores": 0,
                      "BenchPreS": benchmark("BenchPreS"), "PersistBench": benchmark("PersistBench")},
                     ensure_ascii=False, indent=2))
