"""Read-only verification on the one source root yielding the two perfect scores."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parents[1]
author = base.parents[1] / "literature/qamc_pa_v1/RPEval"
rev = "0f8bce80a03e6b86426485264b14ae7de49cc8f9"
def read(path):
    return json.loads((base/path).read_text())

endpoints = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
formal = read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
table = {}
for track, index in (("explicit",114), ("implicit",118)):
    uid = f"rpeval/formal_multi_v1/{track}/{index}"
    ref = json.loads(subprocess.check_output(["git","-C",str(author),"show",
        f"{rev}:benchmark_dataset/{track}_preference/multi_testset.json"]))[index]
    assert ref["intent_type"] == "AAAAABC"
    assert "新技术" in ref["persona"][5] and "任何手工制作环节" in ref["persona"][6]
    ep = next(r for r in endpoints if r["uid"] == uid)
    task = ep["no_history_state"]["answer"]
    assert "儿童书店、手工体验课" in task.split("雨天备选路线")[1].split("晴天备选路线")[0]
    assert "科技馆" in task
    assert sha256(task.encode()).hexdigest() == ep["scores"]["TASK_ONLY"]["answer_sha256"]
    table[track] = {"TASK_ONLY":ep["scores"]["TASK_ONLY"]["grade"]["match"]["matched"]}
    for row in formal:
        if row["uid"] != uid:
            continue
        assert "科技馆" in row["answer"]
        table[track][row["method"]] = row["native_fields"]["match"]["matched"]
        if row["method"] == "RPR_PAPER_FULL":
            assert sha256(row["answer"].encode()).hexdigest() == ep["scores"]["IPE_C"]["answer_sha256"]
            assert ("全程不安排折纸" if track=="explicit" else "不用做手工") in row["answer"]
            assert [m["policy"] for m in row["view"]["preference_use_policy"]][-2:] == ["B","C"]
            table[track]["IPE_C"] = table[track][row["method"]]
print(json.dumps(table, indent=2, sort_keys=True))
