"""Resume scoring while excluding unrelated archives and replaying settled generation."""
from argparse import ArgumentParser
from pathlib import Path
from runpy import run_path

here = Path(__file__).resolve().parent
module = run_path(str(here / "run.py"))
engine, transfer, probe = (module[k] for k in ("engine", "transfer", "probe"))
original_match = transfer.matching_grading_receipts
original_stage = engine.stage


def matching(board, cases, protocol, archive):
    return original_match(board, cases, protocol, [row for row in archive if row["uid"] in cases])


def stage(name, jobs, plan, live, ledger, cache=None):
    # All generation requests have terminal local receipts. The stage verifier checks their hashes.
    return original_stage(name, jobs, plan, live and name != module["ACTOR"], ledger, cache)


def main(action):
    transfer.matching_grading_receipts = matching
    engine.stage = stage
    try:
        module["run"](action)
    finally:
        transfer.matching_grading_receipts = original_match
        engine.stage = original_stage


if __name__ == "__main__":
    cli = ArgumentParser()
    cli.add_argument("action", choices=("run", "replay"))
    main(cli.parse_args().action)
