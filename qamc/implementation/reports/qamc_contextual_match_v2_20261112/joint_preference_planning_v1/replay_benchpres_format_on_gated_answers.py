"""Replay the existing V31 formatter on the new BenchPreS gate without calls."""
from collections import Counter
import json
from pathlib import Path
import sys

from markdown_it import MarkdownIt

from audit_qamc_benchpres_bold_sensitivity import visible_strong
from qamc.common import sha
import run_communication_binding as run

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scoped_delivery_v31.render import BOLD_PREFERENCE, render_emphasis


def replay():
    path = run.OUT / run.BENCH / "SETTLED.json"
    result = run.read(path)
    if run.read(path.with_name("RUN_STATE.json"))["state"] != "COMPLETE":
        raise ValueError("Expected settled answers")
    roots = {row["uid"]: row for row in run.archive.development_roots(run.BENCH)}
    parser, totals, cases = MarkdownIt("commonmark"), Counter(), []
    for row in result["rows"]:
        if row["method"] != run.BOUND or row["actor_status"] != "OK":
            continue
        uid, answer = row["uid"], row["answer"]
        root, trace = roots[uid], result["selector"][uid]
        memory = root["original_sources"]
        uses = trace["bound"]
        layout = []
        for use in uses:
            mid = use["memory_id"]
            typed = trace["typed"][mid]
            if typed["source_act"] == typed["task_act"] == "LAYOUT" and typed["register_fit"] == "COMPATIBLE":
                layout.append({"id": mid, "scope": "grounded", "decision": "expression",
                               "warrant": "preference", "quote": use["source_quote"]})
        public = {"query": root["public_task"]["query"],
                  "current_context": root["public_task"]["current_context"], "memories": memory}
        select = {"status": "OK", "uses": layout, "views": {
            "WARRANT_ONLY": {"source_ids": [use["memory_id"] for use in uses]}}}
        rendered, edit = render_emphasis({"public": public}, select, answer)
        if edit is not None:
            start, end = edit["start"], edit["end"]
            if rendered != answer[:start] + "**" + answer[start:end] + "**" + answer[end:]:
                raise ValueError(f"Formatter modified non-markup content: {uid}")
        row_data = {
            "uid": uid, "explicit_source": any(BOLD_PREFERENCE.search(m["text"]) for m in memory),
            "compatible_layout_quote": any(BOLD_PREFERENCE.search(use["quote"]) for use in layout),
            "original_has_rendered_strong": visible_strong(answer, parser),
            "changed": rendered != answer, "answer_sha256": sha(answer), "replayed_answer_sha256": sha(rendered),
        }
        totals["scanned_answers"] += 1
        totals["edited_answers"] += row_data["changed"]
        totals["explicit_source"] += row_data["explicit_source"]
        totals["compatible_layout_quote"] += row_data["compatible_layout_quote"]
        totals["already_emphasized_with_layout_quote"] += (
            row_data["compatible_layout_quote"] and row_data["original_has_rendered_strong"])
        cases.append(row_data)

    # Join the native diagnostic only after rendering, never as an input to the decision.
    gap = run.read(path.with_name("STRONG_GATE_GAP.json"))
    lost = {row["uid"] for row in gap["bold_losses"]}
    lost_cases = [row for row in cases if row["uid"] in lost]
    if len(lost_cases) != len(lost):
        raise ValueError("Some known formatting losses lack a rendered draft")
    return {"totals": totals, "known_strong_gate_bold_losses": lost_cases, "cases": cases,
            "new_model_calls": 0, "native_scores_modified": 0}


if __name__ == "__main__":
    print(json.dumps(replay(), ensure_ascii=False, indent=2, sort_keys=True))
