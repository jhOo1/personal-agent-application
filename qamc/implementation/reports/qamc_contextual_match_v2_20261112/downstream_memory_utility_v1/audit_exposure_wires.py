"""Rebuild three archived Actor exposure wires. No score or response is printed."""
import json

import qamc_paper_baseline_validation_run as source

from exposure_wires import rendered_projection, rp_projection


def verify_rpe(directory):
    rows = source.read(directory / "rpeval_formal_multi_coverage_v1" / "RESULT_ROWS.json")
    count = 0
    for record in rows:
        if record["method"] != "RPR_PAPER_FULL" or not record.get("actor_request"):
            continue
        wire = record["actor_request"]
        body = json.loads(wire["messages"][1]["content"])
        if rp_projection(wire, range(len(body["source_evidence"]))) != wire:
            raise ValueError("Full projection changed the archived RP request")
        empty = rp_projection(wire, [])
        task = {**body, "source_evidence": [], "preference_use_policy": []}
        if json.loads(empty["messages"][1]["content"]) != task or empty["messages"][0] != wire["messages"][0]:
            raise ValueError("Empty projection changed RP task facts or system")
        count += 1
    return count


def verify_rendered(rows, bridge, method, *, bench_cases=None):
    bench = bench_cases is not None
    template = bridge.blobs["GEPA" if bench else "RUBRIC"].decode()
    count = 0
    for record in rows:
        if (record["method"] != method or not record.get("actor_request")
                or (bench and record["benchmark"] != "benchpres")):
            continue
        wire = record["actor_request"]
        view = record["view"]
        if bench:
            task = source.task_for(bench_cases[record["uid"]])
            original = [m.text for m in task.memories]
            positions_by_id = {m.memory_id: i for i, m in enumerate(task.memories)}
            exposure = [positions_by_id[item["memory_id"]] for item in view["source_evidence"]]
            if [original[i] for i in exposure] != [item["text"] for item in view["source_evidence"]]:
                raise ValueError("Archived BenchPreS source differs from original task memory")
        else:
            original = view["original_memory_texts"]
            exposure = range(len(original))
        def render(memory):
            return bridge.render(memory, wire["model"], template)
        guide = {} if bench else None
        full = rendered_projection(wire, original, exposure, render, archived_positions=exposure, bench_guidance=guide)
        if full != wire:
            raise ValueError("Full projection changed the archived rendered Actor request")
        empty = rendered_projection(wire, original, [], render, archived_positions=exposure, bench_guidance=guide)
        if empty["messages"][0]["content"] != render([]):
            raise ValueError("Empty projection failed the frozen renderer")
        if bench:
            public = json.loads(wire["messages"][1]["content"])
            public.pop("selected_memory_use_guidance", None)
            if json.loads(empty["messages"][1]["content"]) != public:
                raise ValueError("Empty projection changed the Strong Gate task")
        elif empty["messages"][1] != wire["messages"][1]:
            raise ValueError("Empty projection changed the PersistBench task")
        count += 1
    return count


def audit():
    directory = source.OUT.parent
    bridge = source.PersistAuthorBridge(source.previous.parent.AUTHOR)
    bench = source.read(source.OUT / "RESULT_ROWS.json")
    bench_cases = {row["uid"]: row for row in source.read(source.OUT / "PLAN.json")["cases"]
                   if row["benchmark"] == "benchpres" and not row["independent_confirmation"]}
    paths = sorted((directory / "persist_author_controls_v2" / "waves").glob("[0-9][0-9].json"))
    persist = [r for p in paths for r in source.read(p)["rows"]]
    counts = {
        "RPEval_RP": verify_rpe(directory),
        "BenchPreS_Strong_Gate": verify_rendered(bench, bridge, "GEPA_SELECTED_BOUNDS", bench_cases=bench_cases),
        "PersistBench_PB_RUBRIC": verify_rendered(persist, bridge, "PB_RUBRIC"),
    }
    if not all(counts.values()):
        raise ValueError("Expected nonempty archived wires for all three benchmarks")
    return {"archived_full_exact_empty_verified": counts, "new_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
