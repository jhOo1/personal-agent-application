"""Sharp per-task bounds from saved position counts, with a source-verified example."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parent.parent
author = base.parents[1] / "literature/qamc_pa_v1/RPEval"
revision = "0f8bce80a03e6b86426485264b14ae7de49cc8f9"
def load(path):
    return json.loads(path.read_text())

tracks = {t: json.loads(subprocess.check_output(["git", "-C", str(author), "show",
          f"{revision}:benchmark_dataset/{t}_preference/multi_testset.json"])) for t in ("explicit","implicit")}
bounds = defaultdict(Counter)
rows = load(base / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
cases = {r["uid"]: r for r in load(base / "rpeval_formal_multi_coverage_v1/PLAN.json")["cases"]}
for row in rows:
    if not all(v["grade"].get("match") for v in row["scores"].values()):
        continue
    case = cases[row["uid"]]
    assert not case["independent_confirmation"]
    track, index = case["track"].split("/")[0], case["row_index"]
    labels = tracks[track][int(index)]["intent_type"]
    assert labels == row["labels"]
    if "C" not in labels:
        continue
    for arm, cell in row["scores"].items():
        score = cell["grade"]["match"]
        assert score["positions"] == len(labels)
        errors = len(labels) - score["matched"]
        for sample in ["all"] + (["unflagged"] if all(v["flags"] == [] for v in row["scores"].values()) else []):
            count = bounds[sample + "/" + arm]
            count["tasks"] += 1
            count["unmatched"] += errors
            for name, n in [("A", labels.count("A")), ("BC", len(labels)-labels.count("A")), ("C",labels.count("C"))]:
                low = max(0, errors - (len(labels)-n))
                high = min(errors,n)
                count[name+"_min_positions"] += low
                count[name+"_max_positions"] += high
                count[name+"_forced_tasks"] += low > 0

uid = "rpeval/formal_multi_v1/explicit/000"
row = next(r for r in rows if r["uid"] == uid)
raw = next(r for r in load(base / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
           if r["uid"] == uid and r["method"] == "RPR_PAPER_FULL")
assert sha256(raw["answer"].encode()).hexdigest() == row["scores"]["IPE_C"]["answer_sha256"]
judge = json.loads(raw["raw_scores"]["RPEvalJudge"])
assert "第4、5、8条" in judge["reason"] and "intent要求部分结合（B）" in judge["reason"]
assert all(row["labels"][idx-1] == "A" for idx in (4,5,8))
assert "如果某处人多" in raw["answer"] and "不安排高强度活动" in raw["answer"]
print(json.dumps({"counts":bounds,"case":{"match":judge["match"],"UPB":judge["UPB"],
                 "existing_flags":row["scores"]["IPE_C"]["flags"]}},indent=2,sort_keys=True))
