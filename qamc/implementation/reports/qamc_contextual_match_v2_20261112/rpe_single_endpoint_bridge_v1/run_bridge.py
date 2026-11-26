"""Extend the frozen IPE-C route to the already-exposed single-preference roster."""
import argparse
import ast
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from complete import engine, probe, read
from extend import archived, merge_stage
from qamc.common import parse_object, sha
from qamc.contextual_match.development import text_request
from qamc.pa.core import digest
from qamc.pa.rpeval_scoring import judge_prompt, load_rubrics, parse_score

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = HERE.parents[2]
OLD = BASE / "paper_baseline_validation_156_v1"
AUTHOR = ROOT / "literature/qamc_pa_v1/RPEval"
RUN = engine.RUN.with_name(HERE.name)
FULL = "RPR_PAPER_FULL"
ZERO = "TASK_ONLY"
EXTERNAL = (FULL, "DES2GEN_FULL", "MEMADAPTER_FULL")
SYSTEM = "Evaluate the completed answer using the supplied benchmark rubric. Return JSON."
MODEL = "qwen3.8-flash"
CAP = 8192
ACTOR, JUDGE = "SingleZeroActor", "SingleDetailJudge"
LABELS = {"ignore": "A", "support": "B", "supportive": "B", "dominate": "C", "dominant": "C",
          "忽略偏好": "A", "支持性偏好": "B", "以偏好为主线": "C"}


def score_wire(rubrics, reference, answer):
    return text_request(SYSTEM, judge_prompt(rubrics, reference, answer, False), MODEL, CAP)


def frozen_manifest():
    included = [x for x in read(OLD / "MANIFEST_156.json")
                if x["benchmark"] == "rpeval" and x["track"].endswith("/single")]
    if len(included) != 24 or any(x["independent_confirmation"] for x in included):
        raise ValueError("Expected exactly 24 non-confirmation development tasks")
    if Counter(c["track"] for c in included) != {"explicit/single": 12, "implicit/single": 12}:
        raise ValueError("Frozen format allocation changed")
    return {c["uid"]: c for c in included}


def author_contract():
    root = AUTHOR / "prompts_715.py"
    detailed = AUTHOR / "prompts/prompts_715.py"
    entry = AUTHOR / "generation_task/eval_single.py"
    short = next(ast.literal_eval(n.value) for n in ast.parse(root.read_text()).body
                 if isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "_judge_template"
                                                       for x in n.targets))
    long = load_rubrics(detailed)
    if ("\"match\"" in short or '"match"' not in long["LLM_judge_prompt"]
            or 'from prompts_715 import LLM_judge_template' not in entry.read_text()
            or 'jr.get("match")' not in entry.read_text()):
        raise ValueError("Frozen author release contract differs")
    return long, {x.name if x != detailed else "detailed_prompts": sha(x.read_bytes())
                  for x in (root, detailed, entry)}


def prepare():
    cases = frozen_manifest()
    rubrics, protocol = author_contract()
    references = {u: read(ROOT / c["evaluation_path"]) for u, c in cases.items()}
    public = read(OLD / "PUBLIC_TASKS.json")
    parents = {(x["uid"], x["method"]): x for x in read(OLD / "RESULT_ROWS.json")
               if x["uid"] in cases and x["method"] in EXTERNAL}
    saved = {x["uid"]: x for x in read(OLD / "SAVED_OPPONENT_ROWS.json")
             if x["uid"] in cases and x["method"] == FULL}
    observed = set()
    for p in (OLD / "grading/stage_manifests").glob("*.json"):
        for x in read(p)["units"]:
            if x["unit"]["root_id"] in cases and x["unit"]["stage"] == "RPEvalJudge":
                observed.add(sha(x["request"]))
    if len(parents) != len(cases) * len(EXTERNAL) or len(saved) != len(cases):
        raise ValueError("Historical opponent inventory changed")
    archive, actors, routes = {}, {}, {}
    for uid, case in cases.items():
        ref = references[uid]
        task = public[uid]
        if (digest(ref) != case["evaluation_hash"] or digest(task) != case["public_hash"]
                or not isinstance(ref["persona"], str) or ref["question"] != task["query"]):
            raise ValueError("Private evaluation binding changed")
        rp = saved[uid]
        if rp["reader_statuses"]["RPR_IPE"] != "OK" or len(rp["aggregation"]) != 1:
            raise ValueError("Missing valid original IPE estimate")
        aggregation = rp["aggregation"][0]
        order = aggregation["ipe_order"]
        old = rp["actor_request"]
        packet = json.loads(old["messages"][1]["content"])
        if set(order) != set("ABC") or len(order) != 3:
            raise ValueError("Invalid original IPE order")
        if (aggregation["memory_id"] != "M0"
                or packet["source_evidence"] != [{"memory_id": "M0", "text": task["memories"][0]["text"]}]
                or packet["query"] != task["query"] or sha(old) != rp["actor_request_sha256"]
                or old != parents[uid, FULL]["actor_request"]):
            raise ValueError("Unverifiable old Actor input")
        routes[uid] = FULL if order[0] == "C" else ZERO
        wire = deepcopy(old)
        wire["messages"][1]["content"] = json.dumps({**packet, "source_evidence": [],
                                                     "preference_use_policy": []}, ensure_ascii=False)
        actors[uid, ZERO] = wire
        archive[uid] = {}
        for method in EXTERNAL:
            row = parents[uid, method]
            if row["actor_status"] != "OK" or not row["answer"]:
                raise ValueError("Fixed opponent answer missing")
            grade_key = sha(score_wire(rubrics, ref, row["answer"]))
            if grade_key not in observed:
                raise ValueError("Detailed adapted grading envelope drift")
            raw = row["raw_scores"]["RPEvalJudge"]
            score = parse_score(parse_object(raw))
            previous = row["score"]
            if any(previous[k] != score[k] for k in score):
                raise ValueError("Historical opponent grades changed")
            archive[uid][method] = score
    actor_cache, _ = archived(actors, ROOT)
    actor_cache = {key: row for key, row in actor_cache.items() if RUN.name not in Path(row["archive"]).parts}
    pin = {"actor_sha256": sha({uid: wire for (uid, _), wire in actors.items()}),
           "old_scores_sha256": sha(archive), "routes_sha256": sha(routes), "author_source": protocol,
           "cases_sha256": sha(cases), "code_sha256": sha(Path(__file__).read_bytes()),
           "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes())}
    return pin, cases, references, rubrics, archive, actors, routes, actor_cache


def dispatch(args, data):
    pin, cases, references, rubrics, base, actors, routes, cache = data
    if args.action == "freeze":
        probe.freeze(RUN / "FROZEN.json", {"pin": pin, "actor_cache": {u: r for (u, _), r in cache.items()}})
    elif args.action == "run":
        frozen = read(RUN / "FROZEN.json")
        if pin != frozen["pin"]:
            raise ValueError("Frozen single preference experiment changed")
        cache = {(uid, ZERO): r for uid, r in frozen["actor_cache"].items()}
        engine.OUT = probe.OUT = probe.RUN = RUN
        engine.CAP = dict.fromkeys((ACTOR, JUDGE), len(cases))
        identity = {"experiment_sha256": sha(frozen), "service_reference_sha256": probe.read_reference()[1]}
        ledger = []
        with probe.runner_lock(RUN / "runner.lock"):
            probe.freeze(RUN / "EXECUTION.json", identity)
            answers = merge_stage(ACTOR, actors, cache, identity, ledger)
            jobs = {key: score_wire(rubrics, references[key[0]], row["answer"])
                    for key, row in answers.items() if row["status"] == "OK"}
            judges, _ = archived(jobs, ROOT)
            judges = {k: v for k, v in judges.items() if RUN.name not in Path(v["archive"]).parts}
            scores = merge_stage(JUDGE, jobs, judges, identity, ledger)
            rows = []
            for uid, case in cases.items():
                key = uid, ZERO
                judge = scores.get(key)
                task_score = None
                status = answers[key]["status"]
                if judge:
                    status = judge["status"]
                    if status == "OK":
                        try:
                            task_score = parse_score(parse_object(judge["answer"]))
                        except (ValueError, TypeError, KeyError):
                            status = "INVALID_SCORE"
                fields = {**base[uid], ZERO: task_score}
                fields["IPE_C"] = fields[routes[uid]]
                rows.append({"uid": uid, "source_group": case["group_id"], "track": case["track"],
                             "label": LABELS[references[uid]["intent_type"]], "route": routes[uid],
                             "task_only_status": status, "actor": answers[key], "judge": judge, "scores": fields})
            if len(ledger) > 48:
                raise ValueError("Exceeded the frozen physical request ceiling")
            probe.freeze(RUN / "RESULTS.json", {"rows": rows, "ledger": ledger})
    print(json.dumps({"cases": len(cases), "routes": Counter(routes.values()),
                      "actor_cache": len(cache), "freeze_sha256": sha(pin)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run"))
    args = parser.parse_args()
    dispatch(args, prepare())
