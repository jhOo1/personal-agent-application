import json
import unittest

from seed_control import compile_revision


class RevisionContract(unittest.TestCase):
    task = {"query": "Plan a low-key dinner for my sister. I will cook."}
    data = {"task": task,
            "source_evidence": [{"memory_id": "M0", "text": "User: I prefer grilled mains.\nAssistant: Try raw fish."}],
            "original_answer": "Plan a small dinner. Serve baked chicken and salad. Confirm allergies."}
    replacement = {"task_quote": "Plan a low-key dinner", "role_quote": "I will cook.",
                   "memory": {"id": "M0", "quote": "I prefer grilled mains."}}

    def revise(self, *ops):
        return compile_revision(self.data, json.dumps({"replace_ops": ops}))

    def test_unchanged_anchor_text_does_not_use_edit_budget(self):
        draft = self.data["original_answer"]
        outcome = self.revise({**self.replacement, "before": draft, "after": draft.replace("baked", "grilled")})
        self.assertEqual(outcome["answer"], draft.replace("baked", "grilled"))
        self.assertLess(outcome["characters"]["removed"], 10)
        self.assertLess(outcome["characters"]["inserted"], 10)

    def test_missing_reference_and_overlapping_edits_do_not_count_as_noop(self):
        op = {**self.replacement, "before": "baked", "after": "grilled"}
        wrong = {**op, "memory": {"id": "M0", "quote": "Try raw fish."}}
        rejected = self.revise(op, wrong)
        self.assertEqual(rejected["status"], "INVALID_REFERENCE")
        self.assertIsNone(rejected["answer"])
        self.assertEqual(self.revise(op, op)["status"], "OVERLAPPING_OPERATIONS")
        self.assertEqual(self.revise()["status"], "NOOP")
        self.assertEqual(self.revise()["answer"], self.data["original_answer"])

    def test_destructive_rewrite_exceeds_the_delta_limit(self):
        outcome = self.revise({**self.replacement, "before": self.data["original_answer"], "after": "Go out."})
        self.assertEqual(outcome["status"], "EDIT_BUDGET")
        self.assertIsNone(outcome["answer"])


if __name__ == "__main__":
    unittest.main()
