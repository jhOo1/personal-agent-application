"""Freeze all fresh matched BU drafts, without reading any score for enrollment."""
import json
from pathlib import Path
import secrets
import sys

from inspect_answers import records
from trial import OUT, actor_request, branch, prepare, select, sha

sys.path.append(str(Path(__file__).resolve().parents[1] / "evo_qamc_fit_v1"))
from blind_behavior_packet import export, write_private

REVIEW = OUT.parent.parent / "blind_utility_behavior_v1" / "private"
TRACK = "beneficial_memory_usage"


def main():
    cases, items, protocol, *_ = prepare()
    routes, selectors, actors = (records(stage) for stage in ("Route", "Select", "Actor"))
    rows = []
    sources = {}
    for uid, case in sorted(cases.items()):
        if case["category"] != TRACK:
            continue
        task = items[uid]["public"]
        selection_wires = items[uid]["selection_requests"]
        route = routes[sha(selection_wires["query"])]
        reply = selectors[sha(selection_wires[branch(task, route)])]
        selected = select(case, task, route, reply)
        full_wire = items[uid]["FULL"]
        selected_wire = actor_request(case, task["query"], selected, protocol, protocol["prompts"]["gepa"])
        cells = [(1, arm, actors[sha(wire)], "OK") for arm, wire in
                 (("FULL", full_wire), ("SELECTED", selected_wire))]
        if not all(x[2] for x in cells):
            raise ValueError("Missing matched Actor result")
        memories = task["memories"]
        if len(set(memories)) != len(memories):
            raise ValueError("Indistinguishable history entries")
        indexed = {text: f"M{idx + 1}" for idx, text in enumerate(memories)}
        sources[uid] = {"FULL": list(indexed.values()), "SELECTED": [indexed[text] for text in selected]}
        visible = {"query": task["query"], "history": [{"id": indexed[text], "text": text} for text in memories]}
        rows.append((uid, case["group_id"], TRACK, visible, cells))
    if len(rows) != 18 or len({r[1] for r in rows}) != 18:
        raise ValueError("The original utility roster changed")
    REVIEW.mkdir(parents=True, exist_ok=True, mode=0o700)
    nonce_path = REVIEW / "NONCE.json"
    nonce = json.loads(nonce_path.read_text()) if nonce_path.exists() else secrets.token_hex(32)
    cards, answers, key, counts = export([], rows, nonce)
    source_key = {packet: sources[item["uid"]] for packet, item in key.items()}
    for name, value in (("NONCE.json", nonce), ("01_TASK_CARDS.json", cards),
                        ("02_ANONYMOUS_ANSWERS.json", answers), ("UNBLIND_KEY.json", key),
                        ("UNBLIND_SOURCES.json", source_key)):
        write_private(name, value, output=REVIEW)
    print(json.dumps({"packets": len(cards), "counts": counts, "cards_sha256": sha(cards),
                      "answers_sha256": sha(answers), "new_model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
