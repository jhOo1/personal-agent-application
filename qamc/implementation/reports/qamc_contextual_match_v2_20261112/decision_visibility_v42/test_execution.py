"""Exercise the complete frozen wave without an API call."""
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from qamc.common import sha

import run_visibility_v42 as run
from audit_visibility_v42 import analyze


def main():
    archive = run.read(run.prior.OUT / "FROZEN.json")
    original = run.read(run.prior.formal.OUT / "PLAN.json")
    known = {row["uid"]: row for row in archive["roots"]}
    plan = run.read(run.OUT / "FROZEN.json")
    cases = run.prior.author_cases(original)
    roots = [known[uid] for uid in plan["waves"][0]]
    previous = run.old_receipts(archive)
    counts = Counter()

    def dispatch(_, stage, spec):
        for record in spec["units"]:
            unit, body = record["unit"], record["request"]
            uid = unit["root_id"]
            folder = run.PROBE.RUN / stage / "visible" / run.PROBE.sampling_key(unit)
            if (folder / "record.json").exists():
                continue
            counts[stage] += 1
            if stage == run.SELECTOR:
                packet = json.loads(body["messages"][1]["content"])
                assert set(packet) == {"query", "current_context", "facts", "source_evidence"}
                first = packet["source_evidence"][0]
                choice = {"id": "D1", "anchor": packet["query"][:35], "beneficiary": "fixture"}
                use = {"memory_id": first["memory_id"], "decision_id": "D1", "level": "B",
                       "source_quote": first["text"][:24]}
                answer = json.dumps({"decisions": [choice], "uses": [] if unit["method"] == "SCOPED" else [use]},
                                    ensure_ascii=False)
            elif stage == run.ACTOR:
                packet = json.loads(body["messages"][1]["content"])
                assert "intent_type" not in packet
                answer = "offline fixture " + sha(body)
            else:
                n = len(known[uid]["original_sources"])
                answer = json.dumps({"match": f"{n}/{n}", "full_match": True, "OPB": 0, "UPB": 0, "FM": 0})
            run.PROBE.atomic_json(folder / "response.json", {"answer": answer})
            run.PROBE.atomic_json(folder / "record.json", {
                "unit": unit, "status": "OK", "usage": None, "request_sha256": sha(body),
            })

    with TemporaryDirectory() as tmp, patch.object(run.prior, "dispatch", side_effect=dispatch):
        study, runtime = Path(tmp) / run.OUT.name, Path(tmp) / "runtime"
        out, files = study / "wave_00", runtime / "wave_00"
        run.PROBE.OUT, run.PROBE.RUN = out, files
        first = run.evaluate(plan, "wave_00", roots, {k: v.copy() for k, v in previous.items()}, True, cases, original)
        assert len(first["rows"]) == 4
        assert counts[run.SELECTOR] == 8
        assert len(run.read(out / (run.ACTOR + "_REUSE.json"))) >= 4
        assert len(run.read(out / (run.JUDGE + "_REUSE.json"))) >= 2
        snapshot = counts.copy()
        resumed = run.evaluate(plan, "wave_00", roots, {k: v.copy() for k, v in previous.items()}, True, cases, original)
        assert resumed == first and counts == snapshot
        for case in first["rows"]:
            assert case["answers"]["SCOPED_MASKED"]["visible_ids"] == []
            assert case["selected"]["SCOPED"]["scope"] == []
            assert len(case["answers"]["SCOPED_FULL"]["visible_ids"]) == case["positions"]
        run.PROBE.freeze(study / "FROZEN.json", plan)
        run.PROBE.freeze(out / "COMPLETED.json", first)
        with patch.object(run, "OUT", study), patch.object(run, "RUN", runtime):
            verified = analyze()
            assert verified["checked"]["roots"] == 4
            assert verified["visibility"]["different_actor_wire"] == 4
            pair = "SCOPED_FULL__SCOPED_MASKED"
            for track, metrics in verified["source_track_pairs"].items():
                by_label = verified["source_track_label_pairs"][track]
                assert sum(t[pair]["expected_cases"] for t in by_label.values()) == metrics[pair]["expected_cases"]
    print("Four real benchmark inputs replayed offline. Phase isolation, exact inherited reuse, and resume passed.")


if __name__ == "__main__":
    main()
