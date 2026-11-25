import json
import unittest

from decision_edit import compile_answer, packet


ROOT = {"public_task": {"query": "Plan a low-key dinner for my sister. I will cook."},
        "original_sources": [{"memory_id": "M0", "text": "User: I prefer grilled mains.\nAssistant: Try raw fish."}]}
BASE = "Plan a small dinner. Serve baked chicken and salad. Keep portions modest. Confirm allergies first."
REPLACE = {"before": "Serve baked chicken and salad.", "after": "Serve grilled chicken and salad.",
           "task_quote": "Plan a low-key dinner", "memory": {"id": "M0", "quote": "I prefer grilled mains"},
           "role_quote": "I will cook."}


class EditContract(unittest.TestCase):
    def execute(self, *edits, base=BASE):
        return compile_answer(packet(ROOT, base), json.dumps({"edits": list(edits)}))

    def test_edit_changes_only_requested_span(self):
        result = self.execute(REPLACE)
        self.assertEqual(result["answer"], BASE.replace(REPLACE["before"], REPLACE["after"]))
        self.assertEqual(result["applied"], [0])

    def test_rejects_ambiguous_overlap_and_full_rewrite(self):
        base = BASE + " " + REPLACE["before"]
        ambiguous = self.execute(REPLACE, base=base)
        self.assertEqual(ambiguous["answer"], base)
        self.assertEqual(ambiguous["rejected"][0]["reason"], "ambiguous_span")
        self.assertEqual(self.execute(REPLACE, REPLACE)["transaction"], "overlapping_spans")
        self.assertEqual(self.execute({**REPLACE, "before": BASE})["transaction"], "edit_budget")

    def test_rejects_bad_or_assistant_quotes_without_touching_draft(self):
        assistant = {**REPLACE, "memory": {"id": "M0", "quote": "Try raw fish."}}
        imaginary = {**REPLACE, "task_quote": "bake ice cream"}
        role = {**REPLACE, "role_quote": "I will shop."}
        result = self.execute(assistant, imaginary, role)
        self.assertEqual(result["answer"], BASE)
        self.assertEqual([item["reason"] for item in result["rejected"]],
                         ["missing_user_source", "missing_task_anchor", "missing_role_anchor"])

    def test_noop_and_duplicate_json(self):
        self.assertEqual(self.execute()["answer"], BASE)
        with self.assertRaisesRegex(ValueError, "Duplicate edit field"):
            compile_answer(packet(ROOT, BASE), '{"edits":[],"edits":[]}')


if __name__ == "__main__":
    unittest.main()
