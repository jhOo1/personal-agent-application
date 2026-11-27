"""Rebuild target full-system requests before treating a legacy answer as reusable."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from audit import BASE, LEGACY, key, read, roster

ROOT = BASE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT)]
from qamc.common import parse_object, sha
from qamc.pa.rpeval_scoring import judge_prompt, load_rubrics
from qamc.contextual_match.development import text_request
from qamc.pa.core import Memory, PublicTask
from proposals.qamc_des2gen import core as des
from proposals.qamc_rpr_cross_benchmark import core as rp


def check():
    verified = roster()[-1]
    dp = read(ROOT / "reports/qamc_contextual_match_20261111/PROMPTS.json")["base"]["d2g"]
    rp_dir = ROOT / "proposals/qamc_rpreasoner_paper"
    pp = {k: (rp_dir / (k + ".md")).read_text() for k in ("mle", "ipe", "generator")}
    runs = LEGACY.parent / "runs"
    api = runs / "qamc_rpreasoner_paper/execution/api"
    rubrics = load_rubrics(ROOT / "literature/qamc_pa_v1/RPEval/prompts/prompts_715.py")
    counts = Counter()
    with closing(sqlite3.connect((api / "ledger.sqlite").as_uri()+"?mode=ro", uri=True)) as rb, closing(sqlite3.connect(
            (runs / "qamc_des2gen/execution/samples.sqlite").as_uri()+"?mode=ro", uri=True)) as db:
        for row in read(LEGACY / "qamc_des2gen/ALL_NINE_CASE_DETAILS.json"):
            c = row["case"]
            if c["benchmark"] != "rpeval" or key(c) not in verified:
                continue
            v = row["original_public_input"]
            assert v["uid"] == verified[key(c)]["uid"]
            t = PublicTask(v["uid"], v["query"], tuple(Memory(m["memory_id"], m["text"], tuple(map(tuple,m["ranges"])))
                           for m in v["memories"]), v["current_context"], tuple(v["fixed_facts"]))
            def rp_answer(body):
                for (raw,) in rb.execute("select data from requests where payload_sha=?", (sha(body),)):
                    receipt = json.loads(raw)
                    if receipt["status"] == "ok" and read(api / receipt["request_path"]) == body:
                        return read(api / receipt["response_path"])["answer"]
            def des_answer(stage, body):
                for req, res in db.execute("select request_json,response_json from samples where request_sha=? "
                                           "and json_extract(unit_json,'$.root_id')=? and json_extract(unit_json,'$.stage')=? "
                                           "and status='COMPLETE'", (sha(body), t.uid, stage)):
                    if json.loads(req) == body:
                        return json.loads(res)["answer"]
            def judge_body(answer):
                ref = read(LEGACY.parent / c["evaluation_path"])
                return text_request("Evaluate the completed answer using the supplied benchmark rubric. Return JSON.",
                                    judge_prompt(rubrics, ref, answer, False), "qwen3.8-flash", 8192)
            estimates = {k: rp_answer(b) for k,b in rp.estimator_requests(t,pp).items()}
            for k,s in estimates.items():
                counts["RP_exact_"+k] += bool(s)
            if all(estimates.values()):
                req = rp.generator_request(t, pp, **{k:parse_object(s) for k,s in estimates.items()})["request"]
                ans = rp_answer(req)
                counts["RP_chain_and_answer_exact"] += bool(ans and ans == row["methods"]["RPR_PAPER_XBENCH"]["answer"])
                if ans:
                    counts["RP_exact_target_judge_in_original_ledger"] += bool(rp_answer(judge_body(ans)))
            s = des_answer("Decision", des.decision_request(t,dp))
            counts["Des2Gen_exact_decision"] += bool(s)
            if s:
                req = des.generator_request(t,dp,des.parse_decisions(t,s))["request"]
                ans = des_answer("Actor",req)
                counts["Des2Gen_chain_and_answer_exact"] += bool(ans and ans == row["methods"]["D2G_PAPER_ADAPT"]["answer"])
                if ans:
                    counts["Des2Gen_exact_target_judge_in_original_ledger"] += bool(des_answer("RPEvalJudge", judge_body(ans)))
    return dict(counts)


if __name__ == "__main__":
    print(json.dumps(check(),sort_keys=True,indent=2))
