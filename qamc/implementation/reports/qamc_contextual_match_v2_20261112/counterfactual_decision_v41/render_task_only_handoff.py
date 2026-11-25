"""Append the settled no-history control to the full stage handoff."""
from argparse import ArgumentParser
import json
from pathlib import Path

from qamc.common import sha
from score_task_only import OUT, READ, saved_drafts, v41

WITNESSES = ("rpeval/pa_transfer_20261109/e097bc155af6d021da86",
             "rpeval/formal_multi_v1/explicit/007",
             "rpeval/formal_multi_v1/explicit/046",
             "rpeval/formal_multi_v1/implicit/105")


def json_block(data):
    return "\n\n````json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n````\n"


def render():
    parent = READ(v41.OUT / "FROZEN.json")
    control = READ(OUT / "FROZEN.json")
    terminal = READ(OUT / "RESULTS.json")
    if terminal["state"]["state"] != "COMPLETE" or len(terminal["ledger"]) != control["maximum_new_grade_requests"]:
        raise ValueError("Wait for all planned scoring requests before generating the handoff")
    roots = {row["uid"]: row for row in parent["roots"]}
    scored = {row["uid"]: row for row in terminal["roots"]}
    grades = {sha(item["request"]): item["request"]
              for wave in control["waves"].values() for item in wave["units"]}
    drafts = saved_drafts(parent)
    parts = [(OUT / "RESULTS.md").read_text(), "\n\n## 上一阶段 V41 全量复盘\n\n",
             (v41.OUT / "TERMINAL_REVIEW.md").read_text()]
    for uid in WITNESSES:
        source, result, indices = roots[uid], scored[uid], control["ready"][uid]
        old_draft = drafts[indices["task_wire_sha256"]]
        request = v41.task_only_request(source)
        if sha(request) != indices["task_wire_sha256"] or sha(old_draft["answer"]) != indices["answer_sha256"]:
            raise ValueError("No-history witness drift")
        parts.extend([f"\n## 无历史对照案例 {uid}", json_block({
            "author_labels": result["labels"], "sources": source["original_sources"],
            "RP_predictions": source["archived_policy"], "RP_actual_request": source["archived_actor_request"],
            "RP_archived_answer_and_score": source["archived"][v41.RP],
            "task_only_actual_request": request, "task_only_answer": old_draft["answer"],
            "task_only_score": result["task_only"],
            "task_only_native_judge_request": grades[indices["graded_wire_sha256"]],
        })])
    parts.extend(["\n## 无历史对照逐题原生评分与实际账本", json_block(terminal),
                  "\n## 无历史对照诊断与路由回放", json_block(READ(OUT / "DIAGNOSTICS.json")),
                  "\n## 前置策略错误与最终原生失分的重合边界", json_block(READ(OUT / "UPSTREAM_HEADROOM.json"))])
    return "".join(parts)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    output = parser.parse_args().path
    with output.open("x", encoding="utf-8") as file:
        file.write(render())
    print(f"{output}  {sha(output.read_bytes())}")
