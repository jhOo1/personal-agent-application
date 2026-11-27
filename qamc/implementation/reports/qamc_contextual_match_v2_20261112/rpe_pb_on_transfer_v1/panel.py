"""Freeze a source-disjoint exposed ON panel; do not construct model input from scores."""
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
FORMAL = BASE / "rpeval_formal_multi_coverage_v1"

def read(p):
    return json.loads(p.read_text())

def roster():
    endpoints = read(BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    archive = {r["uid"]: r for r in read(FORMAL / "RESULT_ROWS.json") if r["method"] == "RPR_PAPER_FULL"}
    manifest = {c["uid"]: c for c in read(FORMAL / "MANIFEST_300.json")}
    tasks = read(FORMAL / "PUBLIC_TASKS.json")
    groups = set()
    panel = []
    # Prespecified behavior anchors; the fourth deliberately includes an all-ignore misuse.
    anchors = ("explicit/074", "explicit/129", "explicit/094", "implicit/094")
    order = sorted(endpoints, key=lambda r: sha256(("pb-on-transfer-v1/" + r["uid"]).encode()).digest())
    for suffix in (*anchors, None):
        for row in order:
            uid = row["uid"]
            if suffix and not uid.endswith("/" + suffix):
                continue
            if row["old_route"] != "REUSE_RP" or row["source_group"] in groups:
                continue
            labels = row["labels"]
            if suffix is None and ("A" not in labels or not ({"B", "C"} & set(labels))):
                continue
            case, a, task = manifest[uid], archive[uid], tasks[uid]
            assert not case["independent_confirmation"] and case["analysis_group_id"] == row["source_group"]
            if a["actor_status"] != "OK":
                continue
            packet = json.loads(a["actor_request"]["messages"][1]["content"])
            evidence, policy = packet["source_evidence"], packet["preference_use_policy"]
            assert [x["text"] for x in evidence] == [x["text"] for x in task["memories"]]
            assert [x["memory_id"] for x in evidence] == [x["memory_id"] for x in policy]
            assert len(set(x["text"] for x in evidence)) == len(evidence)
            assert packet["query"] == task["query"] and packet["facts"] == task["fixed_facts"]
            groups.add(row["source_group"])
            panel.append(dict(uid=uid,group=row["source_group"],reason=suffix or "mixed_hash",
                              wire=a["actor_request_sha256"],source_count=len(evidence)))
            if len(panel)==12:
                return panel
    raise ValueError("Insufficient verified ON roots")

if __name__ == "__main__":
    print(json.dumps(roster(),indent=2))
