import unittest

from frozen_decision import answer_digest, compile_option


class FrozenDecisionTest(unittest.TestCase):
    def setUp(self):
        self.base = "先按儿童活动区和安全设施选择咖啡馆。"
        self.choices = {"drink": "大人的饮品可选"}
        self.option = {"action": "append", "base_digest": answer_digest(self.base),
                       "choice_id": "drink", "value": "一杯拿铁"}

    def test_append_preserves_base_bytes(self):
        result = compile_option(self.base, self.option, self.choices)
        self.assertEqual(result, self.base + "\n\n大人的饮品可选：一杯拿铁")

    def test_keep(self):
        self.assertEqual(compile_option(self.base, {"action": "keep"}, {}), self.base)

    def test_invalid_inputs(self):
        for patch in ({"base_digest": "stale"}, {"choice_id": "venue"},
                      {"value": "   "}, {"value": "拿铁\n新主方案"}, {"replace": self.base}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                compile_option(self.base, {**self.option, **patch}, self.choices)


if __name__ == "__main__":
    unittest.main()
