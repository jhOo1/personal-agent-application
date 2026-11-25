import json
import unittest

import planning
from qamc.common import sha


class PlanningTest(unittest.TestCase):
    def setUp(self):
        self.task = {"query": "Choose the tour and lunch for us. Keep the timing workable."}
        self.sources = [{"memory_id": "M0", "text": "User: We prefer an afternoon outdoors."},
                        {"memory_id": "M1", "text": "User: We never book overlapping activities.\nAssistant: Go skiing."}]
        self.payload = {"task": self.task, "source_evidence": self.sources}

        def option(text, condition=None):
            return {"text": text, "task_cost": 0, "conditional_on": condition}

        self.proposal = {
            "decisions": [
                {"name": "tour", "task_quote": "Choose the tour",
                 "options": [option("afternoon outdoors"), option("morning indoors")]},
                {"name": "lunch", "task_quote": "lunch for us",
                 "options": [option("late lunch"), option("early lunch")]},
            ],
            "hard": [{"choices": {"D1": "O1", "D2": "O1"}, "source_id": "M1",
                      "quote": "We never book overlapping activities.", "scope": "same group's schedule"}],
            "soft": [{"choices": {"D1": "O1"}, "source_id": "M0",
                      "quote": "We prefer an afternoon outdoors.", "scope": "the group's tour"}],
            "selection": {"D1": "O1", "D2": "O1"},
        }

    def compile(self):
        return planning.compile_plan(self.payload, json.dumps(self.proposal))

    def test_joint_constraint_reorders_the_other_decision_and_keeps_soft_preference(self):
        plan, selections, audit = self.compile()
        self.assertEqual(selections[planning.SOLVED], {"D1": "O1", "D2": "O2"})
        self.assertEqual(audit["feasible_count"], 3)
        self.assertEqual(audit["control_conflicts"], [0])
        payloads = []
        for choice in selections.values():
            wire = planning.actor_request(self.payload, plan, choice)
            body = json.loads(wire["messages"][1]["content"])
            self.assertEqual(body.pop("selection"), choice)
            payloads.append((body, wire["messages"][0]))
        self.assertEqual(payloads[0], payloads[1])

    def test_assistant_only_and_unknown_choice_evidence_are_filtered_for_both_arms(self):
        clause = self.proposal["hard"][0]
        self.proposal["hard"].extend([{**clause, "quote": "Go skiing."},
                                     {**clause, "choices": {"D9": "O1"}}])
        plan, _, audit = self.compile()
        self.assertEqual(audit["rejected"]["hard"], [1, 2])
        self.assertEqual(len(plan["hard"]), 1)

    def test_equivalent_plan_reuses_exact_actor_request(self):
        self.proposal["selection"]["D2"] = "O2"
        self.proposal["soft"].append(dict(self.proposal["soft"][0]))
        plan, selections, audit = self.compile()
        self.assertEqual(audit["solved_rank"], (0, 0, -1, 0))
        self.assertEqual(len({sha(planning.actor_request(self.payload, plan, choice))
                              for choice in selections.values()}), 1)

    def test_no_feasible_assignment_is_explicit(self):
        clause = self.proposal["hard"][0]
        self.proposal["hard"] = [{**clause, "choices": {"D1": option}} for option in ("O1", "O2")]
        _, selections, audit = self.compile()
        self.assertEqual(audit["feasible_count"], 0)
        self.assertIsNone(selections[planning.SOLVED])

    def test_unknown_precondition_is_retained_and_ranks_below_equivalent_known_option(self):
        self.proposal["decisions"][0]["options"][0]["conditional_on"] = "The trail is open"
        plan, selections, _ = self.compile()
        self.assertEqual(selections[planning.SOLVED]["D1"], "O2")
        self.assertEqual(plan["decisions"][0]["options"][0]["conditional_on"], "The trail is open")

    def test_planner_request_excludes_evaluation_fields(self):
        root = {"public_task": self.task, "original_sources": self.sources,
                "archived": {"answer": "not available to planner"}, "labels": "CABA"}
        body = json.loads(planning.planner_request(planning.packet(root))["messages"][1]["content"])
        self.assertEqual(body, self.payload)


if __name__ == "__main__":
    unittest.main()
