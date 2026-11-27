"""Compare saved RP Judge messages with the pinned author rows and scored answers."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parents[1]
archive = base / "rpeval_formal_multi_coverage_v1"
root = base.parents[1]
run = root / "runs" / base.name / archive.name / "grading"
author = root / "literature/qamc_pa_v1/RPEval"
revision = "0f8bce80a03e6b86426485264b14ae7de49cc8f9"
def read(path):
    return json.loads(path.read_text())

tracks = {t: json.loads(subprocess.check_output(["git", "-C", str(author), "show",
          f"{revision}:benchmark_dataset/{t}_preference/multi_testset.json"])) for t in ("explicit","implicit")}
cases = {r["uid"]: r for r in read(archive/"PLAN.json")["cases"]}
rows = {r["uid"]:r for r in read(archive/"RESULT_ROWS.json") if r["method"] == "RPR_PAPER_FULL"}
receipts = {}
for path in (run/"outputs").glob("*.json"):
    receipt = read(path)
    unit = receipt["unit"]
    if unit["method"] == "RPR_PAPER_FULL" and unit["stage"] == "RPEvalJudge":
        assert unit["root_id"] not in receipts
        receipts[unit["root_id"]] = receipt
counts = Counter()
for uid,row in rows.items():
    case = cases[uid]
    assert not case["independent_confirmation"]
    counts["assigned"] += 1
    receipt = receipts.get(uid)
    if not receipt or receipt["status"] != "OK":
        counts["no_local_success_receipt"] += 1
        continue
    wire = read(run/"execution/visible"/receipt["sample_key"]/"request.json")
    payload = json.dumps(wire,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    assert hashlib.sha256(payload.encode()).hexdigest() == receipt["request_sha256"]
    assert receipt["response"]["answer"] == row["raw_scores"]["RPEvalJudge"]
    track = case["track"].split("/")[0]
    ref = tracks[track][case["row_index"]]
    prompt = wire["messages"][-1]["content"]
    labels = ref["intent_type"]
    content = ref["implicit_persona" if track == "implicit" else "persona"]
    actor = json.loads(row["actor_request"]["messages"][-1]["content"])
    assert [v["text"] for v in actor["source_evidence"]] == content
    checks = {"two_intent_fields": all(f"【{key}】：{labels}\n" in prompt for key in ("intent","intent_type")),
              "ordered_sources": f"【Persona】:{content}\n" in prompt,
              "answer": f"【Reply】:{row['answer']}\n" in prompt,
              "question": f"【question】:{ref['question']}\n" in prompt}
    counts[track+"_receipts"] += 1
    counts[track+"_matches_author_persona"] += int(f"【Persona】:{ref['persona']}\n" in prompt)
    counts[track+"_matches_actor_sources"] += int(checks["ordered_sources"])
    counts["verified_receipt"] += 1
    for key,val in checks.items():
        counts[key] += int(val)
    if uid.endswith("/explicit/000"):
        assert all(checks.values()) and labels == "ABCAAABAA"
        counts["chengdu_verified"] += 1
print(json.dumps(counts,indent=2,sort_keys=True))
