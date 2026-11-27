"""Offline qualification of the exposed strong-draft panel and isolated writer contract."""
import json
from collections import Counter
from pathlib import Path

import operand_inputs as old
import run_matched_alternatives as mag
from delta import index
from qamc.common import sha

HERE = Path(__file__).resolve().parent


def faithful_sources(raw):
    if isinstance(raw, list):
        return {f"S{i}": item for i, item in enumerate(raw, 1)}
    if isinstance(raw, dict):
        return {f"S{i}": {k: v} for i, (k, v) in enumerate(raw.items(), 1)}
    if raw is None:
        return {}
    if isinstance(raw, str):
        return {"S1": raw} if raw else {}
    raise ValueError("Unrecognized source representation")


def record(domain, uid, group, task, draft):
    return {"uid": uid, "group": group, "domain": domain, "draft": draft, "units": index(draft),
            "task": {k: task[k] for k in ("query", "current_context") if k in task},
            "facts": faithful_sources(task.get("facts")),
            "history": faithful_sources(task["history"])}


def roster():
    cards = []
    for uid, row in mag.cards().items():
        cards.append(record("RPEval", uid, row["source_group"], row["task"], row["answer"]))
    for name, row in {**old.bench_cards(), **old.persist_cards()}.items():
        cards.append(record(name.split("/")[0], row["uid"], row["group"],
                            {**row["context"], "history": row["history"]}, row["draft"]))
    if len({row["uid"] for row in cards}) != 29 or any(not row["task"].get("query") for row in cards):
        raise ValueError("Expected the complete existing 13/8/8 exposed panels and their original queries")
    return cards


def writer_input(row, decision, targets, fact_ids, history_ids, arm):
    """The history-informed binder supplies only IDs; its prose cannot enter the writer."""
    units = {unit["id"]: unit for unit in row["units"]}
    if not targets or len(set(targets)) != len(targets) or len(targets) > 3:
        raise ValueError("Expected one decision with one to three distinct write locations")
    if any(t not in units or units[t]["kind"] == "fixed" for t in targets):
        raise ValueError("Unknown or immutable write location")
    if len(targets) == len(units):
        raise ValueError("Whole-answer replacement is outside the local comparison")
    payload = {"task": row["task"], "decision": decision,
               "bound_facts": {i: row["facts"][i] for i in fact_ids},
               "bound_history": {i: row["history"][i] for i in history_ids},
               "locations": [{"id": k, "kind": unit["kind"]} for k, unit in units.items() if k in targets]}
    if arm == "LOCAL_EDIT":
        payload["original_units"] = row["units"]
    elif arm != "ISOLATED":
        raise ValueError("Unknown writer")
    return payload


def commit_cells(row, targets, replacements):
    if set(replacements) != set(targets) or any(not isinstance(s, str) or not s.strip() for s in replacements.values()):
        raise ValueError("Partial replacement or empty content")
    pieces = []
    for unit in row["units"]:
        text = unit["text"]
        if unit["id"] in targets:
            if unit["kind"] == "fixed":
                raise ValueError("Fixed unit")
            leading = text[:len(text) - len(text.lstrip())]
            trailing = text[len(text.rstrip()):]
            text = leading + replacements[unit["id"]].strip() + trailing
        pieces.append(text)
    return "".join(pieces)


def check():
    panel = roster()
    inventory = {}
    for row in panel:
        if "".join(u["text"] for u in row["units"]) != row["draft"]:
            raise ValueError("Draft indexing drift")
        targets = [u["id"] for u in row["units"] if u["kind"] != "fixed"][:1]
        if not targets or len(row["units"]) == 1:
            state = "no_local_region"
        else:
            placeholder = "CONTRACT CHECK"
            inputs = [writer_input(row, placeholder, targets, [], [], arm) for arm in ("ISOLATED", "LOCAL_EDIT")]
            assert set(inputs[1]) - set(inputs[0]) == {"original_units"}
            assert {k: inputs[1][k] for k in inputs[0]} == inputs[0]
            original = next(u["text"] for u in row["units"] if u["id"] == targets[0])
            assert commit_cells(row, targets, {targets[0]: original}) == row["draft"]
            state = "local_region_available"
        inventory.setdefault(row["domain"], Counter())[state] += 1
    return {"rows": len(panel), "by_domain": inventory, "new_model_requests": 0,
            "input_sha256": sha(panel), "scope": "mechanical qualification only"}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
