"""Trace every RP-only masked pass for which Gate omitted an applicable attribute."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import runpy
from collections import Counter
import re

with redirect_stdout(StringIO()):
    audit = runpy.run_path(str(Path(__file__).with_name("mask_attributes.py")))
gate = audit["roster"]["gate"]
rp = "RPR_PAPER_FULL"
failures = audit["remaining_failures"]
records = audit["records"]
target = [u for u in audit["common"]
          if "omission" in failures(records[u, gate]) and not failures(records[u, rp])]
assert len(target) == 2
print("|Task prefix|Method|AAR|MR|Completeness|Missed applicable requirements|")
print("|---|---|---:|---:|---:|---|")
voice = re.compile(r"\b(?:I|me|my|mine|myself|we|us|our|ours|ourselves)\b", re.I)
by_cell = {}
for uid, method, answer, score, _ in audit["archive"]["candidates"](audit["archive"]["panel"]):
    if uid in audit["common"] and method in audit["methods"]:
        for d in score["decisions"]:
            if not d["appropriate"]:
                continue
            pref = d["preference"].lower()
            if not ("neutral perspective" in pref or "objective information provider" in pref):
                continue
            key = (uid, method, pref)
            row = bool(voice.search(answer)), d["label"] == "follow"
            assert by_cell.setdefault(key, row) == row
    if uid not in target or method not in (rp, gate):
        continue
    missing = [d["preference"].split(" prefers ")[-1] for d in score["decisions"]
               if d["appropriate"] and d["label"] != "follow"]
    print(f"|{uid.split('/')[-1][:8]}|{method}|{score['aar_numerator']}/{score['aar_denominator']}|"
          f"{score['mr_numerator']}/{score['mr_denominator']}|{score['task_completeness']}|"
          + ", ".join(missing) + "|")

print("\n## Is removing first-person pronouns necessary or sufficient for expression credit?\n")
print("|Method|First person present: credited/graded|Absent: credited/graded|")
print("|---|---:|---:|")
for method in audit["methods"]:
    cells = Counter(v for (u,m,p),v in by_cell.items() if m == method)
    present = sum(n for (voice_present,_), n in cells.items() if voice_present)
    absent = sum(cells.values()) - present
    print(f"|{method}|{cells[True,True]}/{present}|{cells[False,True]}/{absent}|")
print(f"\n{len({u for u,m,p in by_cell})} exposed tasks. Counts are attribute judgments; archived answers may share sources.")
