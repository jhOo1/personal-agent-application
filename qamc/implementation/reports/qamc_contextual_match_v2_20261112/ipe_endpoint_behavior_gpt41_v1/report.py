"""Summarize paired behavior assessments, including the fixed exposure-rate control."""
from evaluate import main, REVIEW, RUN

plan = REVIEW.read(RUN / "FROZEN.json")
REVIEW.RUN = RUN
REVIEW.check_vote = main.validator(REVIEW.check_vote)
results = REVIEW.report(plan, allow_pending=True)
rows = [row for row in results["reviews"] if row["assessment"]]
opened = sum(row["ipe"] == main.RP for row in rows)
rate = opened / len(rows) if rows else 0
summary = main.summarize(results)["cards"]["all"]
print("# RPEval archived endpoint behavior check\n")
print(f"Frozen source groups: {len(plan['packets'])}. Requests: {results['physical_requests']}. "
      f"Receipt statuses: {results['status_counts']}. Reported tokens: {results['reported_tokens']}. "
      f"Unknown usage: {results['unknown_usage']}. Valid paired assessments: {len(rows)}. "
      f"History enabled on {opened} of these. No new Actor answers, native scores or human judgments.\n")
print("|Author intent|Paired determinate positions|Task only|Full history|IPE-C|Expected at same opening rate|")
print("|---|---:|---:|---:|---:|---:|")
for label in "ABC":
    task, full, route = [summary.get(f"{arm}_match_{label}", 0) for arm in (main.TASK, main.RP, "IPE_C")]
    denominator = summary.get(f"paired_{label}", 0)
    expected = (1-rate)*task + rate*full
    print(f"|{label}|{denominator}|{task}|{full}|{route}|{expected:.2f}|")
print("\nNumerators count behavior matching the author intent in both-endpoint determinate positions. "
      "For A, either no use or an independently task-justified decision qualifies. B requires soft use, "
      "C requires a binding constraint. Unknowns and indeterminate task-justified B/C judgments are excluded pairwise. "
      "The reference is the expectation over uniform random assignment of the same count of open tasks; it uses no labels. "
      "This panel deliberately balances rare route strata. Its old native-adapted Match was 60/118 for IPE-C, "
      "64/118 task only and 72/118 full history. Behavior judgments share the gpt-4.1 alias with the project scorer. "
      "Assessment availability depends on strict JSON and literal evidence checks. No imputation.")
for arm in (main.TASK, main.RP, "IPE_C"):
    print(f"\n{arm}: complete {summary.get(arm+'_completion_COMPLETE', 0)}/{len(rows)}, "
          f"requirement violations {summary.get(arm+'_requirements_VIOLATION',0)}, "
          f"unsupported fact violations {summary.get(arm+'_facts_VIOLATION',0)}.")
