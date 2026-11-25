"""Check that the draft contrast changes only memory exposure and keeps finals matched."""

from collections import Counter
import json
from pathlib import Path
import sys

from intervention import final_requests, parse_final, task_only_request


def main(path):
    data = json.loads(path.read_text())
    roots = data["roots"]
    if (len(roots), len({r["source_group"] for r in roots})) not in {(118, 25), (233, 43)}:
        raise ValueError("Unexpected exposure scope")
    checked = Counter()
    for root in roots:
        task_wire = task_only_request(root)
        archived_wire = root["archived_actor_request"]
        task_payload = task_wire["messages"][1]["content"]
        task_only = json.loads(task_payload)
        full = json.loads(archived_wire["messages"][1]["content"])
        assert full == {**root["public_task"], "source_evidence": root["original_sources"],
                        "preference_use_policy": root["archived_policy"]}
        assert task_only == {**full, "source_evidence": [], "preference_use_policy": []}
        assert {**task_wire, "messages": [task_wire["messages"][0], archived_wire["messages"][1]]} == archived_wire
        assert not any(source["text"] in task_payload for source in root["original_sources"]
                       if source["text"] and source["text"] not in json.dumps(root["public_task"], ensure_ascii=False))
        # Placeholders exercise the transport only. The runner must use saved and fresh real responses.
        first = "contract-test first draft"
        second = "contract-test task-only draft"
        finals = final_requests(root, archived_draft=first, task_only_draft=second)
        final_delta, final_review = finals["DELTA"], finals["REVIEW"]
        assert json.loads(final_delta["messages"][1]["content"]) == {**full, "draft_a": first, "draft_b": second}
        assert final_delta["messages"][0]["content"] != final_review["messages"][0]["content"]
        assert {**final_delta, "messages": [final_review["messages"][0], final_delta["messages"][1]]} == final_review
        response = json.dumps({"answer": "contract-test answer", "changes": [
            {"decision": "contract-test decision", "disposition": "KEEP",
             "source_ids": [root["original_sources"][0]["memory_id"]]}]})
        assert parse_final(response, root)["answer"] == "contract-test answer"
        try:
            parse_final(response.replace('"KEEP"', '"DROP_ALL"'), root)
        except ValueError:
            checked["invalid_contract_rejected"] += 1
        else:
            raise AssertionError("Unexpected invalid final accepted")
        checked["paired_wires"] += 1
    print(json.dumps({**checked, "groups": len({r["source_group"] for r in roots}), "model_requests": 0}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
