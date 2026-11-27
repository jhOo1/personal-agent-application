import json
import re
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
run = here.parents[2] / "runs" / here.parent.name / "bench_gate_gepa_feedback_v1"
def read(path):
    return json.loads(path.read_text())

answers = defaultdict(dict)
guides = {}
for path in sorted((run / "Actor/visible").glob("*/record.json")):
    rec = read(path)
    uid, arm = rec["unit"]["root_id"], rec["unit"]["method"]
    if arm not in ("baseline", "score"):
        continue
    wire = read(path.with_name("request.json"))
    guide = json.loads(wire["messages"][-1]["content"])["selected_memory_use_guidance"]
    assert guides.setdefault(uid, guide) == guide
    if rec["status"] == "OK":
        answers[uid][arm] = read(path.with_name("response.json"))["answer"]

def signature(answer):
    numbers = Counter(re.findall(r"\d+(?:[.,]\d+)*", answer))
    bold = bool(re.search(r"\*\*[^*\n]+\*\*", answer))
    return numbers, bold

choices = {}
for uid, guide in guides.items():
    a = answers[uid]
    if "baseline" not in a:
        continue
    triggered = any(re.search(r"\b(concise|brief|brevity|simple|succinct)\b", entry["use_instruction"], re.I) for entry in guide)
    shorter = "score" in a and len(a["score"].split()) < len(a["baseline"].split())
    pick = triggered and shorter
    choices[uid] = {"baseline":"baseline","always_alt":"score","shorter":"score" if pick else "baseline",
                    "guarded":"score" if pick and signature(a["score"]) == signature(a["baseline"]) else "baseline"}

# All choices fixed before opening scores.
grades = {(r["uid"],r["arm"]): r["score"] for r in read(run / "material/SETTLED.json")["rows"]}
profiles = {c["uid"]:c["analysis_group_id"] for c in read(run.with_name("benchpres_repeat_matched_v1")/"PLAN_PRIVATE.json")["cases"]}
totals = defaultdict(Counter)
changed_profiles = defaultdict(set)
for uid, policies in choices.items():
    if not all(grades.get((uid, arm)) for arm in ("baseline", "score")):
        continue
    for policy, arm in policies.items():
        score = grades[uid,arm]
        t = totals[policy]
        t["tasks"] += 1
        if arm == "score":
            t["alternate"] += 1
            changed_profiles[policy].add(profiles[uid])
        for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness"):
            t[k] += score[k]
        for dec in score["decisions"]:
            if dec["appropriate"] and "bold" not in dec["preference"].lower():
                t["nonbold_denominator"] += 1
                t["nonbold_numerator"] += dec["label"] == "follow"
for policy, t in totals.items():
    t["alternate_profiles"] = len(changed_profiles[policy])
print(json.dumps(dict(assigned=len(profiles), wires=len(guides), eligible_baseline=len(choices), totals=totals),indent=2))
