"""Attribute changes in a solved plan to source interventions, separate from answer grading."""
import json
from collections import Counter, defaultdict

from qamc.common import sha

from analyze_planning import domains_for, planning_receipts, run
from planning import MODEL, SOLVED, dominates, solve


def source_effects(plan, selections):
    """Replay each cited source's removal over unchanged model-supplied alternatives."""
    chosen = selections[SOLVED]
    model = selections[MODEL]
    domains = domains_for(plan)
    hard, soft = plan["hard"], plan["soft"]
    effects = {}
    for source in sorted({row["source_id"] for row in hard + soft} - {"TASK"}):
        source_hard = [row for row in hard if row["source_id"] == source]
        source_soft = [row for row in soft if row["source_id"] == source]
        # Removing a clause cannot affect the solve if its cited source was not used
        # as a hard guard or as an incentive on the chosen assignment.
        supports = [row for row in source_soft if chosen and dominates(chosen, row["choices"])]
        alternative = None
        if source_hard or supports:
            alternative = solve(domains, [row for row in hard if row["source_id"] != source],
                                [row for row in soft if row["source_id"] != source], model)
        effects[source] = {
            "hard_citations": len(source_hard), "soft_citations": len(source_soft),
            "choices_supported_by_soft": sorted({k for row in supports for k in row["choices"]}),
            "selection_changes_without_source": alternative is not None and alternative["selection"] != chosen,
        }
    return effects


def audit():
    frozen = run.read(run.OUT / "FROZEN.json")
    traces, _ = planning_receipts(frozen)
    archive_path = run.prior.OUT / "FROZEN.json"
    native_path = run.parent.OUT / "SETTLED.json"
    for path in (archive_path, native_path):
        key = str(path.relative_to(run.HERE.parent.parent.parent))
        if sha(path.read_bytes()) != frozen["hashes"][key]:
            raise ValueError("Frozen source or score archive changed")
    archive = run.read(archive_path)["roots"]
    native = run.read(native_path)["rows"]
    if len(archive) != len(native) or len(traces) != len(archive):
        raise ValueError("Source audit must cover the same frozen roster")
    diagnostics = set(frozen["diagnostic_source_groups"])
    totals = defaultdict(lambda: defaultdict(Counter))
    details = {}
    valid = 0
    for root, score in zip(archive, native, strict=True):
        uid = root["uid"]
        if score["uid"] != uid or score["group"] != root["group"]:
            raise ValueError("Author provenance does not align with the frozen task")
        trace = traces[uid]
        if "solver" not in trace:
            continue
        source_ids = [row["memory_id"] for row in root["original_sources"]]
        labels = score["labels"]
        if source_ids != [f"M{i}" for i in range(len(labels))] or set(labels) - {"A", "B", "C"}:
            raise ValueError("Original source ordering does not align with author positions")
        valid += 1
        effects = source_effects(trace["plan"], trace["selections"])
        panes = ["all"]
        if set(labels) == {"A"}:
            panes.append("all_A")
        if "C" in labels:
            panes.append("contains_C")
        if root["group"] not in diagnostics:
            panes.append("outside_documented_diagnostics")
        selected = trace["selections"][SOLVED]
        details[uid] = {"source_group": root["group"], "has_solution": selected is not None,
                        "changed_selection": selected != trace["selections"][MODEL], "sources": effects}
        for pane in panes:
            for src, label in zip(source_ids, labels, strict=True):
                observation = effects.get(src, {})
                row = totals[pane][label]
                row["author_positions"] += 1
                row["hard_cited"] += bool(observation.get("hard_citations"))
                row["soft_cited"] += bool(observation.get("soft_citations"))
                row["selected_soft"] += bool(observation.get("choices_supported_by_soft"))
                row["fixed_plan_selection_sensitive"] += bool(observation.get("selection_changes_without_source"))
    return {"assigned": len(traces), "valid_plans": valid, "source_effect_by_author_label": totals, "per_case": details}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
