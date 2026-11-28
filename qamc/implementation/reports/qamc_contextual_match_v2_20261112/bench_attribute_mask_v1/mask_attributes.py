"""Drop attribution requirements in a diagnostic only, keeping all five archived answers."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import runpy

base = Path(__file__).resolve().parent.parent
with redirect_stdout(StringIO()):
    roster = runpy.run_path(str(base / "bench_profile_external_stability_v1/profile_contrasts.py"))
common = roster["common"]
methods = roster["methods"]
archive = roster["data"]
from summarize_reassembly import BOLD

nickname = re.compile(r"\b(?:nicknames?|called)\b", re.I)
records = {}
for uid, method, answer, score, _ in archive["candidates"](archive["panel"]):
    if uid not in common or method not in methods:
        continue
    value, attrs, answer_hash = roster["cells"][uid][method]
    assert archive["sha"](answer) == answer_hash
    decisions = score["decisions"]
    assert sorted((d["preference"], d["appropriate"]) for d in decisions) == attrs
    rows = []
    for d in decisions:
        pref = d["preference"]
        kind = "bold" if BOLD.search(pref) else "nickname" if nickname.search(pref) else "other"
        rows.append((kind, d["appropriate"], d["label"] == "follow"))
    assert sum(a and f for _, a, f in rows) == value["primary"]
    assert sum(not a and f for _, a, f in rows) == value["MR"]
    key = uid, method
    record = rows, value["completeness"] == 5
    assert key not in records or records[key] == record
    records[key] = record
assert len(records) == 37 * 5

print("# Removing bold and nickname attributes from the archived joint endpoint\n")
print("Each cell counts passes on the same 37 exposed tasks. Completeness must still be 5/5.\n")
print("|Omitted requirements|" + "|".join(methods) + "|")
print("|---|" + "---:|" * len(methods))
for skip in ((), ("bold",), ("nickname",), ("bold","nickname")):
    counts = []
    for m in methods:
        n = 0
        for uid in common:
            rows, complete = records[uid, m]
            success = complete and all(a == f for k,a,f in rows if k not in skip)
            if not skip:
                assert success == roster["passed"](roster["cells"][uid][m][0], False)
            n += success
        counts.append(n)
    print("|" + (", ".join(skip) or "none") + "|" + "|".join(map(str,counts)) + "|")
print("\n|Method|Other appropriate realized|Other inappropriate realized|Full completeness|Joint on tasks with other appropriate preferences|")
print("|---|---:|---:|---:|---:|")
for m in methods:
    pairs = [records[u,m] for u in common]
    other = [(a,f) for rows,_ in pairs for k,a,f in rows if k=="other"]
    eligible = [(rows,c) for rows,c in pairs if any(k=="other" and a for k,a,_ in rows)]
    passed = sum(c and all(a==f for k,a,f in rows if k=="other") for rows,c in eligible)
    print(f"|{m}|{sum(a and f for a,f in other)}/{sum(a for a,_ in other)}|"
          f"{sum(not a and f for a,f in other)}/{sum(not a for a,_ in other)}|"
          f"{sum(c for _,c in pairs)}/37|{passed}/{len(eligible)}|")

def remaining_failures(record):
    rows, complete = record
    failures = set()
    if not complete:
        failures.add("completeness")
    for family, appropriate, followed in rows:
        if family == "other" and appropriate != followed:
            failures.add("omission" if appropriate else "misuse")
    return failures

from collections import Counter

print("\n## Matched outcomes after excluding bold and nickname\n")
print("Cells partition the 37 tasks. Loss reasons can overlap.\n")
print("|Comparator|Both pass|Gate only|Comparator only|Neither|Reasons comparator failed on Gate-only tasks|Reasons Gate failed on comparator-only tasks|")
print("|---|---:|---:|---:|---:|---|---|")
for comparator in methods[1:]:
    outcomes = Counter()
    reasons = [Counter(), Counter()]
    for uid in common:
        left = remaining_failures(records[uid, roster["gate"]])
        right = remaining_failures(records[uid, comparator])
        outcomes[not left, not right] += 1
        if not left and right:
            reasons[0].update(right)
        if left and not right:
            reasons[1].update(left)
    assert sum(outcomes.values()) == 37
    columns = [outcomes[key] for key in ((True, True), (True, False), (False, True), (False, False))]
    reasons_text = [", ".join(f"{k} {n}" for k,n in sorted(r.items())) or "none" for r in reasons]
    print("|" + "|".join(map(str, [comparator, *columns, *reasons_text])) + "|")
