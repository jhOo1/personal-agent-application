"""Join the archived full-memory Raw, Strong Gate, and paper-prompt arms."""
from collections import Counter
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "reports/qamc_contextual_match_20261111/development_v1"
CURRENT = Path(__file__).resolve().parent.parent
PAPER = CURRENT / "benchpres_matched_paper_v1"
GATE = "GEPA_SELECTED_BOUNDS"
SELECTIVITY = "PAPER_SELECTIVITY"
METHODS = ("RAW", GATE, SELECTIVITY)


def read(path):
    return json.loads(path.read_text())


def summarize():
    plan = read(PAPER / "PLAN.json")
    old = read(LEGACY / "PLAN.json")
    cases = {c["uid"]: c for c in plan["cases"]}
    old_cases = {c["uid"]: c for c in old["cases"] if c["benchmark"] == "benchpres"}
    if set(cases) != set(old_cases):
        raise ValueError("Different BenchPreS rosters")
    identity = ("source_id", "row_index", "source_sha256", "public_hash", "evaluation_hash")
    for uid, case in cases.items():
        if any(case[key] != old_cases[uid][key] for key in identity):
            raise ValueError(f"Input identity changed: {uid}")
    for kind in ("generation", "grading"):
        protocol = plan["protocols"][kind]
        qwen = old["protocols"]["qwen"]
        if protocol["model"] != qwen["model"] or any(
                qwen["stages"][s] != settings for s, settings in protocol["stages"].items()):
            raise ValueError(f"Model alias or stage settings changed: {kind}")
    legacy = read(LEGACY / "CURRENT_SCORED_RESULTS.json")
    rows = [r for wave in legacy["waves"] for r in wave["rows"]
            if r["uid"] in cases and r["method"] == "RAW"]
    rows.extend(r for r in plan["inherited_scores"] if r["method"] == GATE)
    rows.extend(read(PAPER / "RESULT_ROWS.json"))
    by = {(r["uid"], r["method"]): r for r in rows}
    if len(by) != len(rows) or set(by) != {(uid, m) for uid in cases for m in METHODS}:
        raise ValueError("Method assignments differ")
    status = {m: Counter(r["actor_status"] if not r["score"] else "SCORED"
                         for (uid, method), r in by.items() if m == method) for m in METHODS}
    common, totals = [], {m: Counter() for m in METHODS}
    fields = ("aar_numerator", "aar_denominator", "mr_numerator", "mr_denominator", "task_completeness")
    for uid, case in cases.items():
        scores = {m: by[uid, m]["score"] for m in METHODS}
        if not all(scores.values()):
            continue
        refs = [(d["preference"], d["appropriate"]) for d in scores["RAW"]["decisions"]]
        for method, grade in scores.items():
            if refs != [(d["preference"], d["appropriate"]) for d in grade["decisions"]]:
                raise ValueError(f"Scored attribute reference changed: {uid}/{method}")
            nonbold = [d for d in grade["decisions"] if d["appropriate"]
                       and all(term not in d["preference"].lower() for term in
                               ("bold text", "bold formatting", "bold typeface"))]
            totals[method].update({f: grade[f] for f in fields})
            totals[method].update(nonbold_n=sum(d["label"] == "follow" for d in nonbold),
                                  nonbold_d=len(nonbold))
        common.append(case)
    return {"assigned": len(cases), "scores_or_status": status, "common": len(common),
            "profiles": len({c["analysis_group_id"] for c in common}), "totals": totals}


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
