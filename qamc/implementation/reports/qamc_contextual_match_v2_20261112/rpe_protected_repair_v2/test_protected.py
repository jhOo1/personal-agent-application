import json
import unittest

from protected import apply, exact_span, locate


class ProtectedRepairTests(unittest.TestCase):
    def setUp(self):
        self.draft = "路线甲。\n旧选项。\n保留✅。\n旧总结。\n注意事项。"
        self.packet = {"context": {"query": "请安排路线", "history": ["曾明确排除旧方案"],
                                   "facts": [], "current_context": ""},
                       "default_id": "B", "candidates": {"B": self.draft}}
        self.plan = {"mode": "ACT", "reason": "两个决定冲突",
                     "evidence": {"origin": "HISTORY", "quote": "排除旧方案"},
                     "targets": [{"op": "REPLACE", "quote": "旧总结。"},
                                 {"op": "DELETE", "quote": "旧选项。\n"}]}

    def locator(self):
        return locate(json.dumps(self.plan), self.packet)

    def test_atomic_delete_and_replace_preserve_unicode(self):
        diagnosis = self.locator()
        self.assertEqual(diagnosis["targets"][0]["quote"], "旧选项。\n")
        edits = {"mode": "PATCH", "edits": [{"id": "T2", "text": "新总结。"}, {"id": "T1", "text": ""}]}
        self.assertEqual(apply(json.dumps(edits), self.packet, diagnosis, "PATCH"),
                         "路线甲。\n保留✅。\n新总结。\n注意事项。")
        edits["edits"].pop()
        with self.assertRaises(ValueError):
            apply(json.dumps(edits), self.packet, diagnosis, "PATCH")

    def test_enrich_keeps_original(self):
        self.plan["targets"] = [{"op": "ENRICH", "quote": "路线甲。"}]
        edits = '{"mode":"PATCH","edits":[{"id":"T1","text":" 备用新方案。"}]}'
        self.assertEqual(apply(edits, self.packet, self.locator(), "PATCH"),
                         self.draft.replace("路线甲。", "路线甲。 备用新方案。"))

    def test_rejects_overlapping_repeated_or_absent_quotes(self):
        self.plan["targets"].append({"op": "DELETE", "quote": "旧选项。\n保留"})
        with self.assertRaises(ValueError):
            self.locator()
        for case, quote in (("aaaa", "aaa"), ("x-y-x", "x"), ("one", "two")):
            with self.assertRaises(ValueError):
                exact_span(case, quote)

    def test_wrong_source_and_whole_answer(self):
        self.plan["evidence"]["origin"] = "TASK"
        with self.assertRaises(ValueError):
            self.locator()
        self.plan["evidence"]["origin"] = "HISTORY"
        self.plan["targets"] = [{"op": "REPLACE", "quote": self.draft}]
        with self.assertRaises(ValueError):
            self.locator()

    def test_free_can_make_a_complete_revision_and_both_can_abstain(self):
        for arm in ("FREE", "PATCH"):
            self.assertEqual(apply('{"mode":"KEEP"}', self.packet, self.locator(), arm), self.draft)
        self.assertEqual(apply('{"mode":"REWRITE","answer":"新路线。"}',
                               self.packet, self.locator(), "FREE"), "新路线。")
        with self.assertRaises(ValueError):
            apply('{"mode":"REWRITE","answer":"新路线。"}', self.packet, self.locator(), "PATCH")


if __name__ == "__main__":
    unittest.main()
