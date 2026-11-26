"""Run the same frozen anonymous pairs with the separate DeepSeek evaluator alias."""
import json
from pathlib import Path
import sys

import blind_endpoints as main

REVIEW = main.review
RUN = main.RUN.with_name("ipe_endpoint_behavior_deepseek_v1")
ALIAS = "deepseek-v4.1-flash"


def prepare(fingerprint):
    plan = main.prepare(fingerprint)
    original = REVIEW.read(main.RUN / "FROZEN.json")
    if original["source_pins"] != plan["source_pins"] or original["packets"] != plan["packets"]:
        raise ValueError("Original anonymous panel changed")
    for pair in plan["packets"].values():
        pair["wire"]["model"] = ALIAS
        pair["wire_sha256"] = main.sha(pair["wire"])
    plan["source_pins"][Path(__file__).name] = main.sha(Path(__file__).read_bytes())
    return plan


if __name__ == "__main__":
    REVIEW.OUT = REVIEW.RUN = RUN
    REVIEW.CAP = 22
    REVIEW.prepare = prepare
    REVIEW.check_vote = main.validator(REVIEW.check_vote)
    if sys.argv[1:] == ["summarize"]:
        print(json.dumps(main.summarize(REVIEW.read(RUN / "RESULTS.json")), indent=2))
    else:
        REVIEW.main()
