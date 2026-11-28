"""Compare archived RPEval grades where the exact no-history Actor and answer coincide."""
from collections import Counter, defaultdict
from itertools import combinations
import json

import complete_endpoints as endpoints
from qamc.common import parse_object, sha


def audit():
    prior = endpoints.prior
    _, _, _, cached_answers, cached_grades, _, _ = endpoints.prepare()
    plan, cases, parent, archive, ranks, _, _, _ = prior.prepare()
    prepared = {row["uid"]: row.get("task_only_request_sha256") for row in plan["rows"]}
    result = prior.read(endpoints.HERE / "RESULTS.json")
    blocks = defaultdict(dict)
    counts = Counter()
    for row in result["rows"]:
        labels = row["labels"]
        if not labels or set(labels) != {"A"}:
            continue
        counts["all_a"] += 1
        endpoint = row["no_history_state"]
        control = row["controls"][endpoints.ZERO]
        grade, answer, raw = control["grade"], endpoint["answer"], endpoint["raw"]
        if not grade.get("match") or not answer or not raw:
            continue
        counts["graded"] += 1
        uid = row["uid"]
        digest = prepared[uid]
        wire = endpoints.v41.task_only_request(prior.source_root(archive[uid, endpoints.RP], ranks[uid]))
        data = json.loads(wire["messages"][1]["content"])
        if (sha(wire) != digest or cached_answers.get(digest) != answer
                or control["answer_sha256"] != sha(answer)
                or data["source_evidence"] != [] or data["preference_use_policy"] != []):
            raise ValueError("Could not verify exact no-history Actor and answer")
        judge_wire = endpoints.engine.rpe_wire(parent, cases[uid],
            {"uid": uid, "actor_status": "OK", "answer": answer})
        judge_digest = sha(judge_wire)
        receipt = endpoint.get("judge_receipt")
        grade_attested = (receipt["request_sha256"] == judge_digest if receipt
                          else cached_grades.get(judge_digest) == raw)
        fields, _ = endpoints.probe.fields(parse_object(raw), len(labels), True)
        if not grade_attested or fields != grade:
            raise ValueError("Could not verify archived Judge request and parsed score")
        block = blocks[digest, sha(answer), len(labels)]
        evaluated = (grade["match"]["matched"], grade["OPB"], grade["UPB"], control["flags"] == [])
        if block.setdefault(judge_digest, evaluated) != evaluated:
            raise ValueError("Conflicting grades for an identical Judge request")
    counts["actor_blocks"] = len(blocks)
    for block in blocks.values():
        if len(block) < 2:
            continue
        counts["distinct_judge_blocks"] += 1
        differences = False
        for (match_a, opb_a, upb_a, clean_a), (match_b, opb_b, upb_b, clean_b) in combinations(block.values(), 2):
            counts["pairs"] += 1
            counts["match_changes"] += match_a != match_b
            counts["positive_opb_flips"] += (opb_a > 0) != (opb_b > 0)
            counts["positive_upb_flips"] += (upb_a > 0) != (upb_b > 0)
            counts["clean_pairs"] += clean_a and clean_b
            counts["clean_match_changes"] += clean_a and clean_b and match_a != match_b
            differences |= match_a != match_b
        counts["blocks_with_match_change"] += differences
    return dict(counts)


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
