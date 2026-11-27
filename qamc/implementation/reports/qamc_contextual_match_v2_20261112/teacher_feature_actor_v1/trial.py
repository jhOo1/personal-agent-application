"""Matched direct generation on frozen IPE-C evidence and exposed roots."""
import json
import sys
from copy import deepcopy
from pathlib import Path
import run_rpe_fixed_route_actor as runner

HERE = Path(__file__).resolve().parent
original_prepare = runner.prepare
original_panel = runner.PANEL
EXAMPLES = {
    "TASK_FEATURE": "A traveler wants to learn Spanish for a trip. A language app already on the shortlist offers short game-like exercises and pronunciation playback. Explain how these features help rehearse travel phrases and practice speaking before departure.",
    "MEMORY_FEATURE": "A traveler wants to learn Spanish for a trip. The traveler enjoys game-like practice and cares about pronunciation. A language app already on the shortlist offers short game-like exercises and pronunciation playback. Explain how these features fit those preferences.",
}
PREFIX = "\n\nIllustration from a different task, for the writing approach only. "


def prepare():
    previous, wires, roots = original_prepare()
    if previous != runner.read(original_panel):
        raise ValueError("Prior panel drift")
    archive = runner.read(runner.HERE.parent / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")
    donor, = [r for r in archive["rows"] if r["uid"].endswith("/implicit/067")]
    cases, jobs = [], {}
    for stratum in runner.QUOTAS:
        eligible = [r for r in previous["cases"] if r["stratum"] == stratum
                    and r["source_group"] != donor["source_group"]]
        for row in sorted(eligible, key=lambda r: runner.sha(["teacher-feature-v1", r["uid"]]))[:3]:
            uid = row["uid"]
            wire = dict(wires[uid, runner.METHOD], model="qwen3.8-flash")
            if runner.sha(wire) != row["qwen_request_sha256"]:
                raise ValueError("Original generation request mismatch")
            cases.append(row)
            for arm, example in EXAMPLES.items():
                enriched = deepcopy(wire)
                enriched["messages"][0]["content"] += PREFIX + example
                jobs[uid, arm] = enriched
    assert len(cases) == 9 and len({r["source_group"] for r in cases}) == 9
    jobs = dict(sorted(jobs.items(), key=lambda item: runner.sha(list(item[0]))))
    return {"cases": cases, "demo_sha256": runner.sha(EXAMPLES),
            "job_hashes": [runner.sha(w) for w in jobs.values()]}, jobs, roots


runner.OUT = HERE / "receipts"
runner.RUN = runner.RUN.with_name(HERE.name)
runner.PANEL = HERE / "PANEL.json"
runner.prepare = prepare
if __name__ == "__main__":
    if sys.argv[1:] == ["freeze"]:
        runner.probe.freeze(runner.PANEL, prepare()[0])
    elif sys.argv[1:] == ["run"]:
        runner.run()
    else:
        raise SystemExit("Use freeze or run")
