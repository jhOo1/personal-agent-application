import json
import unittest

from selection import IDS, METHODS, blind_order, conversation, parse_compare, reward_choice, serialize_task


class SelectionTest(unittest.TestCase):
    def test_context_has_no_evaluation_or_method_metadata(self):
        inputs = {"query": "task", "current_context": "", "fixed_facts": [],
                  "persona": "do not read", "intent_type": "not visible",
                  "memories": [{"text": "source", "memory_id": "M0", "score": 1}]}
        context = serialize_task(inputs)
        payload = conversation(context, "answer")
        self.assertEqual(json.loads(payload[0]["content"]), {
            "query": "task", "current_context": "", "facts": [], "history": ["source"],
        })
        self.assertEqual(payload[1], {"role": "assistant", "content": "answer"})

    def test_rank_must_be_complete_finite_and_unique(self):
        self.assertEqual(reward_choice({"A": 1, "B": 2.0, "C": 0}), "B")
        self.assertIsNone(reward_choice({"A": 1, "B": 2, "C": 2}))
        for invalid in ({"A": 1}, {"A": float("nan"), "B": 2, "C": 0},
                        {"A": True, "B": 2, "C": 0}):
            with self.assertRaises(ValueError):
                reward_choice(invalid)

    def test_candidate_ids_are_blind_and_validated(self):
        self.assertEqual(set(blind_order("a")), set(IDS))
        self.assertEqual(set(blind_order("a").values()), set(METHODS))
        self.assertEqual(blind_order("a"), blind_order("a"))
        self.assertEqual(parse_compare('{"choice":"B"}'), "B")
        for invalid in ("B", '{"choice":"RP"}', '{"choice":"A","why":"x"}', '{"choice":null}'):
            with self.assertRaises(ValueError):
                parse_compare(invalid)


if __name__ == "__main__":
    unittest.main()
