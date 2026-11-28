"""Build two method-blinded packets from frozen exposed answers. No model calls."""
import csv
import hashlib
import hmac
import json
import os
import runpy
import secrets
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

here = Path(__file__).resolve().parent
with redirect_stdout(StringIO()):
    panel = runpy.run_path(str(here.parent / "bench_profile_external_stability_v1/profile_contrasts.py"))
raw = panel["data"]
tasks = set(panel["common"])
methods = (panel["gate"], "PAPER_SELECTIVITY")
from replay import archive

roots = {r["uid"]: r["public_task"] for r in archive.transfer.development_roots("BenchPreS") if r["uid"] in tasks}
assert set(roots) == tasks and len(tasks) == 37
items = {}
for uid, method, answer, score, _ in raw["candidates"](raw["panel"]):
    if uid not in tasks or method not in methods:
        continue
    assert raw["sha"](answer) == panel["cells"][uid][method][2]
    attrs = sorted(d["preference"] for d in score["decisions"])
    assert len(attrs) == len(set(attrs)) == 5
    task = roots[uid]
    item = dict(query=task["query"], current_context=task["current_context"], facts=task["facts"],
                attributes=attrs, answer=answer)
    assert items.setdefault((uid, method), item) == item
assert len(items) == 74
for uid in tasks:
    assert items[uid,methods[0]]["attributes"] == items[uid,methods[1]]["attributes"]

out = here.parents[2] / "runs" / here.parent.name / here.name / "private"
os.umask(0o077)
out.mkdir(parents=True, exist_ok=True)
key_file = out / "private_seed"
if not key_file.exists():
    with key_file.open("xb") as f:
        f.write(secrets.token_bytes(32))
secret = key_file.read_bytes()
assert len(secret) == 32

def token(*parts):
    return hmac.new(secret, json.dumps(parts).encode(), hashlib.sha256).hexdigest()

def store(path, data):
    if path.exists():
        assert path.read_bytes() == data, path.name
    else:
        with path.open("xb") as f:
            f.write(data)

index = {}
for reviewer in ("reader1", "reader2"):
    folder = out / reviewer
    folder.mkdir(exist_ok=True)
    packets = []
    for (uid, method), item in items.items():
        code = token(reviewer, uid, method)[:16]
        assert code not in index
        index[code] = [uid, method, raw["sha"](item["answer"])]
        packets.append(dict(id=code, **item))
    packets.sort(key=lambda p: p["id"])
    store(folder / "tasks.jsonl", "".join(json.dumps(p, ensure_ascii=False)+"\n" for p in packets).encode())
    sheet = StringIO()
    writer = csv.writer(sheet)
    writer.writerow(["id", *[f"attribute_{i}" for i in range(1,6)], "completeness_1_to_5",
                     "unsupported_claim", "unnecessary_disclosure", "omitted_obligation", "supporting_quote_or_note"])
    for p in packets:
        writer.writerow([p["id"], *[""] * 10])
    store(folder / "blank.csv", sheet.getvalue().encode())
    store(folder / "instructions.md", (here / "INSTRUCTIONS.md").read_bytes())
store(out / "coordinator_key.json", json.dumps(index, sort_keys=True).encode())
assert len(index) == 148
print("Verified 37/48 assigned tasks, 74 answers, two reviewer packets, 370 attribute slots per reader. Human ratings collected by this build: 0.")
