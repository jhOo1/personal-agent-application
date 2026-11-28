"""Bind ten prior screening rows to exact routing receipts and author controls."""
from collections import Counter
import json
from pathlib import Path

from complete import ROOT, actor_request, get_author, input_requests, normalized, probe, read, transfer
from qamc.common import sha
from repeat_receipts import branch
from transfer_replay import persist

HERE = Path(__file__).resolve().parent
ROOT_RUNS = ROOT / "runs" / HERE.parent.name
RUN = ROOT_RUNS / HERE.name
SCREEN = ROOT_RUNS / "persist_router_opportunity_v1/screen_private"
ACTOR_CAP = 8192
ANSWER = '__QAMC_TEST_ANSWER__'
EXPECTED = {"sycophancy": 8, "beneficial_memory_usage": 2}


def prepare():
    old = {r["uid"] for r in read(ROOT_RUNS / "persist_exposure_fr3_v1/RESULTS.json")["rows"]}
    roster = read(HERE.parent / "persist_author_controls_v2/PLAN.json")
    screened = read(SCREEN / "SETTLED.json")["roots"]
    cases = {c["uid"]: c for c in roster["cases"] if c["uid"] in screened}
    if not roster["not_confirmation"] or set(cases) != set(screened) or set(cases) & old:
        raise ValueError("Overlap or invalid exposure boundary")
    if Counter(c["category"] for c in cases.values()) != EXPECTED or any(c["role"] != "DEV" for c in cases.values()):
        raise ValueError("Unexpected assigned tracks or sealed role")
    if len({c["group_id"] for c in cases.values()}) != len(cases):
        raise ValueError("Duplicate source group")
    author, envelopes, _ = get_author()
    old_control = {(r["uid"], r["method"]): r for r in author if r["uid"] in cases}
    protocol = read(ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    route_plan = read(transfer.OUT / "PLAN.json")
    archived = {}
    for path in (SCREEN / "QueryOnly/visible").glob("*/record.json"):
        rec = read(path)
        uid = rec["unit"]["root_id"]
        if uid in archived:
            raise ValueError("Ambiguous earlier route")
        wire, response = (read(path.with_name(n)) for n in ("request.json", "response.json"))
        if rec["status"] != "OK" or sha(wire) != rec["request_sha256"]:
            raise ValueError("Earlier route was unverified")
        archived[uid] = wire, response["answer"]
    rows, wires, rebuilt = {}, {}, {}
    judge = roster["protocols"]["gpt41"]
    _, rubrics, formatter = persist.author.ext.parent.persist.upstream()
    for uid, case in cases.items():
        task = persist.author.parent.smoke.task_for(case)
        public = {"query": task.query, "memories": [m.text for m in task.memories]}
        if sha(public) != case["public_sha256"]:
            raise ValueError("Fixed task changed")
        route, response = archived[uid]
        inputs = input_requests(case, public, route_plan)
        fork = branch(public, response)
        if route != inputs["query"] or fork != screened[uid]:
            raise ValueError("Original query-only result changed")
        full = actor_request(case, public["query"], public["memories"], protocol, protocol["prompts"]["gepa"])
        gepa = old_control[uid, "PB_GEPA"]
        rubric = old_control[uid, "PB_RUBRIC"]
        if (sha(gepa["actor_request"]) != gepa["actor_request_sha256"]
                or sha(rubric["actor_request"]) != rubric["actor_request_sha256"]):
            raise ValueError("Invalid author baseline request identity")
        if full != dict(gepa["actor_request"], max_tokens=ACTOR_CAP):
            raise ValueError("Full history control differs beyond its cap")
        empty = actor_request(case, public["query"], [], protocol, protocol["prompts"]["gepa"])
        actors = {"FULL": full, "EMPTY": empty, "RUBRIC": dict(rubric["actor_request"], max_tokens=ACTOR_CAP)}
        immutable = {k: v for k, v in full.items() if k != "messages"}
        if any({k: v for k, v in w.items() if k != "messages"} != immutable for w in actors.values()):
            raise ValueError("Sampling controls diverge")
        template = persist.author.ext.text_request(
            rubrics[case["category"]],
            formatter["build_judge_prompt"](public["memories"], public["query"], ANSWER),
            judge["model"], judge["stages"][persist.STAGE]["max_tokens"],
        )
        rebuilt[uid] = normalized(template, ANSWER)
        if uid in envelopes and rebuilt[uid] != envelopes[uid]:
            raise ValueError("Rebuilt grading contract differs")
        rows[uid] = {"track": case["category"], "group": case["group_id"], "fork": fork,
                     "candidate_count": len(public["memories"]), "route_sha256": sha(route),
                     "route_answer_sha256": sha(response), "selector_sha256": sha(inputs[fork]),
                     "actor_hashes": {k: sha(v) for k, v in actors.items()},
                     "judge_envelope": sha(rebuilt[uid]),
                     "historical_judge_envelope": uid in envelopes,
                     "archived_author_rubric_has_grade": bool(rubric.get("score"))}
        wires[uid] = {"case": case, "public": public, "route_answer": response,
                      "select": inputs[fork], **actors}
    pin = {"rows": rows, "config_hash": probe.read_reference()[1],
           "source_hash": sha((SCREEN / "SETTLED.json").read_bytes()),
           "tracks": EXPECTED}
    return pin, wires, protocol, judge, rebuilt


if __name__ == "__main__":
    pin, _, _, _, _ = prepare()
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    probe.freeze(RUN / "FROZEN_PREFLIGHT.json", pin)
    print(json.dumps({"sources": pin["tracks"],
                      "existing_author_rubric_score": sum(r["archived_author_rubric_has_grade"] for r in pin["rows"].values()),
                      "existing_author_judge_envelope": sum(r["historical_judge_envelope"] for r in pin["rows"].values()),
                      "branches": Counter(r["fork"] for r in pin["rows"].values()),
                      "model_requests": 0}, sort_keys=True))
