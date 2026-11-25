"""Check previously exposed Actor requests without writing data or calling models."""
from collections import Counter
from pathlib import Path
import json

from baselines import archive
from qamc.common import sha
from residual import actor_wire, atomic

BASE = Path(__file__).resolve().parents[1]


def inspect(benchmark, rows, expected, *, route=None, task_only=None):
    tested = Counter()
    for row in rows:
        uid = row["uid"]
        if uid not in expected or not row.get("actor_request"):
            continue
        if row.get("actor_status") != "OK":
            continue
        wire, digest = row["actor_request"], row["actor_request_sha256"]
        enabled = route is None or route[uid] == "REUSE_RP"
        assert actor_wire(wire, digest, (), history_enabled=enabled) is wire
        changed = actor_wire(wire, digest, atomic((), "ADD", 0, "Keep explicit requirements."),
                             history_enabled=enabled)
        if enabled:
            systems = [i for i, msg in enumerate(wire["messages"]) if msg["role"] == "system"]
            assert len(systems) == 1
            changed["messages"][systems[0]] = wire["messages"][systems[0]]
            assert changed == wire and sha(wire) == digest
            tested["mutable_actor_wires"] += 1
        else:
            task_wire, task_digest = task_only(row)
            assert actor_wire(task_wire, task_digest, ("Keep explicit requirements.",),
                              history_enabled=False) is task_wire
            tested["verified_task_only_wires"] += 1
    if not tested:
        raise ValueError(f"No qualifying {benchmark} Actor wires")
    return tested


def main():
    rpe_original = archive.read(archive.v41.formal.OUT / "PLAN.json")
    if any(row["independent_confirmation"] for row in rpe_original["cases"]):
        raise ValueError("Unexpected confirmation cohort")
    rpe_cases = archive.v41.author_cases(rpe_original)
    route = {row["uid"]: row["old_route"] for row in
             archive.read(BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]
             if row["uid"] in rpe_cases}
    rp_rows = [row for row in archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json")
               if row["method"] == archive.engine.RP]
    frozen = {r["uid"]: r for r in archive.read(
        BASE / "ipe_c_full_exposed_panel_v1" / "FROZEN.json")["rows"]}
    ranks = {r["uid"]: r for r in archive.read(
        archive.v41.formal.OUT / "RPR_RANK_FUSION_AUDIT_300.json")["rows"]}

    def task_only(row):
        uid = row["uid"]
        # Use the original panel constructor, including its ranking-bound view.
        from replay_panel import source_root
        wire = archive.v41.task_only_request(source_root(row, ranks[uid]))
        return wire, frozen[uid]["task_only_request_sha256"]

    output = {"RPEval": inspect("RPEval", rp_rows, route, route=route, task_only=task_only)}
    for benchmark, method in (("BenchPreS", archive.engine.GATE), ("PersistBench", "PB_RUBRIC")):
        cases, _, _ = archive.transfer.context(benchmark)
        roots = {row["uid"] for row in archive.transfer.development_roots(benchmark)}
        rows = [row for row in archive.transfer.archived_answers(benchmark, cases)
                if row["method"] == method]
        output[benchmark] = inspect(benchmark, rows, roots)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
