"""Recover exact strong endpoint answers for the last development comparison."""
from collections import Counter
import json
from pathlib import Path

import collect_interventions as archive
from qamc.common import sha

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def card(root, benchmark, group, stratum, method, answer, score, flags=None):
    return {"root":root,"benchmark":benchmark,"group":group,"stratum":stratum,"baseline":method,
            "base_answer":answer,"base_score":score,"base_flags":flags,"baseline_answer_sha256":sha(answer)}


def rpe():
    stored = archive.read(BASE/"ipe_c_two_endpoint_completion_v1"/"RESULTS.json")["rows"]
    original = archive.read(archive.v41.formal.OUT/"PLAN.json")
    if any(row["independent_confirmation"] for row in original["cases"]):
        raise ValueError("Require exposed RPEval cohort")
    cohort = archive.v41.author_cases(original)
    rp = {r["uid"]:r for r in archive.read(archive.v41.formal.OUT/"RESULT_ROWS.json")
          if r["uid"] in cohort and r["method"]==archive.engine.RP and r["actor_status"]=="OK"}
    result = {}
    for cell in stored:
        uid,strong = cell["uid"],cell["ipe_c"]
        if uid not in rp or not strong["answer_sha256"] or not strong["grade"].get("match"):
            continue
        row = rp[uid]
        wire = row["actor_request"]
        if sha(wire)!=row["actor_request_sha256"]:
            raise ValueError("Saved RP wire mismatch")
        packet = json.loads(wire["messages"][1]["content"])
        root = {"uid":uid,"public_task":{k:packet[k] for k in ("query","current_context","facts")},
                "original_sources":packet["source_evidence"]}
        answer = row["answer"] if cell["old_route"]=="REUSE_RP" else cell["no_history_state"]["answer"]
        if not answer or sha(answer)!=strong["answer_sha256"]:
            raise ValueError(f"Cannot bind exact IPE-C answer: {uid}")
        labels=cell["labels"]
        stratum = "all_A" if set(labels)=={"A"} else "contains_C" if "C" in labels else "B_only"
        result[uid] = card(root,"RPEval",cell["source_group"],stratum,"IPE_C",answer,strong["grade"],strong["flags"])
    return result


def transfer(benchmark):
    cases,protocol,controls = archive.transfer.context(benchmark)
    method = archive.engine.GATE if benchmark=="BenchPreS" else "PB_RUBRIC"
    group_field = "analysis_group_id" if benchmark=="BenchPreS" else "group_id"
    scores = {r["uid"]:r["score"] for r in controls if r["method"]==method and r["score"] is not None}
    rows = archive.transfer.archived_answers(benchmark,cases)
    stored = {}
    for row in rows:
        if row["method"]!=method or row["actor_status"]!="OK" or not row.get("actor_request"):
            continue
        if row["uid"] in stored or sha(row["actor_request"])!=row["actor_request_sha256"]:
            raise ValueError("Saved strong endpoint is ambiguous or mismatched")
        stored[row["uid"]]=row
    raw_cache, conflicts = archive.transfer.matching_grading_receipts(benchmark,cases,protocol,rows)
    result = {}
    for root in archive.transfer.development_roots(benchmark):
        uid = root["uid"]
        if uid not in stored or uid not in scores:
            continue
        row = stored[uid]
        if row.get("score")!=scores[uid]:
            raise ValueError(f"Grade not bound to original strong completion: {uid}")
        wires,_ = archive.transfer.grading_jobs(benchmark,[row],cases,protocol)
        if not wires or any(sha(w) not in raw_cache or sha(w) in conflicts for w in wires.values()):
            continue
        stratum = "communication" if benchmark=="BenchPreS" else cases[uid]["category"]
        result[uid] = card(root,benchmark,cases[uid][group_field],stratum,method,row["answer"],scores[uid])
    return result


def panel():
    v1 = archive.read(BASE/"paired_regret_policy_v1"/"OUTCOME.json")
    matrix = archive.read(BASE/"paired_regret_policy_v1"/"MATRIX.json")["rows"]
    by_domain = {b:[r["uid"] for r in matrix if r["domain"]==b and r["uid"] in v1["predictions"]]
                 for b in ("RPEval","BenchPreS","PersistBench")}
    rpe_cards = rpe()
    allowed = set(by_domain["RPEval"])
    diagnostic = ("implicit/094","implicit/142","implicit/021","explicit/076","explicit/116","implicit/043",
                  "implicit/102","implicit/136")
    groups, picked = set(), []
    for suffix in diagnostic:
        uid = "rpeval/formal_multi_v1/"+suffix
        if uid not in allowed or uid not in rpe_cards or rpe_cards[uid]["group"] in groups:
            continue
        item = rpe_cards[uid]
        picked.append({**item,"diagnostic":True})
        groups.add(item["group"])
    for stratum in ("all_A","B_only","contains_C"):
        options = sorted((r for uid,r in rpe_cards.items() if uid in allowed and r["stratum"]==stratum),
                         key=lambda r:sha(["tatr-roster-v1",r["group"],r["root"]["uid"]]))
        need = 8-sum(r["stratum"]==stratum for r in picked)
        for row in options:
            if need<=0:
                break
            if row["group"] in groups:
                continue
            picked.append({**row,"diagnostic":False})
            groups.add(row["group"])
            need-=1
        if need:
            raise ValueError(f"Too few source groups in {stratum}")
    rejected = []
    for benchmark in ("BenchPreS","PersistBench"):
        bank = transfer(benchmark)
        for uid in by_domain[benchmark]:
            if uid not in bank:
                rejected.append({"uid":uid,"benchmark":benchmark,"reason":"STRONG_ANSWER_OR_EXACT_GRADE_UNAVAILABLE"})
                continue
            picked.append({**bank[uid],"diagnostic":False})
    return picked,rejected


if __name__=="__main__":
    picked,rejected = panel()
    print(dict(Counter(r["benchmark"] for r in picked)),rejected)
