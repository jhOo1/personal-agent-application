"""Replay frozen cohort joins with a local transport fixture and no API access."""
from collections import Counter
import json
import unittest

from qamc.common import sha

import run_decision_edit as runner


class OfflineIntegration(unittest.TestCase):
    def test_exact_reuse_and_new_native_grading_paths(self):
        plan, roots, payloads, jobs = runner.prepare("OFFLINE_TEST")
        altered, broken, missing, *_ = payloads
        base = payloads[altered]["original_answer"]
        t = next(text for text in runner.edit.task_text(payloads[altered]["task"]) if len(text) > 5)
        before = base[:min(30, len(base) // 2)]
        edit_reply = json.dumps({"edits": [{"before": before, "after": before + " [offline fixture]",
                                              "task_quote": t, "memory": None, "role_quote": None}]})
        calls = Counter()

        def stage(name, dispatched):
            calls[name] += len(dispatched)
            if name == runner.JUDGE:
                uid, method, wire = dispatched[0]
                self.assertEqual(len(dispatched), 1)
                self.assertEqual((uid, method), (altered, runner.DECISION))
                self.assertTrue(any("[offline fixture]" in m["content"] for m in wire["messages"]))
                self.assertEqual(len(runner.v42.manifest("test", name, dispatched)["units"]), 1)
                return {(uid, method): ({"request_sha256": sha(wire), "status": "OFFLINE_JUDGE_FAILURE"}, None)}
            self.assertEqual(name, runner.EDIT)
            self.assertEqual(len(runner.v42.manifest("test", name, dispatched)["units"]), len(jobs))
            replies = {}
            for uid, method, wire in dispatched:
                record, raw = {"request_sha256": sha(wire), "status": "OK"}, '{"edits":[]}'
                if method == runner.DECISION and uid == altered:
                    raw = edit_reply
                if method == runner.DECISION and uid == broken:
                    raw = "invalid-json"
                if method == runner.DECISION and uid == missing:
                    record["status"], raw = "OFFLINE_TRANSPORT_FAILURE", None
                replies[uid, method] = record, raw
            return replies

        rows = runner.evaluate((plan, roots, payloads, jobs), stage)
        self.assertEqual((len(rows), len(payloads), calls[runner.EDIT], calls[runner.JUDGE]), (233, 227, 454, 1))
        indexed = {r["uid"]: r for r in rows}
        self.assertEqual(indexed[altered]["edits"][runner.DECISION]["transaction"], "APPLIED")
        self.assertEqual(indexed[altered]["native"][runner.DECISION]["status"], "OFFLINE_JUDGE_FAILURE")
        for uid, status in [(broken, "INVALID_EDIT_CONTRACT"), (missing, "OFFLINE_TRANSPORT_FAILURE")]:
            self.assertEqual(indexed[uid]["edits"][runner.DECISION]["status"], status)
            self.assertFalse(indexed[uid]["native"][runner.DECISION]["fields"])
        report = runner.report(plan, rows, [])
        self.assertEqual(report["native_grade_reused"], {runner.GENERIC: 227, runner.DECISION: 224})
        self.assertFalse(report["screen_pass"])
        print("Offline only: 233 rows, 454 edit fixtures, 451 prior-score joins, 1 changed-answer grade fixture, "
              "1 malformed edit and 1 delivery failure preserved. No network or new grades.")


if __name__ == "__main__":
    unittest.main()
