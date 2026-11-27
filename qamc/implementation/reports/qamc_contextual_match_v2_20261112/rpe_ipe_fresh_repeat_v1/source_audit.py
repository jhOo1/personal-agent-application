"""Read only the tracked reports as they stood before this study."""
import json
import re
import subprocess
from pathlib import Path

here = Path(__file__).resolve().parent
repo = here.parents[2]
base = here.parent.relative_to(repo)
commit = "4ae07afab"
plan = json.loads((here.parent/"rpeval_formal_multi_coverage_v1/PLAN.json").read_text())
cases = plan["cases"]
assert len(cases) == 300 and all(c["independent_confirmation"] is False for c in cases)
lookup = {(c["track"].split("/")[0], c["row_index"]): c["analysis_group_id"] for c in cases}
uids = {c["uid"]: c["analysis_group_id"] for c in cases}
pat = re.compile(r"(explicit|implicit)/(?:multi/)?(\d{1,3})(?!\d)|rpeval/(?:pa_transfer_20261109/[a-f0-9]+|phase2_remaining/\w+/multi/\d+)")
# git grep limits the corpus to a fixed tree; count a root once across aliases and repeated mentions.
args = ["git","grep","-I","-h","-E","(explicit|implicit)/|rpeval/(pa_transfer|phase2_remaining)",commit,"--",f"{base}/**/*.md"]
lines = subprocess.check_output(args,cwd=repo).decode().splitlines()
mentioned, prose = set(), set()
for line in lines:
    for m in pat.finditer(line):
        group = lookup.get((m[1], int(m[2]))) if m[1] else uids.get(m[0])
        if group:
            mentioned.add(group)
            if not line.lstrip().startswith(("|","rpeval/","{",'"')):
                prose.add(group)
print(dict(cases=len(cases), groups=len(set(uids.values())), mentioned=len(mentioned), outside_simple_tables=len(prose)))
