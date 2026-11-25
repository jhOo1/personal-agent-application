"""Exercise the compiler with archived RPEval drafts and source quotations."""
from copy import deepcopy
import json
import unittest

import decision_transactions as method
import run_effect_scope as previous


class TransactionReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, cls.data, cls.roots, _, _ = previous.prepare()
        cls.archived = {row["uid"]: row for row in previous.read(previous.OUT / "SETTLED.json")["rows"]}

    def inputs(self, suffix):
        uid = next(uid for uid in self.data if uid.endswith(suffix))
        return self.roots[uid], self.data[uid]["blocks"], self.archived[uid]

    def compile(self, root, blocks, decisions, *, atomic):
        units, rejected = method.parse(root, blocks, json.dumps({"decisions": decisions}))
        result, commits, failures = method.render(root, blocks, units, atomic=atomic)
        return result, commits, rejected, failures

    def test_hard_only_variant_survives_rejected_shared_aesthetic(self):
        root, blocks, row = self.inputs("explicit/116")
        edit = next(item["edit"] for item in row["execution"]["EFFECT_SCOPE"]["rejected"]
                    if item["edit"]["effects"] == ["E4", "E5"])
        patch = {key: edit[key] for key in ("block", "option", "before", "after")}
        textile_only = {**patch, "after": "5. **选非布艺材质**\n   选木质椅面和可擦洗的硬质餐垫，保留自然质感。"}
        effects = [{k: v for k, v in row["effects"][key].items() if k != "task_quote"} for key in ("E4", "E5")]
        decision = {"decision": "餐厅材质和餐具", "task_basis": "想让餐厅区域更有家的感觉",
                    "effects": effects,
                    "variants": [{"effects": ["E4", "E5"], "patches": [patch]},
                                 {"effects": ["E4"], "patches": [textile_only]}]}
        ordinary, commits, rejected, _ = self.compile(root, blocks, [decision], atomic=False)
        self.assertFalse(commits or rejected)
        self.assertIn(patch["before"], ordinary)
        answer, commits, rejected, _ = self.compile(root, blocks, [decision], atomic=True)
        self.assertFalse(rejected)
        self.assertEqual([{"decision": 1, "variant": 2, "effects": ["E4"]}], commits)
        self.assertEqual(ordinary.replace(patch["before"], textile_only["after"]), answer)
        self.assertNotIn("色彩明快", answer)

    def test_task_basis_and_two_dependent_spans_are_validated_separately(self):
        root, blocks, row = self.inputs("explicit/090")
        effects = json.loads(row["attempts"]["EXACT_EDITS"]["raw"])["effects"]
        length_rule = {k: v for k, v in effects[1].items() if k != "task_quote"}
        draft = blocks["D1"]["lines"][0]
        inbound, outbound = (effects[i]["task_quote"] for i in (1, 2))
        decision = {"decision": "往返交通的车程", "task_basis": "能帮我规划一下路线吗",
                    "effects": [length_rule], "variants": [{"effects": [length_rule["id"]], "patches": [
                        {"block": "D1", "option": None, "before": inbound,
                         "after": "- 核实可选短程交通；无法避开长车程时，留在丽江"},
                        {"block": "D1", "option": None, "before": outbound,
                         "after": "如未前往香格里拉，从丽江安排返程"}]}]}
        modified, commits, rejected, _ = self.compile(root, blocks, [decision], atomic=True)
        self.assertFalse(rejected)
        self.assertEqual(len(commits), 1)
        self.assertIn("从丽江安排返程", modified)
        self.assertNotIn(inbound, modified)

        bad_span = deepcopy(decision)
        bad_span["variants"][0]["patches"][1]["before"] = "文中没有这一段"
        bad_basis = {**decision, "task_basis": inbound}
        overlap = {**decision, "decision": "另一个使用相同落点的决定"}
        for records, reason in (([bad_span], "EDIT_SPAN"), ([bad_basis], "TASK_BASIS"),
                                ([decision, overlap], "INTERDEPENDENT_SPANS")):
            with self.subTest(reason=reason):
                answer, commits, rejected, _ = self.compile(root, blocks, records, atomic=True)
                self.assertEqual(answer, draft)
                self.assertFalse(commits)
                self.assertEqual({item["reason"] for item in rejected}, {reason})

    def test_personal_outdoor_preference_does_not_set_shared_default(self):
        root, blocks, row = self.inputs("explicit/049")
        blocked = row["execution"]["EFFECT_SCOPE"]["rejected"][0]["edit"]
        self.assertEqual(blocked["effects"], ["E1"])
        effect = {k: v for k, v in row["effects"]["E1"].items() if k != "task_quote"}
        decision = {"decision": "亲子行程活动", "task_basis": root["public_task"]["query"],
                    "effects": [effect], "variants": [{"effects": ["E1"],
                        "patches": [{k: blocked[k] for k in ("block", "option", "before", "after")}]}]}
        for atomic in (False, True):
            answer, commits, rejected, failures = self.compile(root, blocks, [decision], atomic=atomic)
            self.assertIn(blocked["before"], answer)
            self.assertFalse(commits or rejected)
            self.assertEqual(failures["NO_PERMITTED_COMPLETE_VARIANT"], 1)


if __name__ == "__main__":
    unittest.main()
