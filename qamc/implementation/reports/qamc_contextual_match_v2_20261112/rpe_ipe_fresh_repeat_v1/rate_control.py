"""Post-hoc diagnostic of task assignment at fixed full-history call count."""
import itertools
import json
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
out = here.parents[2] / "runs" / here.parent.name / here.name
summary = []
for n in (1, 2):
    rows = json.loads((out / f"deployment{n}" / "RESULTS.json").read_text())["rows"]
    complete = [r for r in rows if r["branch"] and all(s["grade"].get("match") for s in r["scores"].values())]
    zero = [r["scores"]["TASK_ONLY"]["grade"]["match"]["matched"] for r in complete]
    increments = [r["scores"]["RP_FULL"]["grade"]["match"]["matched"] - z for r,z in zip(complete,zero)]
    selected = [i for i,r in enumerate(complete) if r["branch"]=="RP_FULL"]
    actual = sum(zero) + sum(increments[i] for i in selected)
    histogram = Counter(sum(zero)+sum(increments[i] for i in choice)
                        for choice in itertools.combinations(range(len(complete)),len(selected)))
    total = sum(histogram.values())
    summary.append(dict(deployment=n, paired=len(complete), full=len(selected),
                        positions=sum(r["scores"]["TASK_ONLY"]["grade"]["match"]["positions"] for r in complete),
                        actual=actual, assignment_count=total, at_least_actual=sum(count for score,count in histogram.items() if score>=actual),
                        mean=sum(k*v for k,v in histogram.items())/total, min=min(histogram),max=max(histogram)))
(here / "RATE_CONTROL.json").write_text(json.dumps(summary, indent=2)+"\n")
