"""Validate the expansion's exact archived scoring envelopes without dispatch."""
import json

from build_jobs import archive as baseline_archive, archive_inputs
from preflight_selected_gepa import HERE, prepare
from qamc.common import sha
from transfer_execution import grading_jobs
from transfer_replay import RUNS, persist, saved_scores


def grading_panel():
    bench = "PersistBench"
    items, _ = prepare()
    cases, protocol, _ = baseline_archive.transfer.context(bench)
    archive, _ = archive_inputs()
    receipts = saved_scores(RUNS / persist.AUTHOR_OUT.name / "gpt41")
    panel = json.loads((HERE / "SELECTED_GEPA_EXPANSION_PANEL.json").read_text())
    result = {}
    for case in panel["cases"]:
        uid = case["uid"]
        baseline = archive[bench, uid]
        old, = grading_jobs(bench, [baseline], cases, protocol)[0].values()
        receipt = receipts[uid, "PB_RUBRIC"]
        if sha(old) != receipt["request_sha256"]:
            raise ValueError(f"Archived grading request differs for {uid}")
        if baseline["raw_scores"][persist.STAGE] != receipt["response"]["answer"]:
            raise ValueError(f"Archived grading reply differs for {uid}")
        probe = "QAMC offline grading-envelope probe. Never dispatch."
        alternate, = grading_jobs(bench, [{**baseline, "answer": probe}], cases, protocol)[0].values()
        original = old["messages"][1]["content"]
        if original.count(baseline["answer"]) != 1:
            raise ValueError(f"Archived answer does not occur once for {uid}")
        expected = {**old, "messages": [old["messages"][0], {
            **old["messages"][1], "content": original.replace(baseline["answer"], probe, 1),
        }]}
        if alternate != expected:
            raise ValueError(f"Changing the answer modifies other grading inputs for {uid}")
        result[uid] = {"archived_judge_sha256": sha(old), "substitution_probe_sha256": sha(alternate)}
    if set(result) != set(items):
        raise ValueError("Preparation and grading panels disagree")
    return result


if __name__ == "__main__":
    print(json.dumps(grading_panel(), indent=2))
