"""Report matched trajectory-policy outcomes without issuing requests."""
import argparse
import json

from read_option_pair import summarize
from run_trajectory_proposals import OUT
from trial_reassembly import probe


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("split", choices=("search", "group_out"))
    split = parser.parse_args().split
    result = probe.read(OUT / split / "RESULTS.json")
    print(json.dumps({**summarize(result, ("atomic", "block")),
                      "eligibility": result["eligibility"]}, indent=2))
