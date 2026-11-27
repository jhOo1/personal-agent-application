"""Build the exposed 13-source scorer packet offline. Run with Python 3.11+."""
import ast
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
repo = here.parents[2]
sys.path.insert(0, str(repo / "src"))
from qamc.contextual_match.inspect_judge import InspectPersistJudge, KINDS

author = repo / "literature/qamc_pa_v1/PersistBench"
revision = "d2ded18be6d15ebb14008d081a44bd03c20670e4"
runs = repo / "runs" / here.parent.name

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def from_commit(filename):
    return subprocess.check_output(["git", "-C", str(author), "show", f"{revision}:{filename}"])

# Import just the standalone prompt module with the pinned category constants.
# The package initializer would also import model clients and batch generators.
tree = ast.parse(from_commit("src/benchmark/prompts.py"))
imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
assert len(imports) == 1 and imports[0].module == "benchmark.config"
assert {n.name for n in imports[0].names} == set(KINDS)
tree.body.remove(imports[0])
prompts = dict(KINDS)
exec(compile(tree, "pinned_author_prompts", "exec"), prompts)

lock = read(repo / "reports/qamc_contextual_match_20261111/persist_judge_route_v1/AUTHOR_SOURCE_LOCK.json")
inspect = InspectPersistJudge(repo, lock)
raw = (author / "experiments/multi_turn/paper_traces/baseline_all_models.json").read_bytes()
assert digest(raw) == read(runs / "persist_released_grade_agreement_v1/private/FROZEN.json")["release"]
release = json.loads(raw)
rows = read(runs / "persist_exposure_fr3_v1/RESULTS.json")["rows"]
eligible = {r["uid"] for r in rows}
tasks = {}
for entry in release["entries"].values():
    task = {k:entry[k] for k in ("query","memories")}
    uid = "persistbench/" + digest(canonical(task))[:20]
    if uid in eligible:
        assert uid not in tasks
        tasks[uid] = (entry["failure_type"], task)

jobs, assignments, parity = {}, [], Counter()
for row in rows:
    uid, draw = row["uid"], row["repeat"]
    if uid not in tasks:
        continue
    track, task = tasks[uid]
    assert track == row["track"]
    for method, arm in sorted(row["methods"].items()):
        actor = arm["actor"]
        key = None
        if actor and actor["status"] == "OK" and actor["answer"]:
            answer = actor["answer"]
            messages = [
                dict(role="system", content=prompts["get_judge_system_prompt"](track)),
                dict(role="user", content=prompts["build_judge_prompt"](**task, memory_response=answer)),
            ]
            payload = dict(model="moonshotai/kimi-k2-thinking", messages=messages, temperature=0,
                           provider=dict(order=["google-vertex"], allow_fallbacks=False),
                           reasoning=dict(enabled=True, effort="high"))
            key = digest(canonical([uid, draw, payload]))
            if key not in jobs:
                jobs[key] = payload
                comparison = inspect.request(task["memories"], task["query"], answer, track, "kimi-k2-thinking")["messages"]
                parity[(messages[0] == comparison[0], messages[1] == comparison[1])] += 1
        assignments.append([uid, draw, method, key])
assert len(tasks) == 13 and len(jobs) == 82 and len(assignments) == 125
assert len({tuple(a[:3]) for a in assignments}) == 125
assert sum(a[-1] is None for a in assignments) == 9
packet = canonical(dict(jobs=jobs, assignments=assignments))
out = runs / here.name / "private/NATIVE_13.json"
# Install complete bytes without clobbering a prior freeze, even on concurrent runs.
from tempfile import NamedTemporaryFile
with NamedTemporaryFile(dir=out.parent) as f:
    f.write(packet)
    f.flush()
    os.fsync(f.fileno())
    try:
        os.link(f.name, out)
    except FileExistsError:
        if out.read_bytes() != packet:
            raise ValueError("Native packet differs from the existing freeze")
print(json.dumps(dict(positions=len(assignments), missing=9, jobs=len(jobs), packet_sha256=digest(packet),
                      standalone_revision=revision, inspect_revision=lock["author_commit"],
                      message_parity={f"system={s},user={u}":n for (s,u),n in sorted(parity.items())}), indent=2))
