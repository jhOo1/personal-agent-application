"""Verify distinct receipts and publish only aggregate scores and costs."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
run = here.parents[2]/"runs"/here.parent.name/here.name
rows = json.loads((run/"private/RESULTS.json").read_text())["rows"]
scores = {(r["judge"],r["case"],r["wave"],r["arm"]):r["grade"] for r in rows}
assert len(scores) == len(rows) == 16
paths = sorted(run.glob("*/visible/*/response.json"))
replies = [json.loads(p.read_text()) for p in paths]
assert len({r["id"] for r in replies}) == len(replies)
usage = sum(r["usage"]["total_tokens"] for r in replies)
print("# Contemporaneous fixed-answer grading control\n")
print("| Judge | Case | Wave 1 original / edited | Wave 2 original / edited |\n|---|---|---:|---:|")
for judge in ("GPT","Qwen"):
    for case in ("garden","lunch"):
        cells = [" / ".join(str(scores[judge,case,i,a]) for a in ("original","edited")) for i in (1,2)]
        print(f"| {judge} | {case} | {' | '.join(cells)} |")
print(f"\n{len(replies)} distinct physical responses, {usage:,} reported tokens, zero Actor calls.")
