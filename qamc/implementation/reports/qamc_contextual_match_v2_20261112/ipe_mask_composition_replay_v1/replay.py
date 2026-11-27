"""Replay the predicted source mask downstream of the archived task switch."""
import json
from collections import defaultdict
from pathlib import Path

base = Path(__file__).resolve().parents[1]
def rows(name):
    return json.loads((base / name / "RESULTS.json").read_text())["rows"]

routes = {row["uid"]: row for row in rows("ipe_c_two_endpoint_completion_v1")}
panel = [row for row in rows("source_mask_factorization_v1") if row["method"] == "RP_MASK"]
assert len(panel) == len({row["uid"] for row in panel}) == 24
groups = defaultdict(list)
for item in panel:
    route = routes[item["uid"]]
    enabled = route["old_route"] == "REUSE_RP"
    assert enabled or route["old_route"] == "REUSE_ORIGINAL_TASK_ONLY_STATE"
    scores = route["scores"]
    endpoint = "RPR_PAPER_FULL" if enabled else "TASK_ONLY"
    assert scores["IPE_C"]["answer_sha256"] == scores[endpoint]["answer_sha256"]
    old = scores["IPE_C"]["grade"]
    masked = item["score"]
    assert old == scores[endpoint]["grade"]
    assert old["match"]["positions"] == masked["match"]["positions"]
    for label in ("all", "enabled" if enabled else "disabled", "stratum " + item["stratum"]):
        groups[label].append((old, masked if enabled else old, masked))

print("# Predicted source masking after IPE-C\n")
print("Exposed development replay on the complete existing 24-task, nine-source-group mask panel. When the archived switch enables history, use the archived answer generated with predicted A sources and their policy entries physically removed. Otherwise preserve the exact IPE-C answer. No author labels enter the rule. Both source text and its policy entry change together. The full and masked answers were generated at different times.\n")
print("Cells show matched positions / OPB / UPB / FM (the last three are summed severities).\n")
print("|Panel|Tasks|Positions|IPE-C|Switch then mask|Always mask|")
print("|---|---:|---:|---|---|---|")
for name, triples in groups.items():
    total = sum(old["match"]["positions"] for old, _, _ in triples)
    cells = []
    for arm in zip(*triples):
        values = [sum(x["match"]["matched"] for x in arm)]
        values.extend(sum(x[field] for x in arm) for field in ("OPB", "UPB", "FM"))
        cells.append(" / ".join(map(str, values)))
    print("|" + "|".join(map(str, [name,len(triples),total,*cells])) + "|")
