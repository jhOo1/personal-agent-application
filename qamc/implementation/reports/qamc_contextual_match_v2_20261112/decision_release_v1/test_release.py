"""Unit tests for the permissions and exposure boundary."""
import unittest

from amp_release import Permission, Slot, compile_release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.frame = (
            Slot("venue", "decision", "Venue", (("v1", "Use a different venue"),)),
            Slot("name", "fact", "Legal sender name"),
            Slot("style", "expression", "Writing style", (("s1", "Use concise sentences"),)),
        )
        self.history = {
            "a": "Guest has a private health condition.",
            "b": "Legal name: Example Person. Preferred nickname: Secret Alias.",
            "c": "Unrelated memory.",
        }
        self.plan = (
            Permission("a", "venue", "require", option="v1"),
            Permission("b", "name", "ground", span=(12, 26)),
        )

    def test_two_same_admitted_sources_different_visible_values(self):
        binary = compile_release(self.frame, self.history, self.plan, exposure="binary")
        partitioned = compile_release(self.frame, self.history, self.plan, exposure="partitioned")
        self.assertEqual(binary["history"], [self.history["a"], self.history["b"]])
        self.assertEqual(partitioned["grounded_facts"], [{"slot": "Legal sender name", "text": "Example Person"}])
        self.assertEqual(partitioned["decision_controls"], [
            {"slot": "Venue", "operation": "require", "value": "Use a different venue"}
        ])
        for token in ("private health condition", "Secret Alias", "Unrelated memory"):
            self.assertNotIn(token, str(partitioned))

    def test_unknown_option_and_cross_channel_release_are_rejected(self):
        bad = (
            Permission("a", "venue", "require", option="free text"),
            Permission("a", "name", "require", option="v1"),
            Permission("b", "name", "ground", span=(False, 18)),
            Permission("b", "name", "ground", span=(12, 200)),
            Permission("unseen", "venue", "require", option="v1"),
        )
        for permit in bad:
            with self.subTest(permit=permit):
                with self.assertRaises(ValueError):
                    compile_release(self.frame, self.history, (permit,), exposure="partitioned")

    def test_abstention_compiles_without_exposure(self):
        self.assertEqual(compile_release(self.frame, self.history, (), exposure="partitioned"),
                         {"grounded_facts": [], "decision_controls": []})
        self.assertEqual(compile_release(self.frame, self.history, (), exposure="binary"), {"history": []})


if __name__ == "__main__":
    unittest.main()
