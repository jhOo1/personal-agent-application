"""Measure the known part of one-selector routes without generating or scoring responses."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import sha

from cost_policy_override_v43 import parent_selection
import run_policy_override_v43 as stage

RP = stage.prior.RP


def audit():
    plan, roots = stage.prepare()
    terminal = stage.OUT / "COMPLETED.json"
    if (stage.read(stage.OUT / "RUN_STATE.json")["state"] != "COMPLETE"
            or plan != stage.read(stage.OUT / "FROZEN.json")):
        raise ValueError("Archived V43 intervention is not terminal and pinned")
    results = stage.read(terminal)
    if [r["uid"] for r in results["rows"]] != [r["uid"] for r in plan["roots"]]:
        raise ValueError("V43 settled sample changed")
    parent, _ = parent_selection(plan)
    old = {}
    for item in plan["input_sources"]:
        dump = stage.read(stage.v42.OUT / f"wave_{item['wave']:02d}" / "COMPLETED.json")
        old.update({row["uid"]: row for row in dump["rows"]})

    tables = {}
    for method in ("DIRECT", "SCOPED"):
        outcome, counts = [], Counter()
        alt = "one_selector"
        for row in results["rows"]:
            uid, root = row["uid"], roots[row["uid"]]
            chosen = parent[uid][method]
            edits, _ = stage.candidate(root, {"DIRECT": chosen, "SCOPED": chosen})
            digest = sha(stage.policy_only_request(root, edits))
            reference = root["archived"][RP]
            options = [
                (root["archived_actor_sha256"], reference["answer"], row["native"][RP]),
                (row["trace"]["actor_sha256"], row["answer"], row["native"][stage.METHOD]),
                *((v.get("request_sha256"), v["answer"], old[uid]["native"][arm])
                  for arm, v in old[uid]["answers"].items()),
            ]
            matching = [(answer, cell) for key, answer, cell in options if key == digest and answer]
            fingerprints = {sha([answer, cell["raw"], cell["fields"]]) for answer, cell in matching}
            counts["duplicated_wire_different_archived_observation"] += len(fingerprints) > 1
            if digest == root["archived_actor_sha256"] or digest == row["trace"]["actor_sha256"]:
                owner = RP if digest == root["archived_actor_sha256"] else stage.METHOD
                cell = {**row["native"][owner], "reuse": owner}
                state = "native_match_known" if cell["fields"].get("match") is not None else "native_match_missing"
            elif not matching:
                state, cell = ("archived_response_missing" if any(digest == key for key, _, _ in options)
                               else "new_actor_wire"), {"fields": {}}
            elif len(fingerprints) > 1:
                state, cell = "archived_replay_conflict", {"fields": {}}
            else:
                cell = matching[0][1]
                state = "native_match_known" if cell["fields"].get("match") is not None else "native_match_missing"
            counts[state] += 1
            counts["identical_to_RP_wire"] += digest == root["archived_actor_sha256"]
            counts["identical_to_V43_wire"] += digest == row["trace"]["actor_sha256"]
            outcome.append({**row, "native": {**row["native"], alt: cell}, "replay_state": state,
                            "projected_actor_sha256": digest})
        measures = {
            tag: {m: stage.v42.paired(rows, m, alt) for m in (RP, stage.METHOD, stage.prior.GATE)}
            for tag, rows in (
                ("all", outcome),
                ("all_A", [r for r in outcome if set(r["labels"]) == {"A"}]),
                ("contains_BC", [r for r in outcome if set(r["labels"]) != {"A"}]),
            )
        }
        tables[method] = {"coverage": counts, "strict_paired_only": measures}
    return {"roots": len(results["rows"]), "source_groups": len({r["group"] for r in results["rows"]}),
            "v43_terminal_sha256": sha(terminal.read_bytes()), "projections": tables, "new_model_calls": 0,
            "scope": ("Use the exact original RP outcome for no-op and the measured V43 outcome for "
                      "opaque but identical interventions. Otherwise only a same-case, identical cached Actor "
                      "request with an unambiguous outcome may be replayed. "
                      "All unsupported outputs remain missing; paired subsets are not whole-panel results.")}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    position = parser.parse_args().output
    report = audit()
    if position:
        with position.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
