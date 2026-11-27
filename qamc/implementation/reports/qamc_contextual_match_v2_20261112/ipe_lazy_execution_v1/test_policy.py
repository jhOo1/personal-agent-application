import unittest
from unittest.mock import Mock
from policy import generate


class DeferredCalls(unittest.TestCase):
    def test_order_and_input(self):
        for orders, active in ((["ABC","BAC"],False), (["BAC","CBA"],True)):
            calls = Mock()
            calls.estimate_ipe.return_value = object()
            calls.read_orders.return_value = orders
            task = object()
            result = generate(task, estimate_ipe=calls.estimate_ipe, read_orders=calls.read_orders,
                              estimate_mle=calls.estimate_mle, empty_actor=calls.empty_actor, rp_actor=calls.rp_actor)
            self.assertEqual([c[0] for c in calls.mock_calls], ["estimate_ipe","read_orders"] +
                             (["estimate_mle","rp_actor"] if active else ["empty_actor"]))
            if active:
                calls.rp_actor.assert_called_once_with(task, calls.estimate_mle.return_value, calls.estimate_ipe.return_value)
            self.assertIs(result, calls.rp_actor.return_value if active else calls.empty_actor.return_value)

    def test_invalid_order_before_actor(self):
        for orders in ([], ["BAC","BBC"]):
            calls = Mock()
            with self.assertRaises(ValueError):
                generate(None, estimate_ipe=calls.ipe, read_orders=lambda t,i: orders, estimate_mle=calls.mle,
                         empty_actor=calls.empty, rp_actor=calls.rp)
            self.assertEqual([c[0] for c in calls.mock_calls], ["ipe"])
