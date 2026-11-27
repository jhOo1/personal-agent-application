"""Attribute existing paired deployment receipts to each implementable execution path."""
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
import json

base = Path(__file__).resolve().parents[3]
run = base / "runs/qamc_contextual_match_v2_20261112/rpe_ipe_fresh_repeat_v1"
def read(path):
    return json.loads(path.read_text())

def analyze(folder):
    rows = read(folder / "RESULTS.json")["rows"]
    records = {}
    for stage in ("Estimate", "Actor"):
        for f in (folder/stage).glob("visible/*/record.json"):
            r = read(f)
            key = (r["unit"]["root_id"],r["unit"]["method"])
            assert key not in records and r["status"]=="OK" and r["automatic_retries"]==0
            records[key] = r
    assert len(records) == 4 * len(rows)
    totals = defaultdict(Counter)
    times = defaultdict(list)
    for row in rows:
        uid = row["uid"]
        branch = row["branch"]
        assert branch in ("RP_FULL","TASK_ONLY")
        specs = {"lazy":["RPR_IPE"] + (["RPR_MLE"] if branch=="RP_FULL" else []) + [branch],
                 "full":["RPR_IPE","RPR_MLE","RP_FULL"], "empty":["TASK_ONLY"]}
        for name, arms in specs.items():
            c = totals[name]
            c["generation_requests"] += len(arms)
            for arm in arms:
                usage = records[uid,arm]["usage"]
                for k in ("prompt_tokens","completion_tokens","total_tokens"):
                    assert isinstance(usage[k],int)
                    c[k] += usage[k]
            durations = [records[uid,k]["elapsed_seconds"] for k in arms]
            modeled = max(durations[:2])+durations[-1] if name=="full" else sum(durations)
            times[name].append(modeled)
            times[name+"/"+branch].append(modeled)
    return dict(roots=len(rows),routes=Counter(r["branch"] for r in rows), attributed=totals,
                median_modeled_seconds={k:round(median(v),2) for k,v in times.items()})

print(json.dumps({i:analyze(run/f"deployment{i}") for i in (1,2)},indent=2))
