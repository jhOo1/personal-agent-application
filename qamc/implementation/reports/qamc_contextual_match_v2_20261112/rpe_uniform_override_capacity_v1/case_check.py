"""Verify source identities, actual answer bytes and saved grades for the five wins."""
import contextlib
import hashlib
import io
import json
import runpy
from collections import Counter
from pathlib import Path

with contextlib.redirect_stdout(io.StringIO()):
    audit = runpy.run_path(str(Path(__file__).with_name("replay.py")))
wins = []
for row in audit["complete_rows"]:
    current, empty = [audit["vector"](row["scores"][arm]) for arm in ("IPE_C", "TASK_ONLY")]
    if empty[1] <= current[1] or not all(x >= y for x, y in zip(empty, current)):
        continue
    meta = audit["task_map"][row["uid"]]
    full = meta["archived"]["RPR_PAPER_FULL"]
    for arm, answer, judge in [
        ("IPE_C", full["answer"], full["raw_judge"]),
        ("TASK_ONLY", row["no_history_state"]["answer"], row["no_history_state"]["raw"]),
    ]:
        score = row["scores"][arm]
        assert hashlib.sha256(answer.encode()).hexdigest() == score["answer_sha256"]
        raw = json.loads(judge)
        assert raw["match"] == f'{score["grade"]["match"]["matched"]}/{len(row["labels"])}'
        assert all(raw[k] == score["grade"][k] for k in ("OPB", "UPB", "FM", "RII", "VG"))
    assert len(meta["original_sources"]) == len(row["labels"])
    assert set(row["labels"]) == {"A"}
    wins.append(row)
assert len(wins) == 5
print(json.dumps({"eligible_wins": len(wins), "all_A_positions": sum(len(r["labels"]) for r in wins),
                  "source_group_sizes": sorted(Counter(r["source_group"] for r in wins).values()),
                  "distinct_empty_answers": len({r["scores"]["TASK_ONLY"]["answer_sha256"] for r in wins}),
                  "distinct_history_answers": len({r["scores"]["IPE_C"]["answer_sha256"] for r in wins})}, indent=2))
