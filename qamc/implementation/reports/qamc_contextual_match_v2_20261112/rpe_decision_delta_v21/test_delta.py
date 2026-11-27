import json
import unittest

from delta import apply, index


class DecisionDeltaTests(unittest.TestCase):
    def setUp(self):
        self.draft = "# Plan\n\nStart close to home.\n\n1. Order plain toast.\n2. Try the dish containing fish.\n3. Ask which tables are available.\n"
        self.units = index(self.draft)
        self.packet = {"draft_units": self.units, "context": {
            "query": "Plan lunch.", "current_context": "",
            "facts": [], "history": ["I like inventive bread and avoid fish."]}}
        self.toast = next(u["id"] for u in self.units if "toast" in u["text"])
        self.fish = next(u["id"] for u in self.units if "the dish" in u["text"])

    def run_groups(self, groups):
        return apply(json.dumps({"mode": "DELTA", "groups": groups}), self.packet, "DELTA")

    def group(self, effect, unit, op, quote="avoid fish", **fields):
        return {"effect": effect, "evidence": {"origin": "HISTORY", "quote": quote},
                "edits": [{"id": unit, "op": op, **fields}]}

    def test_index_is_lossless_for_markdown_and_cjk(self):
        text = "我推荐海鲜。其他选项都可继续。\n\n- 选项甲\n- 选项乙\n\n```text\n# 内容\n```\n"
        units = index(text)
        self.assertEqual([u["kind"] for u in units], ["paragraph", "paragraph", "item", "item", "fixed"])
        self.assertEqual("".join(u["text"] for u in units), text)

    def test_offer_leaves_old_choice_and_inserts_concrete_text(self):
        result, trace = self.run_groups([self.group("OFFER", self.toast, "EXTEND", "inventive bread",
                                                    text="There is also a sesame milk bun.")])
        self.assertEqual(result, self.draft.replace("Order plain toast.",
                                  "Order plain toast. There is also a sesame milk bun."))
        self.assertEqual(trace["applied_effects"], ["OFFER"])

    def test_drop_and_keep_independent_of_rejected_group(self):
        good = self.group("TRIM", self.fish, "REMOVE")
        rejected = self.group("OFFER", self.toast, "EXTEND", "invented history", text="Try jam.")
        result, trace = self.run_groups([good, rejected])
        self.assertEqual(result, self.draft.replace("2. Try the dish containing fish.\n", ""))
        self.assertEqual(trace["rejected_groups"], ["unbound evidence"])

    def test_offer_cannot_only_rewrite_criterion_or_overwrite_option(self):
        criterion = next(u["id"] for u in self.units if "Start" in u["text"])
        clauses = [self.group("OFFER", criterion, "EXTEND", text="Innovative."),
                   self.group("OFFER", self.toast, "REPLACE", text="Find creativity.")]
        for clause in clauses:
            result, trace = self.run_groups([clause])
            self.assertEqual(result, self.draft)
            self.assertEqual(len(trace["rejected_groups"]), 1)

    def test_overlap_forbids_commit(self):
        a = self.group("TRIM", self.fish, "REMOVE")
        b = self.group("QUALIFY", self.fish, "EXTEND", text="Confirm the ingredients.")
        with self.assertRaises(ValueError):
            self.run_groups([a, b])

    def test_one_call_control_envelope(self):
        self.assertEqual(apply('{"mode":"KEEP"}', self.packet, "FREE")[0], self.draft)
        self.assertEqual(apply('{"mode":"REWRITE","answer":"Revised"}',
                               self.packet, "FREE")[0], "Revised")
        with self.assertRaises(ValueError):
            apply('{"mode":"REWRITE","answer":"Revised"}', self.packet, "DELTA")


if __name__ == "__main__":
    unittest.main()
