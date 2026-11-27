import json
import unittest

from action_commit import submit


class ActionCommitTest(unittest.TestCase):
    def setUp(self):
        self.candidates = {
            "T": ("原任务。\n\n", "旧地点。\n\n", "旧邀请。\n\n", "保留 ID-125。"),
            "A": ("另一个开头。\n\n", "新地点。\n\n", "新邀请。\n\n", "新结尾。"),
        }
        self.edit = {"mode": "COMMIT", "base": "T", "donor": "A",
                     "replacements": [{"base": [1, 3], "donor": [1, 3]}]}

    def test_copies_dependent_ranges_and_preserves_untouched_bytes(self):
        got = submit(json.dumps(self.edit), self.candidates, "T", ["ID-125"])
        self.assertEqual(got.outcome, "COMMITTED")
        self.assertEqual(got.answer.encode(), "原任务。\n\n新地点。\n\n新邀请。\n\n保留 ID-125。".encode())
        self.assertEqual((got.replaced_blocks, got.copied_blocks), (2, 2))

    def test_joint_disjoint_ranges_leave_other_blocks_untouched(self):
        self.edit["replacements"] = [{"base": [0, 1], "donor": [0, 1]},
                                     {"base": [2, 3], "donor": [2, 3]}]
        got = submit(json.dumps(self.edit), self.candidates, "T")
        self.assertEqual(got.outcome, "COMMITTED")
        self.assertEqual(got.answer, "另一个开头。\n\n旧地点。\n\n新邀请。\n\n保留 ID-125。")

    def test_invalid_transactions_keep_the_fixed_fallback(self):
        malformed = [
            {**self.edit, "text": "injected new prose"},
            {**self.edit, "donor": "other"},
            {**self.edit, "replacements": [{"base": [1, 2], "donor": [2, 2]}]},
            {**self.edit, "replacements": [{"base": [1, 2], "donor": [3, 4]}]},
            {**self.edit, "replacements": [{"base": [1, 4], "donor": [1, 4]}]},
            {**self.edit, "replacements": [{"base": [True, 2], "donor": [1, 2]}]},
            {**self.edit, "replacements": [{"base": [1, 3], "donor": [1, 2]},
                                           {"base": [2, 3], "donor": [2, 3]}]},
            {**self.edit, "replacements": [{"base": [1, 2], "donor": [1, 3]},
                                           {"base": [2, 3], "donor": [2, 3]}]},
        ]
        for value in malformed:
            with self.subTest(value=value):
                got = submit(json.dumps(value), self.candidates, "T", ["ID-125"])
                self.assertEqual(got.outcome, "CONTRACT_FALLBACK")
                self.assertEqual(got.answer, "".join(self.candidates["T"]))

    def test_select_is_separate_and_duplicate_fields_fail(self):
        raw = '{"mode":"SELECT","base":"A"}'
        self.assertEqual(submit(raw, self.candidates, "T").outcome, "SELECTED")
        self.assertEqual(submit(raw, self.candidates, "T", ["ID-125"]).outcome, "CONTRACT_FALLBACK")
        raw = '{"mode":"SELECT","base":"T","base":"A"}'
        self.assertEqual(submit(raw, self.candidates, "T").outcome, "CONTRACT_FALLBACK")


if __name__ == "__main__":
    unittest.main()
