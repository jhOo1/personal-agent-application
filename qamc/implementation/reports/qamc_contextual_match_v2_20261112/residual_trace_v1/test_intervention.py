import unittest

from residual_memory_delta import Delta, Entry, apply, difference


class InterventionTest(unittest.TestCase):
    def setUp(self):
        self.original = ("M1", "M2", "M3")
        self.state = (Entry("M1", "B"), Entry("M3", "C"))

    def test_reversible_single_operations(self):
        for op in (Delta("KEEP"), Delta("ADD", "M2", "C"), Delta("REMOVE", "M1"), Delta("REBIND", "M1", "A")):
            with self.subTest(op=op):
                out = apply(self.original, self.state, op, allowed_usage={"A", "B", "C"})
                self.assertEqual(op, difference(self.original, self.state, out))
                self.assertEqual((Entry("M1", "B"), Entry("M3", "C")), self.state)

    def test_composite_source_swap_is_not_a_single_addition(self):
        self.assertIsNone(difference(self.original, self.state, (Entry("M2", "B"), Entry("M3", "C"))))

    def test_reject_invalid_original_identity_order_and_policy(self):
        for op in (
            Delta("ADD", "M4", "C"), Delta("ADD", "M1", "C"), Delta("REMOVE", "M2"),
            Delta("KEEP", "M2"), Delta("REBIND", "M1", "bad"), Delta("REBIND", "M1", "B"),
        ):
            with self.subTest(op=op), self.assertRaises(ValueError):
                apply(self.original, self.state, op, allowed_usage={"A", "B", "C"})
        with self.assertRaises(ValueError):
            difference(self.original, self.state, tuple(reversed(self.state)))


if __name__ == "__main__":
    unittest.main()
