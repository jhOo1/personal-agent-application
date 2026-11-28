"""Find the recorded GPT scorer request for each saved Qwen-generated endpoint."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path
import sqlite3

HERE = Path(__file__).resolve().parent
setup = run_path(str(HERE / "trial.py"))
old, build = setup["old"], setup["build"]
root = HERE.parents[2] / "runs" / HERE.parent.name

def main():
    _, cards, jobs = build()
    paths = (
        ("RPR_PAPER_FULL", [old.v41.formal.RUN / "grading/execution/samples.sqlite"]),
        ("TASK_ONLY", [
            *list((root / "counterfactual_rpeval_v41_task_only").glob("*/RPEvalJudge/samples.sqlite")),
            *list((root / "counterfactual_rpeval_v41").glob("*/RPEvalJudge/samples.sqlite")),
            old.v41.formal.RUN / "grading/execution/samples.sqlite",
            root / "ipe_c_full_exposed_panel_v1/RPEvalJudge/samples.sqlite",
            root / "ipe_c_two_endpoint_completion_v1/RPEvalJudge/samples.sqlite",
        ]),
    )
    table = Counter()
    for arm, databases in paths:
        old_hashes = {old.sha(dict(jobs[c["cells"]["QWEN", arm][1]], model="gpt-4.1"))
                      for c in cards.values()}
        found = Counter()
        for path in databases:
            if not path.is_file():
                continue
            with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
                for digest in old_hashes:
                    rows = connection.execute(
                        "select request_json, response_json from samples where request_sha=? "
                        "and status='COMPLETE'", (digest,)).fetchall()
                    for request, response in rows:
                        if (old.sha(json.loads(request)) != digest
                                or not response or not json.loads(response).get("answer")):
                            continue
                        found[digest] += 1
        table[arm + "/assigned"] = len(cards)
        table[arm + "/exact_historical_wire_found"] = len(found)
        table[arm + "/multiple_matching_receipts"] = sum(i > 1 for i in found.values())
    print(json.dumps(table, indent=2))

if __name__ == "__main__":
    main()
