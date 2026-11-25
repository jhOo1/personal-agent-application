"""Keep the diagnostic scoped to claims about the judge's supplied target."""
import unittest

from audit_transaction_judge import explicit_target_claims, flagged_match_bounds


class JudgeTargetClaimsTest(unittest.TestCase):
    def test_chinese_prose_can_contain_the_intent_marker(self):
        reason = "回复对第1条进行了支持性体现，且intent要求第3、4、5、6条为C（主线），第1、2、7条为A（忽略）。"
        claims = explicit_target_claims(reason, 7)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["labels"], {1: "A", 2: "A", 3: "C", 4: "C", 5: "C", 6: "C", 7: "A"})

    def test_target_and_observed_use_remain_separate(self):
        self.assertEqual(explicit_target_claims("实际第3条为C，回复第1条为B。", 7), [])
        self.assertEqual(explicit_target_claims("intent不要求第3条为C。", 7), [])
        claims = explicit_target_claims("目标意图为CCAABAA。实际第3条为C。", 7)
        self.assertEqual(claims[0]["labels"][3], "A")
        self.assertEqual(len(claims), 1)

    def test_same_flagged_receipt_cancels_in_pair(self):
        shared = {"request_sha256": "shared", "fields": {"match": {"matched": 2}}}
        flagged = {"request_sha256": "different", "fields": {"match": {"matched": 4}}}
        rows = [{"positions": 5, "native": {"left": shared, "right": shared}},
                {"positions": 5, "native": {"left": flagged, "right": shared}}]
        bounds = flagged_match_bounds(rows, "left", "right", {"shared", "different"})
        self.assertEqual(bounds["range_replacing_flagged_only"], [-5, 5])
        only_shared = flagged_match_bounds(rows[:1], "left", "right", {"shared"})
        self.assertEqual(only_shared["range_replacing_flagged_only"], [0, 0])
        self.assertEqual(only_shared["same_wire_cancellations"], 1)


if __name__ == "__main__":
    unittest.main()
