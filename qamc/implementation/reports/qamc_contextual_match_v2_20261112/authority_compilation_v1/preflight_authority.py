"""Check wire equality on archived development inputs and the compiler's structural limits."""
from collections import Counter
import json

from authority import compile_answer, compile_public, personal_wires, public_wire
from preflight import public_roots


def check():
    public = compile_public(json.dumps({"blocks": [
        {"id": "P1", "kind": "fixed", "text": "A fixed passage."},
        {"id": "D1", "kind": "decision", "target": "fixture", "goal": "fixture",
         "text": "No preference assumed."},
    ]}))
    counts = Counter()
    memories = [{"memory_id": "M1", "text": "Exact source excerpt."}]
    for benchmark, root in public_roots():
        base = public_wire(root)
        assert json.loads(base["messages"][1]["content"]) == {"task": root["public_task"]}
        assert base == public_wire({**root, "original_sources": memories})
        wires = personal_wires(root, public)
        assert wires["GENERIC"]["messages"][1] == wires["AUTHORITY"]["messages"][1]
        for wire in wires.values():
            assert {k: v for k, v in wire.items() if k != "messages"} == {
                k: v for k, v in base.items() if k != "messages"
            }
            assert json.loads(wire["messages"][1]["content"])["source_evidence"] == root["original_sources"]
        counts[benchmark] += 1
    assert counts == {"RPEval": 233, "BenchPreS": 48, "PersistBench": 58}, counts

    operation = {"id": "D1", "text": "A supported decision.", "source_id": "M1", "quote": "Exact source"}
    task = {"query": "Write the answer.", "current_context": "", "facts": []}

    def answer(ops, emphasis):
        raw = json.dumps({"decisions": ops, "emphasis": emphasis})
        return compile_answer(task, public, raw, memories)

    assert answer([operation], []) == "A fixed passage.\n\nA supported decision."
    assert answer([], [{**operation, "id": "P1", "text": "fixed passage"}]) == (
        "A **fixed passage**.\n\nNo preference assumed."
    )
    for change in ({"id": "P1"}, {"id": "D2"}, {"quote": "invented"}, {"text": "first\nsecond"}):
        try:
            answer([{**operation, **change}], [])
        except ValueError:
            continue
        raise AssertionError("Invalid operation accepted")
    assert public["blocks"][0]["text"] == "A fixed passage."
    return {"exposed_wires": counts, "compiler_fixture_checks": 7, "new_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
