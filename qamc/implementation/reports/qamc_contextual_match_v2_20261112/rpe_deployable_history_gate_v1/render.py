"""Render verified aggregate readout without private task contents."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
run = here.parents[2]/"runs"/here.parent.name/(here.name+"_usage")
result = json.loads((run/"private/SETTLED.json").read_text())
print("# Does the history-aware switch beat the task-only switch?\n")
print("Same actor endpoints and grading records for all decisions. Twelve distinct task requests, two different source histories per request. Identical query-only switches were reused within each pair. Source selection used task/UID hashes and distinct histories, without choosing by score. All tasks are exposed development cases.\n")
print("|Subset|Tasks|Positions|Gate or endpoint|History ON|Match|OPB|UPB|FM|")
print("|---|---:|---:|---|---:|---:|---:|---:|---:|")
for subset, card in result["summary"].items():
    for key in ("query","memory","IPE-C","empty","full"):
        r=card[key]
        print(f"|{subset}|{card['tasks']}|{card['positions']}|{key}|{r['open']}|{r['Match']}|{r['OPB']}|{r['UPB']}|{r['FM']}|")
print("\nOPB, UPB and FM are project-adapted grader severity sums, not position counts. See metric availability in the paired-outcome audit.\n")
print(f"Decision disagreements: {result['disagreements']}. Physical gate calls: {result['physical']}. Transport status: {result['status']}. Invalid decisions after successful transport: {result['invalid_outputs']}. Reported tokens: {result['tokens']}. No new Actor answers or native grades. No human review. The original preflight stopped before dispatch because streaming usage was not requested; the corrected transport manifest is separate.")
