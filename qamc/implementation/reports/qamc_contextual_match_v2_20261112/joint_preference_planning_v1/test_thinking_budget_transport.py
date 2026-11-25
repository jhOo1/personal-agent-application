"""Verify that the public reasoning cap reaches the exact durable request."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from proposals.qamc_protocol_alignment import sampling
from qamc.common import sha

from thinking_budget_transport import FIELD, MODEL, ThinkingBudgetSampler, controlled_wire


def job(budget=4096):
    request = {"model": MODEL, "messages": [{"role": "user", "content": "Reply briefly."}],
               "temperature": 0, "max_tokens": 8192, "stream": True, "stream_options": {"include_usage": True}}
    protocol = {"model": MODEL, "concurrency": 1, "spacing_seconds": 3.2,
                "stages": {"Compose": {"temperature": 0, "max_tokens": 8192, FIELD: budget}}}
    unit = {"root_id": "fixture", "stage": "Compose", "method": "test", "replicate": 0,
            "protocol_sha256": sha(protocol)}
    wire = controlled_wire(request, budget)
    return {"protocol": protocol, "units": [{"unit": unit, "request": wire}]}, unit, wire


class FixtureStream:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        chunks = [
            {"model": MODEL, "choices": [{"delta": {"reasoning_content": "internal fixture"}, "index": 0}]},
            {"model": MODEL, "choices": [{"delta": {"content": "Done."}, "index": 0, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 8, "completion_tokens": 14, "total_tokens": 22,
                                      "completion_tokens_details": {"reasoning_tokens": 12}}},
        ]
        yield from (f"data: {json.dumps(chunk)}\n".encode() for chunk in chunks)
        yield b"data: [DONE]\n"


class FixtureOpener:
    def __init__(self):
        self.wires = []

    def open(self, request, *, timeout):
        self.wires.append(json.loads(request.data))
        return FixtureStream()


class ReasoningBudgetTransportTest(unittest.TestCase):
    CONFIG = {"base_url": "https://example.invalid/v1", "api_key": "fake-key", "access_key": "fake-access",
              "app": "fixture", "quota_id": "fixture-quota", "user_id": "fixture-user"}

    def test_exact_budget_is_sent_journaled_and_reused(self):
        manifest, unit, wire = job()
        opener = FixtureOpener()
        with TemporaryDirectory() as path:
            sampler = ThinkingBudgetSampler(path, manifest, opener=opener, config=self.CONFIG)
            try:
                self.assertFalse(sampler.perform(unit, wire)["cache_hit"])
                self.assertTrue(sampler.perform(unit, wire)["cache_hit"])
                self.assertEqual([wire], [{k: body[k] for k in wire} for body in opener.wires])
                folder = Path(path) / "visible" / sampling.sampling_key(unit)
                persisted = json.loads((folder / "request.json").read_text())
                receipt = json.loads((folder / "record.json").read_text())
                response = json.loads((folder / "response.json").read_text())
                self.assertEqual(persisted, wire)
                self.assertEqual(receipt["request_sha256"], sha(wire))
                self.assertEqual(receipt["reported_completion_minus_reasoning_tokens"], 2)
                self.assertEqual(response["answer"], "Done.")
                self.assertNotIn("internal fixture", json.dumps(response))
                self.assertNotIn("fake-key", json.dumps(persisted))
                with self.assertRaises(ValueError):
                    sampler.perform(unit, {**wire, FIELD: 4095})
            finally:
                sampler.close()

    def test_frozen_limit_is_checked_without_weakening_old_validation(self):
        manifest, _, wire = job()
        with self.assertRaises(ValueError):
            sampling.validate_public_request(wire)
        manifest["units"][0]["request"] = {**wire, FIELD: 4095}
        with TemporaryDirectory() as path, self.assertRaisesRegex(ValueError, "Unfrozen thinking budget"):
            ThinkingBudgetSampler(path, manifest, config=self.CONFIG)


if __name__ == "__main__":
    unittest.main()
