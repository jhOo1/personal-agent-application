"""Offline replay of the actual wave wiring using frozen public cases."""
from collections import Counter
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from unittest.mock import patch

from qamc.common import sha
from run_v41 import DRAFT, FINAL, NATIVE, OUT, evaluate, probe, read, shared_drafts, smoke_check


def main():
    plan = read(OUT / "FROZEN.json")
    uids = plan["waves"][0]
    by_uid = {r["uid"]: r for r in plan["roots"]}
    panel = {**plan, "roots": [by_uid[uid] for uid in uids]}
    counts = Counter()

    def local_dispatch(_, stage, manifest):
        for job in manifest["units"]:
            counts[stage] += 1
            unit, request = job["unit"], job["request"]
            uid, arm = unit["root_id"], unit["method"]
            folder = probe.RUN / stage / "visible" / probe.sampling_key(unit)
            if stage == DRAFT:
                answer = f"offline draft {uid}"
            elif stage == FINAL:
                payload = json.loads(request["messages"][1]["content"])
                assert payload["draft_b"] == f"offline draft {uid}"
                assert "intent_type" not in payload
                answer = json.dumps({"answer": f"offline answer {uid} {arm}", "changes": []})
            else:
                assert f"offline answer {uid} {arm}" in request["messages"][1]["content"]
                assert "offline draft" not in request["messages"][1]["content"]
                n = len(by_uid[uid]["archived_policy"])
                answer = json.dumps({"match": f"{n}/{n}", "full_match": True, "OPB": 0, "UPB": 0})
            probe.atomic_json(folder / "response.json", {"answer": answer})
            probe.atomic_json(folder / "record.json", {"unit": unit, "status": "OK", "usage": None,
                                                      "request_sha256": sha(request)})

    with TemporaryDirectory() as td:
        temp = Path(td)
        with patch.multiple(probe, OUT=temp / "out", RUN=temp / "run"), patch(
                "run_v41.dispatch", side_effect=local_dispatch):
            output = evaluate(panel, "smoke", {}, live=True)
            assert counts == {DRAFT: 4, FINAL: 8, NATIVE: 8}
            assert smoke_check(output) == {"paired_answer_contracts": 4, "paired_native_contracts": 4, "pass": True}
            assert evaluate(panel, "smoke", {}, live=False) == output
            assert counts == {DRAFT: 4, FINAL: 8, NATIVE: 8}
            saved_drafts = read(probe.OUT / "DRAFT_RESULTS.json")
            prior = next(iter(saved_drafts.values()))
            duplicate = {**by_uid[prior["uid"]], "uid": "offline aliased task-only wire"}
            shutil.move(probe.OUT, temp / "smoke_out")
            replayed, aliases = shared_drafts({**plan, "roots": [duplicate]}, "alias", saved_drafts, True)
            assert aliases == {duplicate["uid"]: prior["uid"]} and replayed == saved_drafts
            assert counts[DRAFT] == 4
    print("Offline smoke replay, native answer-only scoring, and cross-wave exact reuse passed.")


if __name__ == "__main__":
    main()
