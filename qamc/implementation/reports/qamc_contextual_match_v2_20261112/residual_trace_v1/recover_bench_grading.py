"""Reuse the three delivered Actor receipts and start only pending BenchPreS grading."""
import argparse

import run_bench_add as pilot


def main(action):
    frozen, *data = pilot.prepare()
    if frozen != pilot.probe.read(pilot.RUN / "FROZEN.json"):
        raise ValueError("Frozen intervention drift")
    if not all((pilot.RUN / f"{name}_MANIFEST.json").is_file() for name in pilot.ACTORS):
        raise ValueError("Expected three already allocated Actor draws")
    execute_stage = pilot.engine.stage

    def recovered_stage(name, tasks, identity, live, ledger, cache=None):
        if not tasks:
            return {}
        if name in pilot.ACTORS:
            result = execute_stage(name, tasks, identity, False, ledger, cache)
            if any(r["status"] != "OK" for r in result.values()):
                raise ValueError("Expected three completed Actor receipts")
            return result
        if name != "BenchAttrs":
            raise ValueError("Only the frozen BenchPreS grader needs recovery")
        return execute_stage(name, tasks, identity, live, ledger, cache)

    pilot.engine.stage = recovered_stage
    try:
        pilot.execute(frozen, *data, live=action == "recover")
    finally:
        pilot.engine.stage = execute_stage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("recover", "replay"))
    main(parser.parse_args().action)
