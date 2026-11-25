"""Verify byte preservation and unchanged rendering on saved benchmark replies."""
import json
import unittest

import decision_transactions as method
import run_decision_transactions as run
import transaction_text_wire as codec


class TransactionTextWireTest(unittest.TestCase):
    def test_saved_decisions_and_answers_round_trip(self):
        counts = {}
        for panel in ("smoke", "pilot"):
            _, _, roots, data, _ = run.prepare(panel)
            settled = run.read(run.BASE_OUT / panel / "SETTLED.json")
            compiled = 0
            for row in settled["rows"]:
                uid = row["uid"]
                root, blocks = roots[uid], data[uid]["blocks"]
                candidate = codec.request(root, blocks, method.ATOMIC)
                baseline = codec.request(root, blocks, method.ORDINARY)
                self.assertEqual(candidate["messages"][1], baseline["messages"][1])
                self.assertEqual(candidate["messages"][1], method.request(root, blocks)["messages"][1])
                marker = codec.packet_marker(candidate["messages"][1]["content"])
                if method.ORDINARY in row["outputs"]:
                    text = row["outputs"][method.ORDINARY]
                    self.assertEqual(codec.ordinary_answer(text), text)
                if method.ATOMIC not in row["outputs"]:
                    continue
                proposal = method.rank.model_object(row["attempts"][method.ATOMIC]["raw"], "decisions")
                restored = codec.decode(codec.encode(proposal, marker), marker)
                self.assertEqual(restored, proposal)
                units, rejected = method.parse(root, blocks, json.dumps(restored, ensure_ascii=False))
                self.assertEqual(rejected, row["rejected"])
                for arm in (method.ATOMIC, method.BUNDLED):
                    answer, committed, errors = method.render(root, blocks, units, atomic=arm == method.ATOMIC)
                    self.assertEqual(answer, row["outputs"][arm])
                    self.assertEqual(committed, row["execution"][arm]["committed"])
                    self.assertEqual(errors, row["execution"][arm]["rejected"])
                compiled += 1
            counts[panel] = compiled
        self.assertEqual(counts, {"smoke": 5, "pilot": 54})

    def test_quotes_empty_fields_and_whitespace(self):
        marker = "@@QAMC-fixture"
        raw = json.loads(codec.METADATA_EXAMPLE)
        edits = raw["decisions"][0]["variants"][0]["patches"]
        edits[0].update(before='  原样 "术语"\nC:\\Temp\n', after="")
        self.assertEqual(codec.decode(codec.encode(raw, marker), marker), raw)
        raw = {"decisions": []}
        self.assertEqual(codec.decode(codec.encode(raw, marker), marker), raw)

    def test_malformed_response_does_not_recover_a_proposal(self):
        marker = "@@QAMC-fixture"
        zero = '{"decisions":[]}'
        for response in (zero, f"{zero}\n{marker} END\ntrailing commentary",
                         f"{zero}\n{marker} T1\nunused\n{marker} END",
                         f"{zero}\n{marker} T1\nfirst\n{marker} T1\nsecond\n{marker} END"):
            with self.subTest(response=response), self.assertRaises(ValueError):
                codec.decode(response, marker)


if __name__ == "__main__":
    unittest.main()
