"""Execute one frozen policy via the archived Actor and native grading contracts."""
from collections import defaultdict

from build_jobs import prepare
from qamc.common import sha
from residual import policy
from trial_reassembly import grading


def evaluate(rules, split, dispatch):
    rules = policy(rules)
    arm = "nro_" + sha(rules)[:24]
    jobs, baselines = prepare(rules, split)
    batches = defaultdict(dict)
    for (benchmark, uid), wire in jobs.items():
        batches[benchmark][uid, arm] = wire

    replies = {}
    for benchmark, batch in sorted(batches.items()):
        stage = f"{arm}_{benchmark}_Actor"
        returned = dispatch(stage, batch)
        if returned.keys() != batch.keys():
            raise ValueError("Actor receipts do not cover the frozen batch")
        for (uid, _), response in returned.items():
            if response.get("request_sha256") != sha(batch[uid, arm]):
                raise ValueError("Actor receipt hash differs")
            replies[benchmark, uid] = response

    targets = []
    for key, base in baselines.items():
        benchmark, uid = key
        response = replies.get(key)
        answer = base["base_answer"] if response is None else response.get("answer")
        status = "OK" if response is None else response["status"]
        if status != "OK":
            answer = None
        elif not isinstance(answer, str) or not answer.strip():
            status, answer = "EMPTY_ANSWER", None
        exact = answer == base["base_answer"]
        targets.append({
            "uid": uid, "benchmark": benchmark, "group": base["group"],
            "stratum": base["stratum"], "method": arm, "answer": answer,
            "actor_status": status, "sources": base["root"]["original_sources"],
            "score": base["base_score"] if exact else None,
            "score_flags": base["base_flags"] if exact else None,
            "generation_origin": "EXACT_ARCHIVE" if response is None else "POLICY",
        })

    def score(stage, wires, cache=None):
        results = dispatch(f"{arm}_{stage}", wires, cache)
        if results.keys() != wires.keys():
            raise ValueError("Judge receipts do not cover the requested batch")
        for key, receipt in results.items():
            if receipt.get("request_sha256") != sha(wires[key]):
                raise ValueError("Judge receipt hash differs")
        return results

    if any(row["actor_status"] == "OK" and row["score"] is None for row in targets):
        grading(targets, score)
    return targets
