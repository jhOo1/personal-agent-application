"""Scope-preserving cluster and missingness sensitivity for the expanded baseline."""
from collections import defaultdict
import json
from pathlib import Path
from random import Random

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def compare(rows, public, method):
    groups = defaultdict(lambda: [0, 0])
    lower, upper, assigned_positions = 0, 0, 0
    for row in rows:
        n = len(public[row["uid"]]["memories"])
        a = row["ipe_c"]["grade"].get("match")
        b = row["controls"][method]["grade"].get("match")
        for cell in (a, b):
            if cell and cell["positions"] != n:
                raise ValueError("Unmatched position count")
        m, k = [x["matched"] if x else None for x in (a, b)]
        lower += (m if m is not None else 0) - (k if k is not None else n)
        upper += (m if m is not None else n) - (k if k is not None else 0)
        assigned_positions += n
        if m is not None and k is not None:
            bucket = groups[row["source_group"]]
            bucket[0] += m - k
            bucket[1] += n
    entries = list(groups.values())
    samples = []
    if len(entries) > 1:
        rng = Random(20261124)
        for _ in range(5000):
            sample = rng.choices(entries, k=len(entries))
            samples.append(100 * sum(x for x, _ in sample) / sum(n for _, n in sample))
        samples.sort()
    return {"groups": len(groups), "assigned_positions": assigned_positions,
            "missing_score_range_pp": [100 * bound / assigned_positions for bound in (lower, upper)],
            "paired_source_group_bootstrap_95_pp": [samples[124], samples[4874]] if samples else None}


def build():
    result = read(HERE / "RESULTS.json")
    public = read(HERE.parent / "rpeval_formal_multi_coverage_v1/PUBLIC_TASKS.json")
    rows = result["rows"]
    if len(rows) != 300 or {r["uid"] for r in rows} != set(public):
        raise ValueError("Expanded panel differs from public archive")
    return {scope: {m: compare(cells, public, m) for m in rows[0]["controls"]}
            for scope, cells in (("all_300", rows),
                                 ("additional_67", [r for r in rows if r["scope"] == "additional_67"]))}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
